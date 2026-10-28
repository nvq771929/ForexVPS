"""Explicit observation policy. Preserve provider impact; no native trade gate."""
from pathlib import Path
import hashlib,json,re,unicodedata
from .candidate_data import canonical
CONTRACT='V222_NEWS_TRACKING_V1'
DEFAULT_PATH=Path(__file__).resolve().parents[1]/'news_policy_v222.json'

def normalized_title(value):
    text=unicodedata.normalize('NFKD',value).encode('ascii','ignore').decode().casefold()
    return ' '.join(re.findall(r'[a-z0-9]+',text))

def load_policy(path=None):
    value=json.loads(Path(path or DEFAULT_PATH).read_bytes())
    if set(value)!={'schema','contract','mode','impacts','priority_events'} or value['schema']!=1 or value['contract']!=CONTRACT or value['mode']!='OBSERVE_ONLY':
        raise ValueError('Unsupported news policy')
    impacts=value['impacts'];priority=value['priority_events']
    if not isinstance(impacts,dict) or set(impacts)!={'High','Medium'} or not isinstance(priority,list) or len(priority)>100:
        raise ValueError('Invalid news impact/watchlist policy')
    def window(row,keys):
        if not isinstance(row,dict) or set(row)!=keys:raise ValueError('Invalid news window fields')
        for k in ('before_minutes','after_minutes'):
            if type(row[k]) is not int or not 0<=row[k]<=120:raise ValueError('News window must be 0..120 minutes')
        if row['before_minutes']+row['after_minutes']==0:raise ValueError('Empty news window')
    for row in impacts.values():window(row,{'before_minutes','after_minutes'})
    seen=set()
    for row in priority:
        window(row,{'currency','title','before_minutes','after_minutes'})
        if row['currency'] not in ('EUR','USD') or not isinstance(row['title'],str) or not normalized_title(row['title']):raise ValueError('Invalid priority event identity')
        key=(row['currency'],normalized_title(row['title']))
        if key in seen:raise ValueError('Duplicate priority event')
        seen.add(key)
    return dict(value,policy_sha256=hashlib.sha256(canonical(value)).hexdigest())

def track(event,policy):
    """Exact normalized title/currency matching; never fuse country/region events."""
    if event['currency'] not in ('EUR','USD'):return dict(tracked=False,reason='CURRENCY_OUT_OF_SCOPE')
    if event['impact']=='Holiday':return dict(tracked=False,reason='HOLIDAY_NOT_RELEASE')
    window=policy['impacts'].get(event['impact']);reason='IMPACT_'+event['impact'].upper() if window else 'IMPACT_OUT_OF_POLICY'
    for row in policy['priority_events']:
        if event['currency']==row['currency'] and normalized_title(event['title'])==normalized_title(row['title']):
            if window:window=dict(before_minutes=max(window['before_minutes'],row['before_minutes']),after_minutes=max(window['after_minutes'],row['after_minutes']))
            else:window=row
            reason='PRIORITY_EVENT';break
    if window is None:return dict(tracked=False,reason=reason)
    return dict(tracked=True,reason=reason,before_seconds=window['before_minutes']*60,after_seconds=window['after_minutes']*60)

def selection(snapshot,policy=None):
    policy=policy or load_policy();rows=[]
    for e in snapshot['events'] if snapshot else []:
        result=track(e,policy)
        rows.append(dict(e,**result,provider_impact=e['impact'],window_start=e['scheduled_utc']-result.get('before_seconds',0),window_end=e['scheduled_utc']+result.get('after_seconds',0)))
    return rows
