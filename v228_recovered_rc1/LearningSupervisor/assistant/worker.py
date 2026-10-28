"""Read-only native journal -> frozen RC1 context -> grounded local explanation."""
from collections import Counter
from datetime import datetime, timezone, timedelta
import csv
import hashlib
import html
import io
import json
from pathlib import Path
import re
import time
import unicodedata

from . import CONTRACT
from .anchors import read_anchor
from .catalog import facts_for, default_selection, QUESTIONS
from .context.engine import ContextObserver
from .local_model import load_config, select
from supervisor.store import Store, atomic, digest
from intelligence.demo_learning import read_policy
from intelligence.origin import read_origin
from intelligence.native_ledger import decode_bytes

def separate(a,b):
    return a!=b and a not in b.parents and b not in a.parents

def channel_name(value):
    if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,48}',value):
        raise ValueError('Use a simple unique assistant channel, without paths')
    return value

class ContextStream:
    def __init__(self,store,offset):
        self.store=store;self.offset=offset;self.engine=ContextObserver();self.snapshot=None
        self.bars={r['broker_bar']['time']:r for r in store.all('ai_bar')}
        for r in sorted(self.bars.values(),key=lambda r:r['broker_bar']['time']):
            if r['used']:
                b=dict(r['broker_bar']);b['time']-=offset*60
                self.snapshot=self.engine.update(b)

    def feed(self,bars,available_ms):
        for b in bars:
            old=self.bars.get(b['time'])
            if old:
                if old['broker_bar']!=b:raise ValueError('Overlapping closed-bar history changed')
                continue
            if self.offset is None:
                self.store.put('ai_unclocked_bar',b['time'],dict(broker_bar=b));continue
            converted=dict(b);converted['time']-=self.offset*60
            used=self.engine.last is None or converted['time']>self.engine.last
            receipt=dict(broker_bar=b,used=used,first_available_broker_ms=available_ms)
            self.store.put('ai_bar',b['time'],receipt);self.bars[b['time']]=receipt
            if used:self.snapshot=self.engine.update(converted)
        return self.snapshot

