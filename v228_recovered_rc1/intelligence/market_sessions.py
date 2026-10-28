"""Versioned observation windows; never a trading eligibility rule."""
from datetime import datetime,time,timedelta,timezone
from zoneinfo import ZoneInfo
from importlib.resources import files
from functools import lru_cache
import tzdata

CONTRACT='V217_SESSION_CONTEXT_V2'
TIMEZONE_DATABASE='tzdata-'+tzdata.__version__


@lru_cache(maxsize=8)
def zone(name):
    # Use the same pinned database on Windows and Linux, independent of OS TZPATH.
    with files('tzdata.zoneinfo').joinpath(*name.split('/')).open('rb') as stream:
        return ZoneInfo.from_file(stream,key=name)
# Explicit research conventions, not exchange opening hours or a liquidity guarantee.
WINDOWS=(('TOKYO','Asia/Tokyo',9,18),('SYDNEY','Australia/Sydney',8,17),
         ('LONDON','Europe/London',8,17),('NEW_YORK','America/New_York',8,17))


def windows(start_utc,days=3):
    result=[]
    for name,zone_name,begin,end in WINDOWS:
        tz=zone(zone_name);day=datetime.fromtimestamp(start_utc,timezone.utc).astimezone(tz).date()
        for offset in range(-1,days+1):
            d=day+timedelta(days=offset)
            if d.weekday()>=5:continue
            left=datetime.combine(d,time(begin),tz).timestamp();right=datetime.combine(d,time(end),tz).timestamp()
            result.append(dict(name=name,start=int(left),end=int(right),timezone=zone_name))
    return sorted(result,key=lambda r:(r['start'],r['name']))


def classify(utc_seconds):
    if utc_seconds is None:return dict(session='SESSION_UNKNOWN',centres=[],mask=0)
    centres=[name for name,zone_name,begin,end in WINDOWS if (lambda d:d.weekday()<5 and begin<=d.hour<end)(datetime.fromtimestamp(utc_seconds,timezone.utc).astimezone(zone(zone_name)))]
    mask=(1 if 'TOKYO' in centres or 'SYDNEY' in centres else 0)|(2 if 'LONDON' in centres else 0)|(4 if 'NEW_YORK' in centres else 0)
    return dict(session={0:'OFF_WINDOW',1:'ASIA',2:'LONDON',3:'ASIA_LONDON',4:'NEW_YORK',5:'ASIA_NEW_YORK',6:'LONDON_NEW_YORK',7:'ASIA_LONDON_NEW_YORK'}[mask],centres=centres,mask=mask)


def episode(utc_seconds,entry_utc,expiry_utc):
    now=classify(utc_seconds);entry=classify(entry_utc);expiry=classify(expiry_utc)
    return dict(session=now['session'],centres=now['centres'],entry_session=entry['session'],expiry_session=expiry['session'],
        crosses_session_boundary=entry['session']!=expiry['session'] if entry_utc is not None else None)
