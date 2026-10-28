"""Local HTML and optional MT4 Common Files telemetry; display only."""
from collections import Counter
from datetime import datetime, timezone,timedelta
import csv
import html
import io
import json
import unicodedata
from pathlib import Path
from .store import atomic,digest
from .forecast import shadow_evaluation

def render(collector, common_dir=None, error=None):
    s=collector.status();store=collector.store
    models=store.all('model');evaluations=shadow_evaluation(store)
    worker_file=store.output/'research_worker_status.json'
    worker=json.loads(worker_file.read_text()) if worker_file.exists() else None
    worker_failed=worker is not None and worker.get('state')=='FAILED'
    audited=store.all('label');decisive=sum(r['status'] in ('WIN','LOSS') for r in audited)
    eval_count=sum((e['metrics'] or {}).get('samples',0) for e in evaluations)
    # Levels reflect evidence, not intelligence, profitability or permission.
    level=0 if not s['official_cases'] else 1 if not models else 2 if not eval_count else 3
    s.update(level=level,level_name=('CHO DU LIEU','DANG THU THAP','DA HUAN LUYEN - SHADOW','DANG KIEM THU DU BAO')[level],
             audited_decisive=decisive,models=len(models),forward_evaluation=evaluations,
             health='STOPPED_ERROR' if error else 'BACKGROUND_RESEARCH_FAILED' if worker_failed else 'RUNNING',
             error=error,research_worker=worker)
    progress=dict(official_cases=s['official_cases'],audited_decisive=decisive,models=len(models),
        prospective=s['prospective'],forward_evaluation=evaluations)
    previous=store.db.execute("SELECT id FROM facts WHERE kind='progress' ORDER BY rowid DESC LIMIT 1").fetchone()
    if previous is None or store.get('progress',previous[0])['summary']!=progress:
        old=store.get('progress',previous[0])['summary'] if previous else {}
        moment=s['updated_utc_ms']
        store.put('progress',digest(progress),dict(utc_ms=moment,summary=progress,
            delta={k:progress[k]-old.get(k,0) for k in ('official_cases','audited_decisive','models','prospective')}))
        store.commit()
    atomic(store.output/'status.json',s)
    cases=[c for c in store.all('case') if not store.get('withheld',c['signal_id'])]
    days=Counter(datetime.fromtimestamp(c['entry_ms']/1000,timezone.utc).strftime('%Y-%m-%d') for c in cases)
    label_by={l['signal_id']:l['status'] for l in audited}
    statuses={}
    for c in cases:
        day=datetime.fromtimestamp(c['entry_ms']/1000,timezone.utc).strftime('%Y-%m-%d')
        statuses.setdefault(day,Counter())[label_by.get(c['signal_id'],'CHUA DOI SOAT')]+=1
    rows=''.join('<tr><td>'+html.escape(day)+'</td><td>'+str(days[day])+'</td><td>'+html.escape(str(dict(statuses[day])))+'</td></tr>' for day in sorted(days,reverse=True)[:60])
    def metric(e):
        if not e['metrics']:return 'Chưa có kết quả dự báo tiến tới đã đối soát.'
        m,b=e['metrics'],e['baseline']
        return f"{m['samples']} mẫu | Brier {m['brier']:.4f} / cơ sở {b['brier']:.4f} | Log loss {m['log_loss']:.4f} / cơ sở {b['log_loss']:.4f} | Đề xuất giữ {e['selected']} tín hiệu, đúng {e['selected_wins']}."
    forward=''.join('<p>'+html.escape(e['model_id'][:12]+': '+metric(e))+'</p>' for e in evaluations) or '<p>Chưa có mô hình. Chưa phát sinh dự báo của bộ học.</p>'
    training=store.output/'research/models/training_status.json'
    if not training.exists():training=store.output/'models/training_status.json'
    preflight=json.loads(training.read_text()) if training.exists() else None
    training_text=html.escape(json.dumps(preflight,ensure_ascii=False,indent=2)) if preflight else 'Chưa chạy lệnh TRAIN. Chỉ đếm mẫu đã đối soát; không huấn luyện sau từng lệnh thua.'
    knowledge_path=store.output/'research/knowledge.json'
    if not knowledge_path.exists():knowledge_path=store.output/'knowledge.json'
    knowledge=json.loads(knowledge_path.read_text()) if knowledge_path.exists() else None
    experience='Chưa đủ mẫu để rút kinh nghiệm.'
    proposal='Tiếp tục thu thập; chưa đề xuất sửa EA.'
    if knowledge and knowledge['findings']:
        main=max(knowledge['findings'],key=lambda f:f['decisive'])
        experience=f"{main['group']}: {main['counts'].get('WIN',0)}/{main['decisive']} WIN; mới là quan sát."
        if knowledge['proposals']:proposal='Cần kiểm định thêm '+knowledge['proposals'][0]['area']+' trên tập mới.'
    page='''<!doctype html><html lang="vi"><meta charset="utf-8"><meta http-equiv="refresh" content="10"><title>V2.24 Bộ học giám sát</title>
<style>body{background:#111923;color:#e8eef4;font:16px system-ui;max-width:1100px;margin:32px auto;padding:0 20px}h1{font-size:26px}.cards{display:flex;gap:12px;flex-wrap:wrap}.card,section{background:#1d2b3a;border:1px solid #37526b;padding:18px;border-radius:9px;margin:12px 0}.card strong{display:block;font-size:28px;color:#58d6bd}table{width:100%;border-collapse:collapse}td,th{padding:10px;text-align:left;border-bottom:1px solid #37526b}pre{white-space:pre-wrap;font-size:13px}.note{color:#b8c9db}</style>'''
    page+=f'<h1>V2.24 — Bộ học giám sát Binary</h1><p>{html.escape(s["level_name"])} | {html.escape(s["health"])} | {html.escape(s["origin"])}</p>'
    if error:page+='<p style="color:#ffb4a8">'+html.escape(error)+'</p>'
    if worker_failed:page+='<p style="color:#ffb4a8">Đối soát / huấn luyện nền gặp lỗi. WATCH vẫn ghi hồ sơ; kiểm tra research/worker.log. Chưa coi kết quả cũ là kết quả mới.</p>'
    page+='<section><h2>Tóm tắt bộ học</h2><p><strong>Ghi nhận:</strong> '+html.escape(experience)+'</p><p><strong>Đề xuất:</strong> '+html.escape(proposal)+'</p><p>Quyền can thiệp EA: OFF. Các phần thông tin chung, Binary và Forex vẫn xem trên Dashboard của EA đang chạy.</p></section>'
    page+='<div class="cards">'+''.join(f'<div class="card"><strong>{v}</strong>{k}</div>' for k,v in (
        ('Tín hiệu chính thức',s['official_cases']),('Mẫu WIN/LOSS đã đối soát',decisive),('Quyết định quan sát',s['observed_decisions']),
        ('Mô hình đã đóng băng',len(models)),('Dự báo ghi trước giờ vào',s['prospective'])))+'</div>'
    page+='<section><h2>Kết quả dự báo trên dữ liệu mới</h2>'+forward+'</section>'
    page+='<section><details><summary>Nhật ký tiến triển (giờ Việt Nam)</summary><table><tr><th>Thời điểm có thay đổi</th><th>Tích lũy thêm</th></tr>'
    for r in sorted(store.all('progress'),key=lambda r:r['utc_ms'],reverse=True)[:30]:
        moment=datetime.fromtimestamp(r['utc_ms']/1000,timezone(timedelta(hours=7))).strftime('%d/%m %H:%M:%S')
        d=r['delta'];text=f"{d['official_cases']:+d} tín hiệu; {d['audited_decisive']:+d} mẫu đã đối soát; {d['models']:+d} mô hình; {d['prospective']:+d} dự báo trước giờ vào"
        page+='<tr><td>'+moment+'</td><td>'+html.escape(text)+'</td></tr>'
    page+='</table><p class="note">Chỉ ghi khi bằng chứng thay đổi. Thêm mẫu chưa đồng nghĩa chất lượng dự báo tăng; cần xem sai số trên dữ liệu mới.</p></details></section>'
    page+='<section><details><summary>Chi tiết huấn luyện theo đợt</summary><pre>'+training_text+'</pre></details></section>'
    if knowledge_path.exists():
        knowledge=json.loads(knowledge_path.read_text())
        page+='<section><details><summary>Bộ học đã ghi nhận gì?</summary><table><tr><th>Nhóm thị trường</th><th>WIN / Mẫu quyết định</th><th>Bằng chứng</th></tr>'
        for finding in knowledge['findings']:
            page+='<tr><td>'+html.escape(finding['group'])+'</td><td>'+str(finding['counts'].get('WIN',0))+' / '+str(finding['decisive'])+'</td><td>'+html.escape(finding['evidence'])+'</td></tr>'
        page+='</table><p class="note">Thống kê mô tả toàn bộ hồ sơ đã đối soát. Đây là nơi đặt giả thuyết, không dùng làm bằng chứng kiểm định độc lập.</p></details></section>'
        page+='<section><h2>Đề xuất nghiên cứu / nâng cấp</h2>'
        if not knowledge['proposals']:page+='<p>Chưa đủ số mẫu trong từng nhóm để đặt đề xuất có cơ sở.</p>'
        for proposal in knowledge['proposals']:
            page+='<p><strong>'+html.escape(proposal['area'])+'</strong>: '+html.escape(proposal['reason']+' '+proposal['action'])+'</p>'
        page+='</section>'
    page+='<section><details><summary>Dữ liệu theo ngày (ngày theo tọa độ server)</summary><table><tr><th>Ngày</th><th>Tín hiệu</th><th>Kết quả MT4 đã đối soát</th></tr>'+rows+'</table></details></section>'
    page+='<p class="note">Brier và Log loss càng thấp càng tốt. Mốc phát triển là trạng thái bằng chứng, không phải điểm thông minh. Kiến thức ở đây là thống kê và trọng số mô hình; không phải hiểu thị trường như con người. Bộ học không điều khiển EA. Hồi cứu không được tính là dự báo tiến tới. HTML tự tải lại mỗi 10 giây khi tiến trình WATCH còn chạy.</p></html>'
    temp=store.output/'dashboard.html.tmp';temp.write_text(page,encoding='utf-8');temp.replace(store.output/'dashboard.html')
    if common_dir:
        common=Path(common_dir).resolve();dest=common/'V224Supervisor'
        if common==collector.source or collector.source in common.parents or common in collector.source.parents:
            raise ValueError('Common telemetry cannot point inside/above source journal')
        dest.mkdir(parents=True,exist_ok=True)
        buffer=io.StringIO(newline='');writer=csv.writer(buffer,lineterminator='\r\n')
        def ascii_line(value):
            value=value.replace('đ','d').replace('Đ','D')
            return ''.join(c for c in unicodedata.normalize('NFKD',value).encode('ascii','ignore').decode() if c not in ',;"\r\n')[:100]
        writer.writerow([2,s['updated_utc_ms']//1000,level,s['official_cases'],decisive,s['prospective'],len(models),
                         'ERROR' if error or worker_failed else 'SHADOW_ONLY',ascii_line(experience),ascii_line(proposal)])
        tmp=dest/'learning_status.csv.tmp'
        try:
            tmp.write_text(buffer.getvalue(),encoding='ascii');tmp.replace(dest/'learning_status.csv')
        except PermissionError:
            # MT4 can briefly hold the file on Windows. Retry at the next heartbeat.
            s['common_telemetry']='RETRY_NEXT_HEARTBEAT'
    return s
