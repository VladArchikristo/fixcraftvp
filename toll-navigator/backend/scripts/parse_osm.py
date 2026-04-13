#!/usr/bin/env python3
"""
OSM Overpass Parser — Toll Roads USA
Пробует несколько зеркал Overpass, делит США на 8 регионов.
Сохраняет результат в data/osm_tolls.json и вставляет в БД.
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
from typing import Optional

# ─── Config ────────────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, '..', 'data')
DB_PATH = os.path.join(DATA_DIR, 'toll_navigator.db')
OUTPUT_JSON = os.path.join(DATA_DIR, 'osm_tolls.json')

# Несколько зеркал Overpass
OVERPASS_MIRRORS = [
    'https://overpass-api.de/api/interpreter',
    'https://overpass.kumi.systems/api/interpreter',
    'https://maps.mail.ru/osm/tools/overpass/api/interpreter',
]

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
log = logging.getLogger('osm-parser')

# ─── State map ────────────────────────────────────────────────────────────────
STATE_ABBREV = {
    'alabama': 'AL', 'alaska': 'AK', 'arizona': 'AZ', 'arkansas': 'AR',
    'california': 'CA', 'colorado': 'CO', 'connecticut': 'CT', 'delaware': 'DE',
    'florida': 'FL', 'georgia': 'GA', 'hawaii': 'HI', 'idaho': 'ID',
    'illinois': 'IL', 'indiana': 'IN', 'iowa': 'IA', 'kansas': 'KS',
    'kentucky': 'KY', 'louisiana': 'LA', 'maine': 'ME', 'maryland': 'MD',
    'massachusetts': 'MA', 'michigan': 'MI', 'minnesota': 'MN', 'mississippi': 'MS',
    'missouri': 'MO', 'montana': 'MT', 'nebraska': 'NE', 'nevada': 'NV',
    'new hampshire': 'NH', 'new jersey': 'NJ', 'new mexico': 'NM', 'new york': 'NY',
    'north carolina': 'NC', 'north dakota': 'ND', 'ohio': 'OH', 'oklahoma': 'OK',
    'oregon': 'OR', 'pennsylvania': 'PA', 'rhode island': 'RI', 'south carolina': 'SC',
    'south dakota': 'SD', 'tennessee': 'TN', 'texas': 'TX', 'utah': 'UT',
    'vermont': 'VT', 'virginia': 'VA', 'washington': 'WA', 'west virginia': 'WV',
    'wisconsin': 'WI', 'wyoming': 'WY',
    # abbrevs pass-through
    'al': 'AL', 'ak': 'AK', 'az': 'AZ', 'ar': 'AR', 'ca': 'CA', 'co': 'CO',
    'ct': 'CT', 'de': 'DE', 'fl': 'FL', 'ga': 'GA', 'hi': 'HI', 'id': 'ID',
    'il': 'IL', 'in': 'IN', 'ia': 'IA', 'ks': 'KS', 'ky': 'KY', 'la': 'LA',
    'me': 'ME', 'md': 'MD', 'ma': 'MA', 'mi': 'MI', 'mn': 'MN', 'ms': 'MS',
    'mo': 'MO', 'mt': 'MT', 'ne': 'NE', 'nv': 'NV', 'nh': 'NH', 'nj': 'NJ',
    'nm': 'NM', 'ny': 'NY', 'nc': 'NC', 'nd': 'ND', 'oh': 'OH', 'ok': 'OK',
    'or': 'OR', 'pa': 'PA', 'ri': 'RI', 'sc': 'SC', 'sd': 'SD', 'tn': 'TN',
    'tx': 'TX', 'ut': 'UT', 'vt': 'VT', 'va': 'VA', 'wa': 'WA', 'wv': 'WV',
    'wi': 'WI', 'wy': 'WY',
}


def state_from_tags(tags: dict) -> str:
    for key in ('addr:state', 'is_in:state_code', 'is_in:state', 'state'):
        val = tags.get(key, '').strip()
        if val:
            abbrev = STATE_ABBREV.get(val.lower())
            if abbrev:
                return abbrev
            if len(val) == 2 and val.upper() in STATE_ABBREV.values():
                return val.upper()
    # Угадываем по ref
    ref = tags.get('ref', '')
    if ref and len(ref) >= 2:
        prefix = ref[:2].upper()
        if prefix in STATE_ABBREV.values():
            return prefix
    return 'US'


# ─── HTTP ─────────────────────────────────────────────────────────────────────

def post_overpass(query: str, timeout_sec: int = 120) -> Optional[dict]:
    """POST запрос к Overpass API — пробует несколько зеркал."""
    encoded_data = ('data=' + urllib.parse.quote(query)).encode('utf-8')
    for mirror in OVERPASS_MIRRORS:
        log.info(f'  Trying mirror: {mirror.split("/")[2]}')
        req = urllib.request.Request(
            mirror,
            data=encoded_data,
            headers={
                'Content-Type': 'application/x-www-form-urlencoded',
                'User-Agent': 'TollNavigator/1.0 (research)',
            }
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
                raw = resp.read().decode('utf-8')
                data = json.loads(raw)
                if 'elements' in data:
                    return data
        except urllib.error.HTTPError as e:
            log.warning(f'  HTTP {e.code} from {mirror}')
            if e.code == 429:
                time.sleep(10)
        except Exception as e:
            log.warning(f'  Error from {mirror}: {e}')
        time.sleep(3)
    return None


# ─── Parse ────────────────────────────────────────────────────────────────────

def parse_region(bounds: tuple, label: str) -> list:
    """Парсит один регион США, возвращает список дорог."""
    s, w, n, e = bounds
    query = (
        f'[out:json][timeout:90];'
        f'('
        f'  way["toll"="yes"]["highway"]({s},{w},{n},{e});'
        f'  relation["toll"="yes"]["route"="road"]({s},{w},{n},{e});'
        f');'
        f'out body;'
    )
    log.info(f'[{label}] Querying bounds ({s},{w} → {n},{e})')
    data = post_overpass(query, timeout_sec=120)

    if not data:
        log.warning(f'[{label}] No response, skipping')
        return []

    elements = data.get('elements', [])
    log.info(f'[{label}] Got {len(elements)} elements')

    results = []
    seen_ids = set()

    for el in elements:
        osm_id = el.get('id')
        if osm_id in seen_ids:
            continue
        seen_ids.add(osm_id)

        tags = el.get('tags', {})
        name = (
            tags.get('name') or
            tags.get('official_name') or
            tags.get('ref') or
            tags.get('alt_name') or
            ''
        ).strip()

        if not name:
            continue

        state = state_from_tags(tags)
        hwy = tags.get('highway', '')
        ref = tags.get('ref', '')

        if 'bridge' in tags.get('bridge', '') or 'tunnel' in tags.get('tunnel', ''):
            toll_type = 'bridge_tunnel'
        elif 'hov' in name.lower() or 'express' in name.lower():
            toll_type = 'express_lane'
        else:
            toll_type = 'toll_road'

        results.append({
            'name': name,
            'state': state,
            'highway_number': ref,
            'toll_type': toll_type,
            'source': 'OSM/Overpass',
        })

    return results


def deduplicate(records: list) -> list:
    seen = set()
    out = []
    for r in records:
        key = r['name'].lower().strip()
        if key not in seen:
            seen.add(key)
            out.append(r)
    return out


# ─── DB ───────────────────────────────────────────────────────────────────────

def insert_to_db(records: list) -> int:
    if not os.path.exists(DB_PATH):
        log.warning(f'DB not found at {DB_PATH}')
        return 0

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    inserted = 0
    for r in records:
        try:
            cur.execute(
                'INSERT OR IGNORE INTO tolls (road_name, state, cost_per_axle, min_cost) VALUES (?, ?, ?, ?)',
                (r['name'], r['state'], 0.0, 0.0)
            )
            if cur.rowcount > 0:
                inserted += 1
        except Exception as e:
            log.debug(f'DB insert error: {e}')
    conn.commit()
    conn.close()
    return inserted


def count_db() -> int:
    if not os.path.exists(DB_PATH):
        return 0
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('SELECT COUNT(*) FROM tolls')
    count = cur.fetchone()[0]
    conn.close()
    return count


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    log.info('=== OSM Toll Road Parser ===')
    os.makedirs(DATA_DIR, exist_ok=True)

    before_count = count_db()
    log.info(f'DB before: {before_count} roads')

    # США разбит на 8 регионов (меньше нагрузка на Overpass)
    regions = [
        # (south, west, north, east, label)
        (24.5, -125.0, 37.0, -110.0, 'SW1'),
        (24.5, -110.0, 37.0,  -95.0, 'SW2'),
        (24.5,  -95.0, 37.0,  -80.5, 'SE1'),
        (24.5,  -80.5, 37.0,  -66.5, 'SE2'),
        (37.0, -125.0, 49.5, -110.0, 'NW1'),
        (37.0, -110.0, 49.5,  -95.0, 'NW2'),
        (37.0,  -95.0, 49.5,  -80.5, 'NE1'),
        (37.0,  -80.5, 49.5,  -66.5, 'NE2'),
    ]

    all_records = []
    region_stats = {}

    for s, w, n, e, label in regions:
        records = parse_region((s, w, n, e), label)
        region_stats[label] = len(records)
        all_records.extend(records)
        log.info(f'[{label}] Accumulated: {len(all_records)} total')
        time.sleep(5)  # rate limit

    # Дедупликация
    unique = deduplicate(all_records)
    log.info(f'After dedup: {len(unique)} unique roads (was {len(all_records)})')

    # Сохраняем JSON
    output = {
        'meta': {
            'total': len(unique),
            'regions': region_stats,
        },
        'records': unique,
    }
    with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    log.info(f'Saved: {OUTPUT_JSON}')

    # Вставляем в БД
    inserted = insert_to_db(unique)
    after_count = count_db()

    # Итог
    print('\n' + '='*50)
    print('OSM PARSE RESULTS')
    print('='*50)
    print(f'Regions processed: {len(regions)}')
    print(f'Raw OSM ways:      {len(all_records)}')
    print(f'Unique roads:      {len(unique)}')
    print(f'New in DB:         {inserted}')
    print(f'DB before:         {before_count}')
    print(f'DB after:          {after_count}')
    print('='*50)

    # Топ штаты
    from collections import Counter
    state_counts = Counter(r['state'] for r in unique)
    print('\nTop 10 states:')
    for state, cnt in state_counts.most_common(10):
        print(f'  {state}: {cnt}')

    return 0


if __name__ == '__main__':
    sys.exit(main())
