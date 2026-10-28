"""Public weekly calendar collector; observation only, with immutable received vintages."""
from datetime import datetime,timedelta,timezone
from pathlib import Path
from .market_sessions import zone
import hashlib,json,re,threading,time,urllib.request,urllib.error,unicodedata
from .candidate_data import canonical
from .demo_learning import atomic
from .lease import exclusive
from .news_policy import load_policy,selection

CONTRACT='V216_ECONOMIC_CALENDAR_V1'
URL='https://nfs.faireconomy.media/ff_calendar_thisweek.json'
TTL=3600


def label(value):
    text=unicodedata.normalize('NFKD',str(value)).encode('ascii','ignore').decode()
    return re.sub(r'[^A-Za-z0-9 _:/.-]',' ',text)[:80].strip() or 'ECONOMIC_EVENT'


def parse(raw,received):
    if len(raw)>2000000:raise ValueError('Calendar exceeds size limit')
    data=json.loads(raw)
    if not isinstance(data,list) or not 1<=len(data)<=5000:raise ValueError('Nonempty weekly event list required')
    events=[];days=[];seen=set()
    for item in data:
        if not isinstance(item,dict):raise ValueError('Calendar row must be an object')
        title=item.get('title');currency=item.get('country');impact=item.get('impact');date=item.get('date')
        if not all(isinstance(v,str) and v for v in (title,currency,impact,date)):raise ValueError('Missing calendar field')
        if currency not in ('USD','EUR','AUD','CAD','CHF','CNY','GBP','JPY','NZD','All'):raise ValueError('Unrecognized currency')
        if impact not in ('High','Medium','Low','Holiday'):raise ValueError('Unrecognized impact')
        dt=datetime.fromisoformat(date.replace('Z','+00:00'))
        if dt.tzinfo is None:raise ValueError('Calendar timezone missing')
        seconds=int(dt.timestamp());days.append(dt.astimezone(zone('America/New_York')).date())
        if currency not in ('EUR','USD'):continue
        key=hashlib.sha256((currency+'|'+title+'|'+dt.date().isoformat()).encode()).hexdigest()[:24]
        if key in seen:raise ValueError('Ambiguous duplicate calendar identity')
        seen.add(key)
        events.append(dict(event_id=key,title=title,label=label(title),currency=currency,impact=impact,scheduled_utc=seconds,
            time_uncertain=dt.hour==0 and dt.minute==0,forecast=str(item.get('forecast','')),previous=str(item.get('previous',''))))
    first=min(days);sunday=first-timedelta(days=(first.weekday()+1)%7)
    if any(not sunday<=d<sunday+timedelta(days=7) for d in days):raise ValueError('Weekly calendar crosses unexpected weeks')
    tz=zone('America/New_York');begin=int(datetime(sunday.year,sunday.month,sunday.day,tzinfo=tz).timestamp())
    d=sunday+timedelta(days=7);end=int(datetime(d.year,d.month,d.day,tzinfo=tz).timestamp())
    result=dict(schema=1,contract=CONTRACT,provider='FAIR_ECONOMY_PUBLIC_WEEKLY',source_url=URL,
        received_utc=int(received),expires_utc=int(received)+TTL,coverage_from_utc=begin,coverage_to_utc=end,
        source_event_count=len(data),scope_event_count=len(events),
        raw_sha256=hashlib.sha256(raw).hexdigest(),events=events,mode='OBSERVE_ONLY',
        coverage_basis='Weekly endpoint plus all returned dated rows; completeness is not independently guaranteed')
    result['payload_sha256']=hashlib.sha256(canonical(result)).hexdigest();return result


def state(snapshot,now,entry,expiry,policy=None):
    if snapshot is None:return dict(status='NEWS_UNKNOWN',event=None)
    if now<snapshot['received_utc']:return dict(status='NEWS_CLOCK_UNCERTAIN',event=None)
    if now>snapshot['expires_utc']:return dict(status='NEWS_STALE',event=None)
    if not snapshot['coverage_from_utc']<=entry<=expiry<snapshot['coverage_to_utc']:return dict(status='NEWS_UNKNOWN',event=None)
    selected=selection(snapshot,policy);relevant=[e for e in selected if e['tracked']]
    if not selected:return dict(status='NEWS_NO_RELEVANT_EVENTS',event=None)
    if not relevant:return dict(status='NEWS_NO_TRACKED_EVENTS',event=None)
    if any(e['time_uncertain'] for e in relevant):return dict(status='NEWS_TIME_UNCERTAIN',event=None)
    hits=[e for e in relevant if entry<=e['window_end'] and expiry>=e['window_start']]
    if hits:return dict(status='NEWS_RISK_WINDOW',event=min(hits,key=lambda e:abs(e['scheduled_utc']-entry)))
    future=[e for e in relevant if e['scheduled_utc']>=now]
    return dict(status='NEWS_CLEAR',event=min(future,key=lambda e:e['scheduled_utc']) if future else None)


def fetch(cache,now=None,opener=urllib.request.urlopen):
    supplied=now is not None
    cache=Path(cache);cache.mkdir(parents=True,exist_ok=True);now=int(time.time() if now is None else now)
    with exclusive(cache/'fetch.lock'):
        try:
            req=urllib.request.Request(URL,headers={'User-Agent':'ForexVPS-V222-PersonalResearch/1.0','Accept':'application/json'})
            with opener(req,timeout=10) as response:raw=response.read(2000001)
            if not supplied:now=int(time.time())
            snapshot=parse(raw,now)
            raw_path=cache/('raw_'+snapshot['raw_sha256']+'.json')
            if raw_path.exists():
                if hashlib.sha256(raw_path.read_bytes()).hexdigest()!=snapshot['raw_sha256']:raise ValueError('Raw calendar checksum differs')
            else:atomic(raw_path,raw)
            vintage=cache/('received_'+str(now)+'_'+snapshot['raw_sha256'][:16]+'.json')
            if not vintage.exists():atomic(vintage,canonical(snapshot))
            atomic(cache/'current.json',canonical(snapshot))
            status=dict(status='FETCH_OK',attempt_utc=now,raw_sha256=snapshot['raw_sha256'],mode='OBSERVE_ONLY')
        except (OSError,ValueError,TypeError,KeyError) as error:
            # No URL/query/header/body in error logs; never erase the last usable vintage.
            status=dict(status='FETCH_FAILED',attempt_utc=now,error_type=type(error).__name__,
                http_status=getattr(error,'code',None),mode='OBSERVE_ONLY')
        atomic(cache/'fetch_status.json',canonical(status));return status


def load(cache):
    path=Path(cache)/'current.json'
    if not path.is_file():return None
    data=json.loads(path.read_bytes())
    value=dict(data);digest=value.pop('payload_sha256',None)
    if digest!=hashlib.sha256(canonical(value)).hexdigest():raise ValueError('Calendar cache checksum differs')
    if data.get('contract')!=CONTRACT:raise ValueError('Calendar cache contract differs')
    # Cache is locally generated JSON; verify fields before any native publication.
    if len(data.get('events',[]))>5000 or data['expires_utc']-data['received_utc']!=TTL:raise ValueError('Invalid calendar cache')
    return data


class Worker:
    def __init__(self,cache):self.cache=Path(cache);self.stop=threading.Event();self.thread=None
    def start(self):
        def run():
            while not self.stop.is_set():
                try:fetch(self.cache)
                except (OSError,ValueError,RuntimeError):pass
                self.stop.wait(900)
        self.thread=threading.Thread(target=run,name='economic-calendar-observer',daemon=True);self.thread.start();return self
    def close(self):self.stop.set()
