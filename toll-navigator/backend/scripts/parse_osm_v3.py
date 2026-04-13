#!/usr/bin/env python3
"""
OSM Overpass Parser v3 — Toll Roads USA
- Обход по 50 штатам через area-запросы
- 4 зеркала Overpass API с ротацией
- Прогресс-файл (можно продолжить при прерывании)
- timeout=120 сек, пауза 10 сек между штатами
- Дедупликация по (road_name, state)
"""

import json
import logging
import os
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from typing import Optional

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, '..', 'data')
DB_PATH = os.path.join(DATA_DIR, 'toll_navigator.db')
OUTPUT_JSON = os.path.join(DATA_DIR, 'osm_tolls_v3.json')
PROGRESS_FILE = os.path.join(DATA_DIR, 'osm_v3_progress.json')

OVERPASS_MIRRORS = [
    'https://overpass-api.de/api/interpreter',
    'https://overpass.kumi.systems/api/interpreter',
    'https://maps.mail.ru/osm/tools/overpass/api/interpreter',
    'https://overpass.openstreetmap.ru/api/interpreter',
]

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
log = logging.getLogger('osm-v3')

US_STATES = [
    ('Alabama', 'AL'),
    ('Alaska', 'AK'),
    ('Arizona', 'AZ'),
    ('Arkansas', 'AR'),
    ('California', 'CA'),
    ('Colorado', 'CO'),
    ('Connecticut', 'CT'),
    ('Delaware', 'DE'),
    ('Florida', 'FL'),
    ('Georgia', 'GA'),
    ('Hawaii', 'HI'),
    ('Idaho', 'ID'),
    ('Illinois', 'IL'),
    ('Indiana', 'IN'),
    ('Iowa', 'IA'),
    ('Kansas', 'KS'),
    ('Kentucky', 'KY'),
    ('Louisiana', 'LA'),
    ('Maine', 'ME'),
    ('Maryland', 'MD'),
    ('Massachusetts', 'MA'),
    ('Michigan', 'MI'),
    ('Minnesota', 'MN'),
    ('Mississippi', 'MS'),
    ('Missouri', 'MO'),
    ('Montana', 'MT'),
    ('Nebraska', 'NE'),
    ('Nevada', 'NV'),
    ('New Hampshire', 'NH'),
    ('New Jersey', 'NJ'),
    ('New Mexico', 'NM'),
    ('New York', 'NY'),
    ('North Carolina', 'NC'),
    ('North Dakota', 'ND'),
    ('Ohio', 'OH'),
    ('Oklahoma', 'OK'),
    ('Oregon', 'OR'),
    ('Pennsylvania', 'PA'),
    ('Rhode Island', 'RI'),
    ('South Carolina', 'SC'),
    ('South Dakota', 'SD'),
    ('Tennessee', 'TN'),
    ('Texas', 'TX'),
    ('Utah', 'UT'),
    ('Vermont', 'VT'),
    ('Virginia', 'VA'),
    ('Washington', 'WA'),
    ('West Virginia', 'WV'),
    ('Wisconsin', 'WI'),
    ('Wyoming', 'WY'),
]

STATE_ABBREV = {s.lower(): a for s, a in US_STATES}
STATE_ABBREV.update({a.lower(): a for _, a in US_STATES})
STATE_ABBREV_SET = set(a for _, a in US_STATES)


def state_from_tags(tags: dict, default_state: str) -> str:
    for key in ('addr:state', 'is_in:state_code', 'is_in:state', 'state'):
        val = tags.get(key, '').strip()
        if val:
            abbrev = STATE_ABBREV.get(val.lower())
            if abbrev:
                return abbrev
            if len(val) == 2 and val.upper() in STATE_ABBREV_SET:
                return val.upper()
    return default_state


