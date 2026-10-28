"""One-shot public news-feed health check. Does not modify an EA journal."""
import argparse,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from intelligence.economic_calendar import fetch,load,state
from intelligence.news_review import write as review


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--cache',type=Path,default=ROOT/'candidate_research/news_check');a=p.parse_args()
    status=fetch(a.cache);now=int(time.time());calendar=load(a.cache)
    details=review(a.cache,a.cache,now)
    print(json.dumps(dict(fetch=status,calendar=details['calendar_state'],tracked_events=details['tracked_events'],scope_events=details['scope_event_count'],policy=details['policy']['contract'],review=str(a.cache/'news_source_review_v222.json'),mode='OBSERVE_ONLY'),indent=2))
    return 0 if status['status']=='FETCH_OK' else 1


if __name__=='__main__':
    try:raise SystemExit(main())
    except (OSError,ValueError,KeyError,TypeError) as error:
        print('NEWS_UNKNOWN: '+type(error).__name__,file=sys.stderr);raise SystemExit(1)
