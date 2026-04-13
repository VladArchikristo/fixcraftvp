#!/usr/bin/env python3
"""
AGENT MEDIUM — Wikipedia Toll Roads Scraper
Парсит страницы Wikipedia "List of toll roads in [State]"
+ запросы через Wikipedia API для поиска дополнительных страниц
Результат сохраняет в toll_navigator.db
"""

import json
import logging
import os
import re
import sqlite3
import time
import urllib.error
import urllib.request
import urllib.parse
from typing import Optional

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, '..', 'data')
DB_PATH = os.path.join(DATA_DIR, 'toll_navigator.db')
LOG_FILE = os.path.join(DATA_DIR, 'agent_medium.log')
PROGRESS_FILE = os.path.join(DATA_DIR, 'agent_medium_progress.json')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [MEDIUM-AGENT] %(message)s',
    datefmt='%H:%M:%S',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_FILE)
    ]
)
log = logging.getLogger('medium-agent')

US_STATES = [
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
    ('Wisconsin', 'WI'), ('Wyoming', 'WY'),
]

# Wikipedia page titles to try for each state
WIKI_PAGE_TEMPLATES = [
    "List_of_toll_roads_in_{state}",
    "Toll_roads_in_{state}",
    "Transportation_in_{state}",
    "List_of_toll_highways_in_{state}",
    "{state}_Turnpike",
]

# Known toll authorities with Wikipedia pages
AUTHORITY_PAGES = [
    ("New_York_State_Thruway", "NY"),
    ("New_Jersey_Turnpike", "NJ"),
    ("Pennsylvania_Turnpike", "PA"),
    ("Florida_Turnpike", "FL"),
    ("Ohio_Turnpike", "OH"),
    ("Indiana_Toll_Road", "IN"),
    ("Illinois_Tollway", "IL"),
    ("Kansas_Turnpike", "KS"),
    ("Oklahoma_Turnpike_Authority", "OK"),
    ("Colorado_E-470", "CO"),
    ("Harris_County_Toll_Road_Authority", "TX"),
    ("North_Carolina_Turnpike_Authority", "NC"),
    ("Virginia_Department_of_Transportation", "VA"),
    ("Maryland_Transportation_Authority", "MD"),
    ("Massachusetts_Turnpike", "MA"),
    ("New_Hampshire_Turnpike_System", "NH"),
    ("Maine_Turnpike", "ME"),
    ("Georgia_State_Road_and_Tollway_Authority", "GA"),
    ("Dallas_North_Tollway", "TX"),
    ("Sam_Houston_Tollway", "TX"),
    ("Dulles_Toll_Road", "VA"),
    ("Garden_State_Parkway", "NJ"),
    ("Atlantic_City_Expressway", "NJ"),
    ("Blue_Water_Bridge", "MI"),
    ("Mackinac_Bridge", "MI"),
    ("Bay_Area_Toll_Authority", "CA"),
    ("Orange_County_Transportation_Authority", "CA"),
]


def fetch_url(url: str, timeout: int = 30) -> Optional[str]:
    headers = {'User-Agent': 'TollNavigator/1.0 (toll road data collection; contact@tollnavigator.com)'}
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode('utf-8', errors='replace')
    except Exception as e:
        log.debug(f"Fetch failed {url}: {e}")
        return None


def fetch_wikipedia_page(title: str) -> Optional[dict]:
    """Fetch Wikipedia page content via API"""
    url = f"https://en.wikipedia.org/w/api.php?action=query&titles={urllib.parse.quote(title)}&prop=revisions&rvprop=content&format=json&formatversion=2"
    data = fetch_url(url)
    if not data:
        return None
    try:
        obj = json.loads(data)
        pages = obj.get('query', {}).get('pages', [])
        if not pages or pages[0].get('missing'):
            return None
        return pages[0]
    except Exception:
        return None


def extract_roads_from_wikitext(text: str, state: str, source_label: str) -> list[dict]:
    """Extract toll road names from Wikipedia wikitext"""
    roads = []
    seen = set()

    # Pattern: [[Road Name]] or [[Road Name|Display]] or * Road Name
    patterns = [
        r'\[\[([^\|\]]+(?:Turnpike|Expressway|Parkway|Freeway|Highway|Toll|Bridge|Tunnel|Road|Thruway|Bypass)[^\|\]]*)\]\]',
        r'\[\[([^\|\]]+)\|([^\]]+(?:Turnpike|Expressway|Parkway|Freeway|Toll|Bridge|Tunnel|Thruway)[^\]]*)\]\]',
        r'\*\s+(?:\[\[)?([A-Z][^|\]\n]+(?:Turnpike|Expressway|Parkway|Freeway|Toll Road|Bridge|Tunnel|Thruway|Bypass))(?:\|[^\]]*)?\]?\]?',
    ]

    for pattern in patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            name = match.group(1).strip()
            # Clean up
            name = re.sub(r'\(.*?\)', '', name).strip()
            name = re.sub(r'\s+', ' ', name)
            if len(name) < 5 or len(name) > 100:
                continue
            key = name.lower()
            if key in seen:
                continue
            seen.add(key)
            roads.append({
                'road_name': name,
                'state': state,
                'source': f'Wikipedia/{source_label}',
                'toll_type': 'toll_road',
                'highway_number': ''
            })

    return roads