def post_overpass(query: str, timeout_sec: int = 120) -> Optional[dict]:
    encoded_data = ('data=' + urllib.parse.quote(query)).encode('utf-8')
    for i, mirror in enumerate(OVERPASS_MIRRORS):
        host = mirror.split('/')[2]
        log.info(f'  [{i+1}/{len(OVERPASS_MIRRORS)}] Mirror: {host}')
        req = urllib.request.Request(
            mirror,
            data=encoded_data,
            headers={
                'Content-Type': 'application/x-www-form-urlencoded',
                'User-Agent': 'TollNavigator/3.0 (research; contact=research@example.com)',
            }
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
                raw = resp.read().decode('utf-8')
                data = json.loads(raw)
                if 'elements' in data:
                    log.info(f'  OK from {host}: {len(data["elements"])} elements')
                    return data
        except urllib.error.HTTPError as e:
            log.warning(f'  HTTP {e.code} from {host}')
            if e.code == 429:
                log.info('  Rate limited, sleeping 20s...')
                time.sleep(20)
            elif e.code in (504, 502, 503):
                log.warning(f'  Server error {e.code}, switching mirror immediately')
        except Exception as e:
            log.warning(f'  Error from {host}: {type(e).__name__}: {str(e)[:120]}')
        # Небольшая пауза перед следующим зеркалом
        if i < len(OVERPASS_MIRRORS) - 1:
            time.sleep(3)
    return None


def build_state_query(state_name: str) -> str:
    """Overpass area-запрос для конкретного штата."""
    return (
        f'[out:json][timeout:90];'
        f'area["name"="{state_name}"]["admin_level"="4"]->.searchArea;'
        f'('
        f'  way["toll"="yes"](area.searchArea);'
        f'  way["barrier"="toll_booth"](area.searchArea);'
        f'  relation["toll"="yes"](area.searchArea);'
        f');'
        f'out body;'
        f'>;'
        f'out skel qt;'
    )


def parse_state(state_name: str, state_abbrev: str) -> list:
    query = build_state_query(state_name)
    log.info(f'[{state_abbrev}] Querying {state_name}...')
    data = post_overpass(query, timeout_sec=120)

    if not data:
        log.warning(f'[{state_abbrev}] No response from any mirror — skipping')
        return []

    elements = data.get('elements', [])
    log.info(f'[{state_abbrev}] Raw elements: {len(elements)}')

    results = []
    seen_ids = set()

    for el in elements:
        osm_id = el.get('id')
        if osm_id in seen_ids:
            continue
        seen_ids.add(osm_id)

        el_type = el.get('type', '')
        tags = el.get('tags', {})

        # Toll booth nodes — пропускаем, нас интересуют дороги
        if el_type == 'node':
            continue

        # Имя дороги: name > official_name > alt_name > ref
        name = (
            tags.get('name') or
            tags.get('official_name') or
            tags.get('alt_name') or
            ''
        ).strip()

        ref = tags.get('ref', '').strip()

        if not name and ref:
            name = ref

        if not name:
            # Для toll_booth без имени — пропускаем
            if tags.get('barrier') == 'toll_booth':
                continue
            continue

        actual_state = state_from_tags(tags, state_abbrev)

        bridge = tags.get('bridge', '')
        tunnel = tags.get('tunnel', '')
        if bridge and bridge != 'no':
            toll_type = 'bridge_tunnel'
        elif tunnel and tunnel != 'no':
            toll_type = 'bridge_tunnel'
        elif 'hov' in name.lower() or 'express' in name.lower() or tags.get('hov') == 'yes':
            toll_type = 'express_lane'
        else:
            toll_type = 'toll_road'

        results.append({
            'name': name,
            'state': actual_state,
            'highway_number': ref,
            'toll_type': toll_type,
            'source': 'osm_overpass_v3',
        })

    log.info(f'[{state_abbrev}] Named records: {len(results)}')
    return results


def deduplicate(records: list) -> list:
    seen = set()
    out = []
    for r in records:
        key = (r['name'].lower().strip(), r['state'])
        if key not in seen:
            seen.add(key)
            out.append(r)
    return out


def get_db_schema(conn):
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(tolls)")
    return {row[1] for row in cur.fetchall()}


def count_db() -> int:
    if not os.path.exists(DB_PATH):
        return 0
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('SELECT COUNT(*) FROM tolls')
    count = cur.fetchone()[0]
    conn.close()
    return count


def get_existing_keys() -> set:
    """Загрузить все (road_name_lower, state) из БД для дедупликации."""
    if not os.path.exists(DB_PATH):
        return set()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('SELECT road_name, state FROM tolls')
    keys = {(r[0].lower().strip(), r[1]) for r in cur.fetchall()}
    conn.close()
    return keys


def insert_to_db(records: list) -> int:
    if not os.path.exists(DB_PATH):
        log.error(f'DB not found: {DB_PATH}')
        return 0

    conn = sqlite3.connect(DB_PATH)
    cols = get_db_schema(conn)
    cur = conn.cursor()
    inserted = 0

    for r in records:
        try:
            if 'highway_number' in cols and 'toll_type' in cols and 'source' in cols:
                cur.execute(
                    '''INSERT OR IGNORE INTO tolls
                       (road_name, state, highway_number, toll_type, source)
                       VALUES (?, ?, ?, ?, ?)''',
                    (r['name'], r['state'], r['highway_number'], r['toll_type'], r['source'])
                )
            else:
                cur.execute(
                    'INSERT OR IGNORE INTO tolls (road_name, state) VALUES (?, ?)',
                    (r['name'], r['state'])
                )
            if cur.rowcount > 0:
                inserted += 1
        except Exception as e:
            log.debug(f'DB error: {e} for {r["name"]}')

    conn.commit()
    conn.close()
    return inserted


def load_progress() -> dict:
    if os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {'done_states': [], 'records': []}


def save_progress(done_states: list, records: list):
    with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
        json.dump({'done_states': done_states, 'records': records}, f, ensure_ascii=False)


def main():
    log.info('=== OSM Toll Road Parser v3 ===')
    os.makedirs(DATA_DIR, exist_ok=True)

    before = count_db()
    log.info(f'DB before: {before} roads')

    # Загружаем прогресс (для продолжения при прерывании)
    progress = load_progress()
    done_states = set(progress.get('done_states', []))
    all_records = progress.get('records', [])

    if done_states:
        log.info(f'Resuming: {len(done_states)} states already done, {len(all_records)} records loaded')

    state_stats = {}
    consecutive_errors = {}

    for state_name, state_abbrev in US_STATES:
        if state_abbrev in done_states:
            log.info(f'[{state_abbrev}] Already done — skipping')
            continue

        err_count = consecutive_errors.get(state_abbrev, 0)
        if err_count >= 3:
            log.warning(f'[{state_abbrev}] 3 errors — skipping state')
            done_states.add(state_abbrev)
            state_stats[state_abbrev] = 0
            save_progress(list(done_states), all_records)
            continue

        try:
            records = parse_state(state_name, state_abbrev)
            state_stats[state_abbrev] = len(records)
            all_records.extend(records)
            done_states.add(state_abbrev)
            consecutive_errors[state_abbrev] = 0

            log.info(f'[{state_abbrev}] Done: {len(records)} roads | Running total: {len(all_records)}')
            save_progress(list(done_states), all_records)

        except Exception as e:
            log.error(f'[{state_abbrev}] Exception: {e}')
            consecutive_errors[state_abbrev] = consecutive_errors.get(state_abbrev, 0) + 1

        # Пауза между штатами — серверы перегружены
        time.sleep(10)

    # Глобальная дедупликация
    unique = deduplicate(all_records)
    log.info(f'Dedup: {len(all_records)} raw → {len(unique)} unique')

    # Сохраняем JSON
    output = {
        'meta': {
            'total': len(unique),
            'raw': len(all_records),
            'states': state_stats,
        },
        'records': unique,
    }
    with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    log.info(f'Saved JSON: {OUTPUT_JSON}')

    # Вставка в БД
    inserted = insert_to_db(unique)
    after = count_db()

    # Чистим прогресс-файл
    if os.path.exists(PROGRESS_FILE):
        os.remove(PROGRESS_FILE)

    print('\n' + '=' * 55)
    print('OSM PARSE v3 RESULTS')
    print('=' * 55)
    print(f'States processed:   {len(done_states)}/50')
    print(f'Raw OSM elements:   {len(all_records)}')
    print(f'Unique roads:       {len(unique)}')
    print(f'New inserted in DB: {inserted}')
    print(f'DB before:          {before}')
    print(f'DB after:           {after}')
    print(f'Net gain:           +{after - before}')
    print('=' * 55)
    print('\nState breakdown:')
    for abbrev, cnt in sorted(state_stats.items()):
        if cnt > 0:
            print(f'  {abbrev}: {cnt}')

    state_counts = Counter(r['state'] for r in unique)
    print('\nTop 15 states:')
    for state, cnt in state_counts.most_common(15):
        print(f'  {state}: {cnt}')

    return 0


if __name__ == '__main__':
    sys.exit(main())
