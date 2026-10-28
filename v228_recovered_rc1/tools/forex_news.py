"""Keep the V2.24 Forex scheduled-news bridge current. No trading or training."""
import argparse,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from intelligence.economic_calendar import fetch
from intelligence.forex_news import publish
from intelligence.lease import exclusive

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data-folder',type=Path);p.add_argument('--once',action='store_true');a=p.parse_args()
    folder=a.data_folder or Path(input('Paste MT4 Data Folder: ').strip().strip('"'))
    if not (folder/'MQL4'/'Files').is_dir():p.error('Expected an existing MT4 Data Folder with MQL4/Files')
    files=folder/'MQL4'/'Files';cache=files/'FX_V222'/'news_cache'
    (files/'FX_V222').mkdir(parents=True,exist_ok=True)
    with exclusive(files/'FX_V222'/'news_worker.lock'):
        due=0
        while True:
            now=int(time.time())
            if now>=due:
                status=fetch(cache);print('Forex news fetch | '+json.dumps(status),flush=True)
                due=now+(900 if status['status']=='FETCH_OK' else 60)
            try: print('Forex news bridge | '+json.dumps(publish(cache,files,now)),flush=True)
            except (OSError,ValueError,KeyError,TypeError) as error:
                print('NEWS_UNKNOWN | '+type(error).__name__,flush=True)
            if a.once:return 0
            time.sleep(30)

if __name__=='__main__':
    try:raise SystemExit(main())
    except KeyboardInterrupt:print('Forex news bridge stopped; EA freshness gate remains active.')
    except (OSError,ValueError,RuntimeError) as error:
        print(type(error).__name__+': '+str(error),file=sys.stderr);raise SystemExit(1)
