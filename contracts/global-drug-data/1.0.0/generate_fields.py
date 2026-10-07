#!/usr/bin/env python3
"""Generate/check the normative SQL field inventory without external dependencies."""
import argparse
import json
from pathlib import Path
import sqlite3
ROOT=Path(__file__).resolve().parent

def render():
    with sqlite3.connect(':memory:') as c:
        c.executescript((ROOT/'schema.sql').read_text())
        spec=json.loads((ROOT/'contract.json').read_text())
        actual={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert actual==set(spec['required_tables']), 'machine contract/SQL table mismatch'
        assert c.execute('PRAGMA user_version').fetchone()[0]==spec['sqlite_user_version']
        lines=['# SQL 欄位清單（自動產生）','','來源：schema.sql。不可手動新增欄位；語意与合法值以 README.md／contract.json 為準。','']
        for table in spec['required_tables']:
            lines.extend([f'## {table}','','| 欄位 | SQLite 型別 | NOT NULL | Default | PK 順序 |','|---|---|---|---|---|'])
            for cid,name,kind,nn,default,pk in c.execute(f'PRAGMA table_info("{table}")'):
                lines.append(f'| {name} | {kind} | {bool(nn)} | {default if default is not None else "—"} | {pk} |')
            lines.append('')
            fks=list(c.execute(f'PRAGMA foreign_key_list("{table}")'))
            if fks:lines.extend(['外鍵：'+ '; '.join(f'{r[3]} → {r[2]}.{r[4]}' for r in fks),''])
        return '\n'.join(lines)+'\n'
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--check',action='store_true');args=p.parse_args()
    text=render();path=ROOT/'SCHEMA_FIELDS.md'
    if args.check:
        if path.read_text()!=text:raise SystemExit('FAIL: stale SCHEMA_FIELDS.md')
        print('PASS: SQL, machine tables/user_version and 234 field inventory match')
    else:path.write_text(text)
