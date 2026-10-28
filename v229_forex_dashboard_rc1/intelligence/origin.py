"""Run-origin separation is mandatory: tester outcomes cannot qualify live models."""
import csv
from pathlib import Path


def read_origin(source,policy):
    with (Path(source)/'data_origin.csv').open(encoding='utf-8-sig',newline='') as stream:
        reader=csv.DictReader(stream);rows=list(reader)
        if reader.fieldnames!=['schema','logic','kind','config_hash','feed_hash'] or len(rows)!=1:
            raise ValueError('Missing or invalid V207 data origin')
    row=rows[0]
    if int(row['schema'])!=1 or any(int(row[k])!=policy[k] for k in ('logic','config_hash','feed_hash')):
        raise ValueError('Data origin differs from policy')
    if row['kind'] not in ('LIVE_MT4','BACKTEST_MT4'):raise ValueError('Unsupported data origin')
    return row['kind']