def init_db(db_path: str):
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
            (r['road_name'], r.get('state',''), r.get('highway_number',''), r.get('toll_type','toll_road'), r.get('source','Wikipedia'))
        )
        count += 1
    conn.commit()
    return count


def load_progress() -> dict:
    try:
        with open(PROGRESS_FILE) as f:
            return json.load(f)
    except Exception:
        return {'done_states': [], 'done_pages': []}


def save_progress(progress: dict):
    with open(PROGRESS_FILE, 'w') as f:
        json.dump(progress, f)


def main():
    log.info("=== MEDIUM AGENT STARTED ===")
    conn = init_db(DB_PATH)
    existing = get_existing(conn)
    log.info(f"Existing records: {len(existing)}")

    progress = load_progress()
    done_states = set(progress.get('done_states', []))
    done_pages = set(progress.get('done_pages', []))

    total_added = 0

    # Phase 1: State list pages
    log.info("--- Phase 1: State Wikipedia pages ---")
    for state_name, state_code in US_STATES:
        if state_code in done_states:
            continue

        state_added = 0
        for template in WIKI_PAGE_TEMPLATES:
            page_title = template.format(state=state_name.replace(' ', '_'))
            if page_title in done_pages:
                continue

            page = fetch_wikipedia_page(page_title)
            if not page:
                done_pages.add(page_title)
                continue

            content = page.get('revisions', [{}])[0].get('content', '')
            if not content:
                done_pages.add(page_title)
                continue

            roads = extract_roads_from_wikitext(content, state_code, f"{state_name}")
            added = insert_roads(conn, roads, existing)
            state_added += added
            total_added += added
            done_pages.add(page_title)

            if added > 0:
                log.info(f"  {state_code} [{page_title}]: +{added} roads")

            time.sleep(1)

        done_states.add(state_code)
        save_progress({'done_states': list(done_states), 'done_pages': list(done_pages)})

    # Phase 2: Authority pages
    log.info("--- Phase 2: Toll authority pages ---")
    for page_title, state_code in AUTHORITY_PAGES:
        if page_title in done_pages:
            continue

        page = fetch_wikipedia_page(page_title)
        if not page:
            done_pages.add(page_title)
            time.sleep(0.5)
            continue

        content = page.get('revisions', [{}])[0].get('content', '')
        roads = extract_roads_from_wikitext(content, state_code, page_title.replace('_', ' '))

        # Also add the authority itself as a road entry if it looks like a road
        authority_name = page_title.replace('_', ' ')
        if any(kw in authority_name for kw in ['Turnpike', 'Expressway', 'Parkway', 'Thruway', 'Tollway', 'Road']):
            roads.append({
                'road_name': authority_name,
                'state': state_code,
                'source': f'Wikipedia/Authority',
                'toll_type': 'toll_road',
                'highway_number': ''
            })

        added = insert_roads(conn, roads, existing)
        total_added += added
        done_pages.add(page_title)

        if added > 0:
            log.info(f"  Authority [{page_title}]: +{added} roads")

        save_progress({'done_states': list(done_states), 'done_pages': list(done_pages)})
        time.sleep(1)

    # Phase 3: Wikipedia "List of toll roads in the United States" sub-pages
    log.info("--- Phase 3: US master pages ---")
    us_pages = [
        ("List_of_toll_roads_in_the_United_States", "US"),
        ("List_of_express_lanes_in_the_United_States", "US"),
        ("List_of_toll_bridges_in_the_United_States", "US"),
        ("List_of_toll_tunnels_in_the_United_States", "US"),
        ("Eastern_toll_roads_in_the_United_States", "US"),
        ("Western_toll_roads_in_the_United_States", "US"),
    ]
    for page_title, state_code in us_pages:
        if page_title in done_pages:
            continue
        page = fetch_wikipedia_page(page_title)
        if not page:
            done_pages.add(page_title)
            time.sleep(0.5)
            continue
        content = page.get('revisions', [{}])[0].get('content', '')
        roads = extract_roads_from_wikitext(content, state_code, page_title.replace('_', ' '))
        added = insert_roads(conn, roads, existing)
        total_added += added
        done_pages.add(page_title)
        if added > 0:
            log.info(f"  US page [{page_title}]: +{added} roads")
        save_progress({'done_states': list(done_states), 'done_pages': list(done_pages)})
        time.sleep(1)

    conn.close()

    # Final count
    conn2 = sqlite3.connect(DB_PATH)
    total = conn2.execute("SELECT COUNT(*) FROM tolls").fetchone()[0]
    conn2.close()

    log.info(f"=== MEDIUM AGENT DONE === Added: {total_added} | Total in DB: {total}")
    print(f"\n✅ MEDIUM AGENT COMPLETE\nNew roads added: {total_added}\nTotal in DB: {total}")


if __name__ == '__main__':
    main()
