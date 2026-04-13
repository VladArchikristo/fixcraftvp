#!/usr/bin/env python3
"""
OSM Overpass Parser v2 — Toll Roads USA
- 12 subregions (NE1 split into 4 parts to fix timeout)
- Accepts road_name from name OR ref tag
- Inserts into backend/data/toll_navigator.db
- Skips duplicates via UNIQUE(road_name, state)
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
OUTPUT_JSON = os.path.join(DATA_DIR, 'osm_tolls_v2.json')

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
log = logging.getLogger('osm-v2')

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

STATE_ABBREV_SET = set(STATE_ABBREV.values())


def state_from_tags(tags: dict) -> str:
    for key in ('addr:state', 'is_in:state_code', 'is_in:state', 'state'):
        val = tags.get(key, '').strip()
        if val:
            abbrev = STATE_ABBREV.get(val.lower())
            if abbrev:
                return abbrev
            if len(val) == 2 and val.upper() in STATE_ABBREV_SET:
                return val.upper()
    ref = tags.get('ref', '')
    if ref:
        parts = ref.split()
        for p in parts:
            if len(p) == 2 and p.upper() in STATE_ABBREV_SET:
                return p.upper()
    return 'US'


def post_overpass(query: str, timeout_sec: int = 90) -> Optional[dict]:
    encoded_data = ('data=' + urllib.parse.quote(query)).encode('utf-8')
    for mirror in OVERPASS_MIRRORS:
        host = mirror.split('/')[2]
        log.info(f'  Mirror: {host}')
        req = urllib.request.Request(
            mirror,
            data=encoded_data,
            headers={
                'Content-Type': 'application/x-www-form-urlencoded',
                'User-Agent': 'TollNavigator/2.0 (research; contact=research@example.com)',
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
                log.info('  Rate limited, sleeping 15s...')
                time.sleep(15)
            elif e.code == 504:
                log.warning('  Gateway timeout, trying next mirror')
        except Exception as e:
            log.warning(f'  Error from {host}: {type(e).__name__}: {e}')
        time.sleep(4)
    return None


def parse_region(bounds: tuple, label: str) -> list:
    s, w, n, e = bounds
    # Query both ways and relations
    query = (
        f'[out:json][timeout:90];'
        f'('
        f'  way["toll"="yes"]["highway"]({s},{w},{n},{e});'
        f'  relation["toll"="yes"]["route"="road"]({s},{w},{n},{e});'
        f'  relation["toll"="yes"]["route"="ferry"]({s},{w},{n},{e});'
        f');'
        f'out body;'
    )
    log.info(f'[{label}] Querying ({s},{w}) → ({n},{e})')
    data = post_overpass(query, timeout_sec=90)

    if not data:
        log.warning(f'[{label}] No response from any mirror')
        return []

    elements = data.get('elements', [])
    log.info(f'[{label}] Raw elements: {len(elements)}')

    results = []
    seen_ids = set()

    for el in elements:
        osm_id = el.get('id')
        if osm_id in seen_ids:
            continue
        seen_ids.add(osm_id)

        tags = el.get('tags', {})

        # Accept name OR ref as road_name
        name = (
            tags.get('name') or
            tags.get('official_name') or
            tags.get('alt_name') or
            ''
        ).strip()

        ref = tags.get('ref', '').strip()

        # If no name, use ref as name (e.g. "I 95", "SR 408")
        if not name and ref:
            name = ref

        if not name:
            continue

        state = state_from_tags(tags)
        hwy = tags.get('highway', '')

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
            'state': state,
            'highway_number': ref,
            'toll_type': toll_type,
            'source': 'OSM/Overpass',
        })

    log.info(f'[{label}] Named records: {len(results)}')
    return results


def deduplicate(records: list) -> list:
    seen = set()
    out = []
    for r in records:
        # Dedup by (name_lower, state)
        key = (r['name'].lower().strip(), r['state'])
        if key not in seen:
            seen.add(key)
            out.append(r)
    return out


def get_db_schema(conn):
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(tolls)")
    return {row[1] for row in cur.fetchall()}


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


def count_db() -> int:
    if not os.path.exists(DB_PATH):
        return 0
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('SELECT COUNT(*) FROM tolls')
    count = cur.fetchone()[0]
    conn.close()
    return count


def main():
    log.info('=== OSM Toll Road Parser v2 ===')
    os.makedirs(DATA_DIR, exist_ok=True)

    before = count_db()
    log.info(f'DB before: {before} roads')

    # 12 regions — former NE1 (midwest) split into 4 smaller boxes
    # to avoid Overpass timeout on dense OH/PA/NY/NJ area
    regions = [
        # SW quadrant
        (24.5, -125.0, 37.0, -110.0, 'SW1-CalNev'),
        (24.5, -110.0, 37.0,  -95.0, 'SW2-AZNMTx'),
        # SE quadrant
        (24.5,  -95.0, 37.0,  -80.5, 'SE1-FLGAAl'),
        (24.5,  -80.5, 37.0,  -66.5, 'SE2-NCVAMd'),
        # NW quadrant
        (37.0, -125.0, 49.5, -110.0, 'NW1-PacNW'),
        (37.0, -110.0, 49.5,  -95.0, 'NW2-MtWy'),
        # NE quadrant — split into 4 to avoid timeout
        # NE1a: Indiana, Ohio, Michigan, Kentucky (west half)
        (37.0,  -89.5, 45.5,  -80.5, 'NE1a-OhIn'),
        # NE1b: Minnesota, Wisconsin, Illinois (north half)
        (41.0,  -97.0, 49.5,  -89.5, 'NE1b-MnWi'),
        # NE1c: Iowa, Missouri, Kansas, Nebraska (plains)
        (35.5,  -97.0, 43.5,  -91.0, 'NE1c-IaMo'),
        # NE1d: Tennessee, North Carolina (south)
        (34.5,  -91.0, 37.5,  -80.5, 'NE1d-TnNc'),
        # NE2 — NY, NJ, PA, New England (very dense — split)
        (38.0,  -80.5, 43.0,  -71.0, 'NE2a-NyNjPa'),
        (41.5,  -74.0, 49.5,  -66.5, 'NE2b-NewEng'),
    ]

    all_records = []
    region_stats = {}

    for s, w, n, e, label in regions:
        records = parse_region((s, w, n, e), label)
        region_stats[label] = len(records)
        all_records.extend(records)
        log.info(f'Running total: {len(all_records)} raw records')
        time.sleep(6)  # polite pause between regions

    # Deduplicate by (name, state)
    unique = deduplicate(all_records)
    log.info(f'Dedup: {len(all_records)} raw → {len(unique)} unique')

    # Save JSON
    output = {
        'meta': {'total': len(unique), 'raw': len(all_records), 'regions': region_stats},
        'records': unique,
    }
    with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    log.info(f'Saved JSON: {OUTPUT_JSON}')

    # Insert to DB
    inserted = insert_to_db(unique)
    after = count_db()

    print('\n' + '=' * 55)
    print('OSM PARSE v2 RESULTS')
    print('=' * 55)
    print(f'Regions processed:  {len(regions)}')
    print(f'Raw OSM elements:   {len(all_records)}')
    print(f'Unique roads:       {len(unique)}')
    print(f'New inserted in DB: {inserted}')
    print(f'DB before:          {before}')
    print(f'DB after:           {after}')
    print(f'Net gain:           +{after - before}')
    print('=' * 55)
    print('\nRegion breakdown:')
    for label, cnt in region_stats.items():
        print(f'  {label:<18} {cnt} elements')

    state_counts = Counter(r['state'] for r in unique)
    print('\nTop 15 states:')
    for state, cnt in state_counts.most_common(15):
        print(f'  {state}: {cnt}')

    return 0


if __name__ == '__main__':
    sys.exit(main())
