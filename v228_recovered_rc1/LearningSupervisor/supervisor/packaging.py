import json
from pathlib import Path
import zipfile

def export_review(output):
    output=Path(output)
    # SQLite backup is consistent even with WAL; never copy a live DB file raw.
    import sqlite3
    source=sqlite3.connect(output/'supervisor.sqlite');backup=output/'review_database.sqlite'
    target=sqlite3.connect(backup)
    try:source.backup(target)
    finally:target.close();source.close()
    destination=output/'V224_Supervisor_Review.zip'
    files=[p for p in output.rglob('*') if p.is_file() and
        (p.suffix in ('.json','.html') or p==backup) and '.writer-lock' not in p.parts]
    with zipfile.ZipFile(destination.with_suffix('.zip.tmp'),'w',zipfile.ZIP_DEFLATED) as z:
        for path in sorted(files):z.write(path,path.relative_to(output))
    destination.with_suffix('.zip.tmp').replace(destination)
    return destination
