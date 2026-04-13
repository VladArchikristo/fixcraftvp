#!/usr/bin/env python3
"""
AGENT OSM RETRY — Overpass API Toll Roads (резюме)
Продолжает парсинг с того места где остановился v3
Оставшиеся штаты: те что не в osm_v3_progress.json
Новые данные сохраняет в toll_navigator.db
"""

import json
import logging
import os
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Optional

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, '..', 'data')
DB_PATH = os.path.join(DATA_DIR, 'toll_navigator.db')
LOG_FILE = os.path.join(DATA_DIR, 'agent_osm_retry.log')
PROGRESS_FILE = os.path.join(DATA_DIR, 'agent_osm_retry_progress.json')
OLD_PROGRESS_FILE = os.path.join(DATA_DIR, 'osm_v3_progress.json')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [OSM-RETRY] %(message)s',
    datefmt='%H:%M:%S',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_FILE)
    ]
)
log = logging.getLogger('osm-retry')

OVERPASS_MIRRORS = [
    'https://overpass-api.de/api/interpreter',
    'https://overpass.kumi.systems/api/interpreter',
    'https://maps.mail.ru/osm/tools/overpass/api/interpreter',
    'https://overpass.openstreetmap.ru/api/interpreter',
    'https://lz4.overpass-api.de/api/interpreter',
]

ALL_STATES = [
    ('Alabama', 'AL'), ('Alaska', 'AK'), ('Arizona', 'AZ'), ('Arkansas', 'AR'),
    ('California', 'CA'), ('Colorado', 'CO'), ('Connecticut', 'CT'), ('Delaware', 'DE'),
    ('Florida', 'FL'), ('Georgia', 'GA'), ('Hawaii', 'HI'), ('Idaho', 'ID'),
    ('Illinois', 'IL'), ('Indiana', 'IN'), ('Iowa', 'IA'), ('Kansas', 'KS'),
    ('Kentucky', 'KY'), ('Louisiana', 'LA'), ('Maine', 'ME'), ('Maryland', 'MD'),
    ('Massachusetts', 'MA'), ('Michigan', 'MI'), ('Minnesota', 'MN'), ('Mississippi', 'MS'),
    ('Missouri', 'MO'), ('Montana', 'MT'), ('Nebraska', 'NE'), ('Nevada', 'NV'),
    ('New Hampshire', 'NH'), ('New Jersey', 'NJ'), ('New Mexico', 'NM'), ('New York', 'NY'),
    ('North Carolina', 'NC'), ('North Dakota', 'ND'), ('Ohio', 'OH'), ('Oklahoma', 'OK'),
    ('Oregon', 'OR'), ('Pennsylvania', 'PA'), ('Rhode Island', 'RI'), ('South Carolina', 'SC'),
    ('South Dakota', 'SD'), ('Tennessee', 'TN'), ('Texas', 'TX'), ('Utah', 'UT'),
    ('Vermont', 'VT'), ('Virginia', 'VA'), ('Washington', 'WA'), ('West Virginia', 'WV'),
    ('Wisconsin', 'WI'), ('Wyoming', 'WY'), ('Puerto Rico', 'PR'), ('Washington DC', 'DC'),
]


def build_query(state_name: str) -> str:
    """Build Overpass QL query for toll roads in a US state"""
    quoted = state_name.replace("'", "\\'")
    return f"""
[out:json][timeout:120];
area["name"="{quoted}"]["admin_level"~"^(4|5)$"]->.searchArea;
(
  way["highway"]["toll"="yes"](area.searchArea);
  way["highway"]["charge"](area.searchArea);
  relation["highway"]["toll"="yes"](area.searchArea);
  relation["route"="road"]["toll"="yes"](area.searchArea);
  node["barrier"="toll_booth"](area.searchArea);
);
out tags;
"""


def fetch_overpass(query: str, mirror_idx: int = 0) -> Optional[dict]:
    mirror = OVERPASS_MIRRORS[mirror_idx % len(OVERPASS_MIRRORS)]
    data = urllib.parse.urlencode({'data': query}).encode()
    headers = {'User-Agent': 'TollNavigator/1.0 (toll road research)'}
    try:
        req = urllib.request.Request(mirror, data=data, headers=headers, method='POST')
        with urllib.request.urlopen(req, timeout=130) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        log.warning(f"HTTP {e.code} from {mirror}")
        return None
    except Exception as e:
        log.warning(f"Error from {mirror}: {type(e).__name__}: {e}")
        return None