class Assistant:
    def __init__(self,source,output,offset=None,channel='v224_demo',common=None,config=None):
        self.source=Path(source).resolve();self.output=Path(output).resolve()
        if not separate(self.source,self.output):raise ValueError('Assistant output and journal must be separate, non-nested directories')
        if offset is not None and (type(offset) is not int or not -720<=offset<=840 or offset%5):
            raise ValueError('Verified broker offset must align with M5')
        self.channel=channel_name(channel);self.common=Path(common).resolve() if common else None
        if self.common and not separate(self.source,self.common):raise ValueError('Common telemetry overlaps native source')
        if self.common and not separate(self.output,self.common):raise ValueError('Common telemetry overlaps assistant output')
        self.config=load_config(config);self.offset=offset
        self.policy=read_policy(self.source);self.origin=read_origin(self.source,self.policy)
        self.metadata={n:hashlib.sha256((self.source/n).read_bytes()).hexdigest() for n in ('demo_policy.csv','data_origin.csv')}
        self.store=Store(self.output)
        self.identity=dict(contract=CONTRACT,source=str(self.source),policy=self.policy,origin=self.origin,offset=offset,channel=self.channel,metadata=self.metadata)
        try:
            self.store.put('ai_identity','source',self.identity);self.store.commit()
            self.verify_prefix()
            self.stream=ContextStream(self.store,offset)
            native=self.store.all('ai_native');self.last=max((r['sequence'] for r in native),default=0)
            views=self.store.all('ai_view');self.view=max(views,key=lambda r:r['sequence']) if views else None
            self.last_observed=max((r['observed_ms'] for r in native),default=0)
            self.symbol=self.view['symbol'] if self.view else ''
        except Exception:
            self.store.close();raise
        self.last_model_mono=-float('inf');self.last_model_facts=None
        self.model_status='LOCAL_MODEL_NOT_CONFIGURED' if not self.config['enabled'] else 'LOCAL_MODEL_WAITING'
        self.model_selection=None;self.model_evidence=None;self.last_model_error=None
        self.last_page=None

    def verify_prefix(self):
        for n,h in self.metadata.items():
            if hashlib.sha256((self.source/n).read_bytes()).hexdigest()!=h:raise ValueError('Assistant source metadata changed')
        for kind in ('ai_native','ai_anchor_file'):
            for r in self.store.all(kind):
                p=self.source/r['file']
                if p.is_symlink() or not p.resolve().is_relative_to(self.source) or hashlib.sha256(p.read_bytes()).hexdigest()!=r['sha256']:
                    raise ValueError('Previously observed assistant source bytes changed')

    def _native_view(self,record):
        e=record['event'];c=record['state']['current']
        action=e['lockedAction'] if e['kind']==3 else c['candidate']['direction']
        if action not in (-1,0,1):raise ValueError('Native action invalid')
        return dict(kind=e['kind'],action=action,reason=e['reason'],setup=c['candidate']['setup'],regime=c['anchor']['regime'],
                    asof_broker_ms=e['observedMs'],horizon_minutes=self.policy['horizon']*5)

    def poll(self,limit=512):
        if type(limit) is not int or not 1<=limit<=4096:raise ValueError('Invalid assistant batch size')
        # The foreground work is bounded; model inference runs only after catching up.
        processed=0;changed=False
        for _ in range(limit):
            path=self.source/f'event_{self.last+1:012d}.bin'
            if not path.exists():
                if any(re.fullmatch(r'event_\d{12}\.bin',p.name) and int(p.stem[6:])>self.last+1 for p in self.source.glob('event_*.bin')):
                    raise ValueError('Native assistant sequence gap')
                break
            if path.is_symlink() or not path.resolve().is_relative_to(self.source):raise ValueError('Native file escaped source')
            raw=path.read_bytes();record=decode_bytes(raw,self.last+1,compact=True);s,e=record['state'],record['event']
            if s['configHash']!=self.policy['config_hash'] or s['feedHash']!=self.policy['feed_hash']:
                raise ValueError('Assistant native policy differs')
            if e['kind']==1:
                bars,receipt=read_anchor(self.source,record,self.policy)
                if self.symbol and receipt['symbol']!=self.symbol:raise ValueError('Assistant symbol changed')
                self.symbol=receipt['symbol'];snapshot=self.stream.feed(bars,e['observedMs'])
                if snapshot is not None and snapshot['asof_ms']>e['observedMs']-self.offset*60000:
                    raise ValueError('Future context cannot describe this native anchor')
                self.store.put('ai_anchor_file',receipt['start'],receipt)
                self.view=dict(sequence=self.last+1,snapshot=snapshot,symbol=self.symbol,native=self._native_view(record),
                    available_at_broker_ms=e['observedMs'],context_feature_eligible=False,
                    timing='CLOSED_HISTORY_REPLAY_AVAILABLE_AT_THIS_ANCHOR_NOT_A_PROSPECTIVE_FORECAST')
                self.store.put('ai_view',self.last+1,self.view);changed=True
            elif e['kind']==3:
                # Context comes only from closed anchor history, not later path or result.
                if self.stream.snapshot is not None and self.stream.snapshot['asof_ms']>e['observedMs']-self.offset*60000:
                    raise ValueError('Future context cannot describe this native LOCK')
                self.view=dict(sequence=self.last+1,snapshot=self.stream.snapshot,symbol=self.symbol,native=self._native_view(record),
                    available_at_broker_ms=e['observedMs'],context_feature_eligible=False,
                    timing='LOCK_OBSERVATION_NOT_A_PRELOCK_ADVICE')
                self.store.put('ai_view',self.last+1,self.view);changed=True
            self.last+=1;processed+=1;self.last_observed=max(self.last_observed,e['observedMs'])
            self.store.put('ai_native',self.last,dict(sequence=self.last,file=path.name,sha256=hashlib.sha256(raw).hexdigest(),observed_ms=e['observedMs']))
        self.store.commit()
        backlog=(self.source/f'event_{self.last+1:012d}.bin').exists()
        return self.render(backlog=backlog,changed=changed,processed=processed)

    def render(self,backlog=False,changed=False,processed=0,error=None):
        bars=list(self.stream.bars.values());used=sum(r['used'] for r in bars)
        progress=dict(closed_m5_used=used,late_bars_ignored=len(bars)-used,completed_h1=self.stream.engine.h1.count,
                      completed_m15=self.stream.engine.m15.count,clock_known=self.offset is not None)
        snapshot=self.view['snapshot'] if self.view else None
        asof_utc=self.last_observed-self.offset*60000 if self.offset is not None else None
        now=time.time_ns()//1000000
        source_age=now-asof_utc if self.origin=='LIVE_MT4' and asof_utc is not None else None
        source_stale=source_age is not None and source_age>360000
        clock_ahead=source_age is not None and source_age< -5000
        context_reference=now if self.origin=='LIVE_MT4' else asof_utc
        stale=snapshot is not None and (context_reference-snapshot['asof_ms']>=300000 or context_reference<snapshot['asof_ms'] or source_stale or clock_ahead)
        current=None if stale else snapshot
        facts=facts_for(current,self.view['native'] if self.view else None,progress)
        key=digest(facts);selection=default_selection(facts)
        if self.config['enabled'] and not backlog and error is None and not source_stale and not clock_ahead:
            if key!=self.last_model_facts and time.monotonic()-self.last_model_mono>=self.config['minimum_interval_seconds']:
                start=time.monotonic();self.last_model_mono=start;self.model_selection=None;self.model_evidence=None;self.last_model_facts=key
                try:
                    chosen,evidence=select(self.config,facts)
                    self.model_selection=chosen;self.model_evidence=evidence;self.model_status='LOCAL_MODEL_SELECTED_EVIDENCE';self.last_model_error=None
                    self.store.put('ai_local_selection',digest(dict(facts=key,evidence=evidence)),dict(facts_sha256=key,selection=chosen,evidence=evidence,
                        completed_utc_ms=time.time_ns()//1000000,elapsed_ms=round((time.monotonic()-start)*1000),ea_effects=False))
                    self.store.commit()
                except Exception as ex:
                    self.model_status='LOCAL_MODEL_UNAVAILABLE';self.last_model_error=type(ex).__name__
            if key==self.last_model_facts and self.model_selection is not None:
                selection=self.model_selection
            elif self.model_status=='LOCAL_MODEL_SELECTED_EVIDENCE':
                self.model_status='LOCAL_MODEL_WAITING_NEW_FACTS'
        if error:self.model_status='SOURCE_ERROR'
        selected={r['id']:r['text'] for r in facts}
        health='ERROR' if error else 'CATCHING_UP' if backlog else 'COLLECTING_CLOCK_UNKNOWN' if self.offset is None else 'SOURCE_CLOCK_AHEAD' if clock_ahead else 'SOURCE_STALE' if source_stale else 'RUNNING'
        status=dict(contract=CONTRACT,updated_utc_ms=now,origin=self.origin,channel=self.channel,symbol=self.symbol,mode='BINARY_RESEARCH',
                    native_records=self.last,new_records_this_poll=processed,source_asof_broker_ms=self.last_observed,
                    broker_utc_offset_minutes=self.offset,context_stale=bool(stale),context=current,progress=progress,
                    context_available_at_broker_ms=self.view['available_at_broker_ms'] if self.view else None,
                    context_timing=self.view['timing'] if self.view else None,source_age_seconds=source_age/1000 if source_age is not None else None,
                    health=health,error=error,model_status=self.model_status,local_model=self.config['model'] if self.config['enabled'] else None,
                    local_model_error=self.last_model_error,local_model_evidence=self.model_evidence if self.last_model_facts==key else None,
                    facts=facts,selection=selection,explanations=[selected[x] for x in selection['fact_ids']],
                    research_proposals=[QUESTIONS[x] for x in selection['question_ids']],
                    probability_30m=None,market_model_trained=False,ea_control_enabled=False,advisory_reply_written=False,
                    retrospective=self.origin=='BACKTEST_MT4',context_feature_eligible=False)
        atomic(self.output/'assistant_status.json',status)
        page_key=digest({k:v for k,v in status.items() if k not in ('updated_utc_ms','source_age_seconds','new_records_this_poll')})
        if page_key!=self.last_page:
            self._page(status,bars);self.last_page=page_key
        if self.common:
            self._telemetry(status)
        return status

    def _page(self,s,bars):
        esc=html.escape
        title='V2.24 RC3 — Trợ lý phân tích cục bộ'
        text='''<!doctype html><html lang="vi"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta http-equiv="refresh" content="10"><title>Trợ lý V2.24 RC3</title><style>body{background:#101923;color:#e9f0f5;font:16px system-ui;max-width:1000px;margin:24px auto;padding:0 16px}section{background:#1c2c3b;padding:16px;border-radius:8px;margin:14px 0}h1{font-size:25px}p,li{line-height:1.6;overflow-wrap:anywhere}pre{white-space:pre-wrap;overflow-wrap:anywhere}table{width:100%;border-collapse:collapse}td,th{text-align:left;padding:8px;border-bottom:1px solid #40556a}.warn{color:#ffda86}</style>'''
        text+='<h1>'+title+'</h1><p>'+esc(s['health']+' | '+s['origin']+' | '+(s['symbol'] or 'CHƯA CÓ SYMBOL'))+'</p>'
        if s['retrospective']:text+='<p class="warn">Dữ liệu Tester hồi cứu, không phải dự báo live hoặc bằng chứng AI đã tư vấn trước Entry.</p>'
        if s['context_stale']:text+='<p class="warn">Bối cảnh cũ so với nhật ký mới nhất; chưa hiển thị như trạng thái hiện tại.</p>'
        if s['health'] in ('SOURCE_STALE','SOURCE_CLOCK_AHEAD'):text+='<p class="warn">Nguồn EA chưa có sự kiện mới hoặc đồng hồ lệch; heartbeat trợ lý không chứng minh EA vẫn thu dữ liệu.</p>'
        if s['error']:text+='<p class="warn">'+esc(s['error'])+'</p>'
        model=s['local_model'] or 'Chưa cấu hình mô hình ngôn ngữ'
        text+='<section><h2>Trạng thái năng lực</h2><p>'+esc(model+' | '+s['model_status'])+'</p><p>Đã có: mô tả RC1 theo quy tắc và giải thích dựa trên dữ kiện. Chưa có: mô hình thắng/thua 30 phút đủ kiểm định. Quyền thay đổi tín hiệu: OFF.</p></section>'
        text+='<section><h2>Điểm cần chú ý</h2><ul>'+''.join('<li>'+esc(x)+'</li>' for x in s['explanations'])+'</ul></section>'
        text+='<section><h2>Đề xuất nghiên cứu</h2><ul>'+''.join('<li>'+esc(x)+'</li>' for x in s['research_proposals'])+'</ul><p>Đây là câu hỏi kiểm chứng, không phải kết luận phải sửa EA hoặc mở lệnh.</p></section>'
        days=Counter(datetime.fromtimestamp((r['broker_bar']['time']-(self.offset or 0)*60),timezone(timedelta(hours=7))).strftime('%d/%m/%Y') for r in bars if r['used']) if self.offset is not None else Counter()
        text+='<section><details><summary>Tiến triển dữ liệu theo ngày thị trường, giờ Việt Nam</summary><p>Số nến được ghi nhận; không phải điểm thông minh hoặc số mẫu WIN/LOSS độc lập.</p><table><tr><th>Ngày</th><th>Nến M5</th></tr>'+''.join('<tr><td>'+day+'</td><td>'+str(n)+'</td></tr>' for day,n in sorted(days.items(),key=lambda x:datetime.strptime(x[0],'%d/%m/%Y'),reverse=True)[:60])+'</table></details></section>'
        text+='<section><details><summary>Dữ kiện và thời điểm khả dụng</summary><pre>'+esc(json.dumps(dict(progress=s['progress'],facts=s['facts']),ensure_ascii=False,indent=2))+'</pre></details></section>'
        text+='<p>LLM chỉ chọn mã dữ kiện/câu hỏi đã xác minh; báo cáo không hiển thị câu văn hoặc xác suất tự sinh. Không đọc kết quả tương lai để mô tả bối cảnh. Tắt trợ lý không đổi quyết định EA.</p></html>'
        tmp=self.output/'assistant_dashboard.html.tmp';tmp.write_text(text,encoding='utf-8');tmp.replace(self.output/'assistant_dashboard.html')

    def _telemetry(self,s):
        dest=self.common/'V224Assistant'/self.channel;dest.mkdir(parents=True,exist_ok=True)
        owner=dest/'owner.json';identity=digest(self.identity)
        try:
            with owner.open('x',encoding='ascii') as f:f.write(json.dumps(dict(identity_sha256=identity)))
        except FileExistsError:
            if json.loads(owner.read_text())!={'identity_sha256':identity}:
                raise ValueError('Assistant channel already belongs to another source; choose a fresh channel')
        def ascii_text(value):
            value=value.replace('đ','d').replace('Đ','D')
            return ''.join(c for c in unicodedata.normalize('NFKD',value).encode('ascii','ignore').decode() if c not in ',;"\r\n')[:100]
        context=s['context'];age=context['observed_age_minutes'] if context else None
        summary=next((r['text'] for r in s['facts'] if r['id']=='CONTEXT'),'Chua du du lieu')
        cells=[1,s['updated_utc_ms']//1000,s['origin'],s['symbol'],s['mode'],300,s['source_asof_broker_ms']//1000,self.channel,
               context['direction'] if context else 'UNKNOWN','N/A' if age is None else f'{age:g}m',context['phase'] if context else 'COLLECTING',
               s['model_status'],s['health'],ascii_text(summary),ascii_text(s['research_proposals'][0])]
        buffer=io.StringIO(newline='');csv.writer(buffer,lineterminator='\r\n').writerow(cells)
        tmp=dest/'status.csv.tmp'
        try:tmp.write_text(buffer.getvalue(),encoding='ascii');tmp.replace(dest/'status.csv')
        except PermissionError:pass  # Windows read lock: retry next heartbeat; never touch native files.

    def close(self):
        self.store.close()
