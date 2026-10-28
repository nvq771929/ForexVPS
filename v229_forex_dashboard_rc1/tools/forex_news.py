"""Keep the dedicated Forex news bridge current. Accept MT4 or live Forex folders."""
import argparse,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from intelligence.economic_calendar import fetch
from intelligence.forex_news import publish
from intelligence.lease import exclusive

def resolve_files_directory(folder):
    """Recognize explicit MT4 layouts; never guess an unrelated parent folder."""
    selected=Path(folder).expanduser().resolve()
    if not selected.is_dir():
        raise ValueError('Path must be an existing folder, not a CSV file')
    if (selected/'MQL4'/'Files').is_dir():
        return selected/'MQL4'/'Files'
    if selected.name.casefold()=='mql4' and (selected/'Files').is_dir():
        return selected/'Files'
    if selected.name.casefold()=='files' and selected.parent.name.casefold()=='mql4':
        return selected
    if selected.name.casefold()=='fx_v222':
        files=selected.parent
    elif selected.parent.name.casefold()=='fx_v222' and selected.name.upper().startswith('LIVE_') and (selected/'forex_session.csv').is_file():
        files=selected.parent.parent
    else:
        raise ValueError('Choose MT4 Data Folder (File > Open Data Folder), MQL4/Files, FX_V222, or its LIVE_* Forex folder')
    if files.name.casefold()!='files' or files.parent.name.casefold()!='mql4':
        raise ValueError('Forex folder must be inside the MT4 layout MQL4/Files/FX_V222')
    return files

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data-folder',type=Path,help='MT4 Data Folder, MQL4/Files, FX_V222, or its LIVE_* folder')
    p.add_argument('--once',action='store_true');a=p.parse_args()
    if a.data_folder is None:
        raw=input('Dan MT4 Data Folder hoac folder Forex FX_V222/LIVE_*: ').strip().strip('"')
        if not raw:p.error('A folder path is required')
        folder=Path(raw)
    else:folder=a.data_folder
    try:files=resolve_files_directory(folder)
    except ValueError as error:p.error(str(error))
    print('MT4 Data Folder: '+str(files.parent.parent),flush=True)
    print('Lich tin Forex: '+str(files/'FX_V222'/'news_calendar.csv'),flush=True)
    cache=files/'FX_V222'/'news_cache'
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