def parse_osm_elements(elements: list, state_code: str) -> list[dict]:
    roads = []
    seen = set()

    for el in elements:
        tags = el.get('tags', {})

        # Get road name
        name = (
            tags.get('name') or
            tags.get('official_name') or
            tags.get('ref') or
            tags.get('short_name') or
            ''
        ).strip()

        if not name or len(name) < 3:
            continue

        # Filter out generic names
        if name.lower() in {'road', 'highway', 'street', 'avenue', 'boulevard', 'drive', 'way'}:
            continue

        key = f"{name.lower()}|{state_code.lower()}"
        if key in seen:
            continue
        seen.add(key)

        highway_type = tags.get('highway', tags.get('route', ''))
        ref = tags.get('ref', '')
        toll_type = tags.get('barrier', 'toll_road')
        if toll_type == 'toll_booth':
            toll_type = 'toll_booth'

        roads.append({
            'road_name': name,
            'state': state_code,
            'highway_number': ref,
            'toll_type': toll_type,
            'source': 'OSM/Overpass-Retry'
        })

    return roads


def init_db(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tolls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            road_name TEXT NOT NULL,
            state TEXT,
            highway_number TEXT,
            toll_type TEXT DEFAULT 'toll_road',
            source TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_name_state ON tolls(road_name, state)")
    conn.commit()
    return conn


def get_existing(conn) -> set:
    cur = conn.execute("SELECT LOWER(road_name) || '|' || LOWER(COALESCE(state,'')) FROM tolls")
    return set(r[0] for r in cur.fetchall())


def insert_roads(conn, roads: list[dict], existing: set) -> int:
    count = 0
    for r in roads:
        key = f"{r['road_name'].lower()}|{r.get('state','').lower()}"
        if key in existing:
            continue
        existing.add(key)
        conn.execute(
            "INSERT INTO tolls (road_name, state, highway_number, toll_type, source) VALUES (?,?,?,?,?)",
            (r['road_name'], r.get('state', ''), r.get('highway_number', ''), r.get('toll_type', 'toll_road'), r.get('source', 'OSM'))
        )
        count += 1
    conn.commit()
    return count


def load_progress() -> set:
    """Load previously completed states from both old and new progress files"""
    done = set()
    for pf in [OLD_PROGRESS_FILE, PROGRESS_FILE]:
        try:
            with open(pf) as f:
                data = json.load(f)
                if isinstance(data, dict):
                    done.update(data.get('done_states', []))
        except Exception:
            pass
    return done


def save_progress(done_states: set):
    with open(PROGRESS_FILE, 'w') as f:
        json.dump({'done_states': list(done_states)}, f)


def main():
    log.info("=== OSM RETRY AGENT STARTED ===")

    conn = init_db(DB_PATH)
    existing = get_existing(conn)
    log.info(f"Existing records: {len(existing)}")

    already_done = load_progress()
    remaining = [(name, code) for name, code in ALL_STATES if code not in already_done]
    log.info(f"States to process: {len(remaining)} (skipping {len(already_done)} already done)")

    done_states = set(already_done)
    total_added = 0
    mirror_idx = 0
    consecutive_errors = 0

    for i, (state_name, state_code) in enumerate(remaining):
        log.info(f"[{i+1}/{len(remaining)}] Processing {state_name} ({state_code})...")

        query = build_query(state_name)
        result = None

        # Try each mirror up to 3 times total
        for attempt in range(3):
            result = fetch_overpass(query, mirror_idx + attempt)
            if result:
                break
            log.warning(f"  Attempt {attempt+1}/3 failed, trying next mirror...")
            time.sleep(5)

        if not result:
            log.error(f"  All mirrors failed for {state_name}, skipping")
            consecutive_errors += 1
            if consecutive_errors >= 3:
                log.error("3 consecutive errors — pausing 60 seconds")
                time.sleep(60)
                consecutive_errors = 0
            mirror_idx = (mirror_idx + 1) % len(OVERPASS_MIRRORS)
            # Still mark as done to avoid infinite retry
            done_states.add(state_code)
            save_progress(done_states)
            continue

        consecutive_errors = 0
        elements = result.get('elements', [])
        log.info(f"  Got {len(elements)} elements from OSM")

        roads = parse_osm_elements(elements, state_code)
        added = insert_roads(conn, roads, existing)
        total_added += added

        log.info(f"  {state_name}: {len(roads)} unique roads → +{added} new in DB")

        done_states.add(state_code)
        save_progress(done_states)

        # Rotate mirrors periodically
        mirror_idx = (mirror_idx + 1) % len(OVERPASS_MIRRORS)

        # Pause to avoid overloading
        pause = 8 if i % 5 != 4 else 15
        time.sleep(pause)

    conn.close()

    # Final stats
    conn2 = sqlite3.connect(DB_PATH)
    total = conn2.execute("SELECT COUNT(*) FROM tolls").fetchone()[0]
    osm_count = conn2.execute("SELECT COUNT(*) FROM tolls WHERE source LIKE 'OSM%'").fetchone()[0]
    conn2.close()

    log.info(f"=== OSM RETRY DONE === New: {total_added} | OSM total: {osm_count} | DB total: {total}")
    print(f"\n✅ OSM RETRY AGENT COMPLETE")
    print(f"New roads added: {total_added}")
    print(f"OSM total: {osm_count}")
    print(f"Total in DB: {total}")


if __name__ == '__main__':
    main()
