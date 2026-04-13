#!/usr/bin/env python3
"""
Toll Navigator — Import parsed tolls JSON into SQLite
Читает backend/data/parsed_tolls.json и database/seed-tolls.js
Импортирует всё в toll_navigator.db
"""

import json
import os
import re
import sqlite3
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.join(SCRIPT_DIR, '..', '..')
DB_PATH = os.path.join(ROOT_DIR, 'toll_navigator.db')
JSON_PATH = os.path.join(SCRIPT_DIR, '..', 'data', 'parsed_tolls.json')
SEED_JS = os.path.join(ROOT_DIR, 'database', 'seed-tolls.js')


def ensure_schema(conn):
    conn.execute('''
        CREATE TABLE IF NOT EXISTS tolls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            road_name TEXT NOT NULL,
            state TEXT NOT NULL,
            highway_number TEXT DEFAULT "",
            toll_type TEXT DEFAULT "toll_road",
            length_miles REAL DEFAULT 0.0,
            rate_per_mile_car REAL DEFAULT 0.0,
            rate_per_mile_5axle REAL DEFAULT 0.0,
            direction TEXT DEFAULT "both",
            cost_per_axle REAL DEFAULT 0.0,
            min_cost REAL DEFAULT 0.0,
            source TEXT DEFAULT "",
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(road_name, state)
        )
    ''')
    conn.commit()
    print(f'[schema] Table tolls OK in {DB_PATH}')


def load_seed_records():
    """Parse seed-tolls.js to extract road objects."""
    records = []
    if not os.path.exists(SEED_JS):
        print(f'[seed] File not found: {SEED_JS}')
        return records

    with open(SEED_JS, 'r', encoding='utf-8') as f:
        content = f.read()

    # Extract JS object blocks like { road_name: '...', state: '...', ... }
    # Simple regex-based extraction
    obj_pattern = re.compile(r'\{([^{}]+)\}', re.DOTALL)
    kv_pattern = re.compile(r'(\w+)\s*:\s*[\'"]([^\'"]*)[\'"]')
    num_pattern = re.compile(r'(\w+)\s*:\s*([\d.]+)')

    for obj_match in obj_pattern.finditer(content):
        obj_str = obj_match.group(1)
        kv = {}
        for k, v in kv_pattern.findall(obj_str):
            kv[k] = v
        for k, v in num_pattern.findall(obj_str):
            if k not in kv:
                try:
                    kv[k] = float(v)
                except ValueError:
                    pass

        road_name = kv.get('road_name', '').strip()
        state = kv.get('state', '').strip()
        if road_name and state:
            records.append({
                'road_name': road_name,
                'state': state.upper()[:2],
                'highway_number': str(kv.get('highway_number', '')),
                'toll_type': str(kv.get('toll_type', 'toll_road')),
                'length_miles': float(kv.get('length_miles', 0) or 0),
                'rate_per_mile_car': float(kv.get('rate_per_mile_car', 0) or 0),
                'rate_per_mile_5axle': float(kv.get('rate_per_mile_5axle', 0) or 0),
                'direction': str(kv.get('direction', 'both')),
                'cost_per_axle': float(kv.get('cost_per_axle', 0) or 0),
                'min_cost': float(kv.get('min_cost', 0) or 0),
                'source': 'seed-tolls.js',
            })
    print(f'[seed] Loaded {len(records)} records from seed-tolls.js')
    return records


def load_parsed_records():
    """Load records from parsed_tolls.json."""
    if not os.path.exists(JSON_PATH):
        print(f'[parsed] File not found: {JSON_PATH}')
        return []

    with open(JSON_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)

    raw = data.get('records', [])
    records = []
    for r in raw:
        records.append({
            'road_name': r.get('name', '').strip(),
            'state': r.get('state', '').upper()[:2],
            'highway_number': r.get('highway_number', ''),
            'toll_type': r.get('toll_type', 'toll_road'),
            'length_miles': float(r.get('length_miles', 0) or 0),
            'rate_per_mile_car': float(r.get('rate_per_mile_car', 0) or 0),
            'rate_per_mile_5axle': float(r.get('rate_per_mile_5axle', 0) or 0),
            'direction': r.get('direction', 'both'),
            'cost_per_axle': float(r.get('rate_per_mile_car', 0) or 0),
            'min_cost': 0.0,
            'source': r.get('source', ''),
        })
    print(f'[parsed] Loaded {len(records)} records from parsed_tolls.json')
    return records


def insert_records(conn, records, batch_name):
    inserted = 0
    skipped = 0
    for r in records:
        if not r['road_name'] or not r['state']:
            skipped += 1
            continue
        try:
            conn.execute('''
                INSERT OR IGNORE INTO tolls
                (road_name, state, highway_number, toll_type, length_miles,
                 rate_per_mile_car, rate_per_mile_5axle, direction,
                 cost_per_axle, min_cost, source)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
            ''', (
                r['road_name'], r['state'], r.get('highway_number',''),
                r.get('toll_type','toll_road'), r.get('length_miles',0),
                r.get('rate_per_mile_car',0), r.get('rate_per_mile_5axle',0),
                r.get('direction','both'), r.get('cost_per_axle',0),
                r.get('min_cost',0), r.get('source',''),
            ))
            if conn.execute('SELECT changes()').fetchone()[0] > 0:
                inserted += 1
            else:
                skipped += 1
        except Exception as e:
            print(f'  ERROR inserting {r["road_name"]}: {e}')
            skipped += 1
    conn.commit()
    print(f'[{batch_name}] Inserted: {inserted}, Skipped/dupes: {skipped}')
    return inserted


def main():
    print('=== Toll Navigator — SQLite Import ===')
    print(f'DB: {DB_PATH}')

    conn = sqlite3.connect(DB_PATH)
    ensure_schema(conn)

    # 1. Seed records
    seed_records = load_seed_records()
    seed_inserted = insert_records(conn, seed_records, 'seed')

    # 2. Parsed records
    parsed_records = load_parsed_records()
    parsed_inserted = insert_records(conn, parsed_records, 'parsed')

    # 3. Final count
    total = conn.execute('SELECT COUNT(*) FROM tolls').fetchone()[0]
    by_state = conn.execute(
        'SELECT state, COUNT(*) as cnt FROM tolls GROUP BY state ORDER BY cnt DESC LIMIT 15'
    ).fetchall()
    by_source = conn.execute(
        'SELECT source, COUNT(*) as cnt FROM tolls GROUP BY source ORDER BY cnt DESC'
    ).fetchall()

    conn.close()

    print()
    print('=' * 55)
    print('FINAL RESULTS')
    print('=' * 55)
    print(f'Seed inserted:    {seed_inserted}')
    print(f'Parsed inserted:  {parsed_inserted}')
    print(f'TOTAL IN DB:      {total}')
    print()
    print('Top states:')
    for state, cnt in by_state:
        print(f'  {state:4s}  {cnt}')
    print()
    print('By source:')
    for src, cnt in by_source:
        print(f'  {src:<35s}  {cnt}')
    print('=' * 55)

    return 0


if __name__ == '__main__':
    sys.exit(main())
