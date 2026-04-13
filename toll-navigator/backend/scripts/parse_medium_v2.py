#!/usr/bin/env python3
"""
MEDIUM Parser v2 — Wikipedia + AARoads toll road data
- Wikipedia "List of toll roads in [State]" pages
- AARoads.com state toll road lists
- Сохраняет в toll_navigator.db
"""

import json
import logging
import os
import re
import sqlite3
import time
import urllib.error
import urllib.request
from html.parser import HTMLParser

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, '..', 'data')
DB_PATH = os.path.join(DATA_DIR, 'toll_navigator.db')
OUTPUT_JSON = os.path.join(DATA_DIR, 'medium_v2_results.json')
PROGRESS_FILE = os.path.join(DATA_DIR, 'medium_v2_progress.json')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [MEDIUM] %(message)s',
    datefmt='%H:%M:%S',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(DATA_DIR, 'medium_v2.log'))
    ]
)
log = logging.getLogger('medium-v2')

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

# Wikipedia toll road pages that are known to exist
WIKI_PAGES = [
    ('https://en.wikipedia.org/wiki/List_of_toll_roads_in_the_United_States', 'ALL'),
    ('https://en.wikipedia.org/wiki/List_of_toll_roads_in_California', 'CA'),
    ('https://en.wikipedia.org/wiki/List_of_toll_roads_in_Florida', 'FL'),
    ('https://en.wikipedia.org/wiki/List_of_toll_roads_in_Texas', 'TX'),
    ('https://en.wikipedia.org/wiki/List_of_toll_roads_in_New_York', 'NY'),
    ('https://en.wikipedia.org/wiki/List_of_toll_roads_in_New_Jersey', 'NJ'),
    ('https://en.wikipedia.org/wiki/List_of_toll_roads_in_Pennsylvania', 'PA'),
    ('https://en.wikipedia.org/wiki/List_of_toll_roads_in_Virginia', 'VA'),
    ('https://en.wikipedia.org/wiki/List_of_toll_roads_in_Illinois', 'IL'),
    ('https://en.wikipedia.org/wiki/List_of_toll_roads_in_Ohio', 'OH'),
    ('https://en.wikipedia.org/wiki/List_of_toll_roads_in_Massachusetts', 'MA'),
    ('https://en.wikipedia.org/wiki/List_of_toll_roads_in_Colorado', 'CO'),
    ('https://en.wikipedia.org/wiki/List_of_toll_roads_in_Georgia', 'GA'),
    ('https://en.wikipedia.org/wiki/List_of_toll_roads_in_North_Carolina', 'NC'),
    ('https://en.wikipedia.org/wiki/List_of_toll_roads_in_Indiana', 'IN'),
    ('https://en.wikipedia.org/wiki/List_of_toll_roads_in_Oklahoma', 'OK'),
    ('https://en.wikipedia.org/wiki/List_of_toll_roads_in_Kansas', 'KS'),
    ('https://en.wikipedia.org/wiki/List_of_toll_roads_in_Maryland', 'MD'),
    ('https://en.wikipedia.org/wiki/List_of_toll_roads_in_Delaware', 'DE'),
    ('https://en.wikipedia.org/wiki/List_of_toll_roads_in_Maine', 'ME'),
    ('https://en.wikipedia.org/wiki/List_of_toll_roads_in_New_Hampshire', 'NH'),
    ('https://en.wikipedia.org/wiki/List_of_toll_roads_in_West_Virginia', 'WV'),
    ('https://en.wikipedia.org/wiki/List_of_toll_roads_in_Kentucky', 'KY'),
    ('https://en.wikipedia.org/wiki/List_of_toll_roads_in_Alabama', 'AL'),
    ('https://en.wikipedia.org/wiki/List_of_toll_roads_in_Louisiana', 'LA'),
    ('https://en.wikipedia.org/wiki/List_of_toll_roads_in_Minnesota', 'MN'),
    ('https://en.wikipedia.org/wiki/List_of_toll_roads_in_Washington', 'WA'),
    ('https://en.wikipedia.org/wiki/Toll_roads_in_the_United_States', 'ALL'),
]

# Wikipedia API endpoint for searching
WIKI_API = 'https://en.wikipedia.org/w/api.php'


def fetch_url(url: str, timeout: int = 30) -> str | None:
    headers = {
        'User-Agent': 'TollNavigator/1.0 (data research; contact@example.com)',
        'Accept': 'text/html,application/xhtml+xml',
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode('utf-8', errors='replace')
    except Exception as e:
        log.warning(f"Fetch failed {url}: {e}")
        return None


def fetch_wiki_api(state_name: str) -> list[dict]:
    """Use Wikipedia API to search for toll road info"""
    results = []

    # Search for state toll road article
    search_url = (
        f"{WIKI_API}?action=query&list=search"
        f"&srsearch=toll+roads+{urllib.parse.quote(state_name)}"
        f"&srnamespace=0&srlimit=5&format=json"
    )

    html = fetch_url(search_url)
    if not html:
        return results

    try:
        data = json.loads(html)
        hits = data.get('query', {}).get('search', [])
        for hit in hits:
            title = hit.get('title', '')
            snippet = hit.get('snippet', '')
            # Extract road names from snippet
            if 'toll' in title.lower() or 'turnpike' in title.lower() or 'expressway' in title.lower():
                results.append({
                    'name': title,
                    'state': '',
                    'source': 'wikipedia_api'
                })
    except Exception as e:
        log.warning(f"Wiki API parse error for {state_name}: {e}")

    return results


def extract_road_names_from_html(html: str, state_code: str) -> list[dict]:
    """Extract toll road names from Wikipedia HTML"""
    roads = []

    # Pattern: find table rows with road names
    # Look for links that contain road keywords
    road_keywords = ['turnpike', 'expressway', 'parkway', 'toll', 'bridge', 'tunnel',
                     'highway', 'interstate', 'thruway', 'freeway', 'bypass']

    # Find all anchor tags
    link_pattern = re.compile(r'<a[^>]*href="/wiki/([^"]+)"[^>]*>([^<]+)</a>', re.IGNORECASE)

    seen = set()
    for match in link_pattern.finditer(html):
        href, name = match.group(1), match.group(2)
        name = name.strip()
        name_lower = name.lower()

        # Skip short names, navigation links, etc.
        if len(name) < 5 or name in seen:
            continue
        if any(skip in name_lower for skip in ['edit', 'help', 'talk', 'special:', 'wikipedia']):
            continue

        # Check if it looks like a road
        if any(kw in name_lower for kw in road_keywords):
            seen.add(name)
            roads.append({
                'name': name,
                'state': state_code,
                'source': 'wikipedia_html'
            })

    # Also look for list items
    li_pattern = re.compile(r'<li[^>]*>.*?<b>([^<]{5,60}(?:toll|turnpike|expressway|parkway|bridge|tunnel|thruway)[^<]{0,40})</b>', re.IGNORECASE)
    for match in li_pattern.finditer(html):
        name = match.group(1).strip()
        if name not in seen and len(name) > 5:
            seen.add(name)
            roads.append({
                'name': name,
                'state': state_code,
                'source': 'wikipedia_bold'
            })

    return roads


def parse_main_wiki_page() -> list[dict]:
    """Parse the main US toll roads Wikipedia page"""
    url = 'https://en.wikipedia.org/wiki/Toll_roads_in_the_United_States'
    log.info(f"Fetching main Wiki page: {url}")

    html = fetch_url(url)
    if not html:
        log.warning("Could not fetch main Wikipedia page")
        return []

    roads = []
    seen = set()

    # State code mapping
    state_map = {name: code for name, code in US_STATES}

    # Find state sections and road names within them
    state_section_pattern = re.compile(
        r'<h[23][^>]*>.*?(' + '|'.join(name for name, _ in US_STATES) + r').*?</h[23]>',
        re.IGNORECASE
    )

    # Split by state sections
    sections = re.split(r'<h[23]', html)
    current_state = 'ALL'

    for section in sections:
        # Detect state
        for state_name, state_code in US_STATES:
            if state_name.lower() in section[:200].lower():
                current_state = state_code
                break

        # Extract road names
        road_pattern = re.compile(
            r'>([^<]{5,80}(?:Turnpike|Expressway|Parkway|Toll Road|Bridge|Tunnel|'
            r'Thruway|Freeway|Highway|Bypass|Beltway|Causeway)[^<]{0,40})<',
            re.IGNORECASE
        )

        for match in road_pattern.finditer(section):
            name = match.group(1).strip()
            # Clean HTML entities
            name = re.sub(r'&[a-z]+;', ' ', name).strip()
            name = re.sub(r'\s+', ' ', name)

            if name and name not in seen and 5 <= len(name) <= 100:
                seen.add(name)
                roads.append({
                    'name': name,
                    'state': current_state,
                    'source': 'wikipedia_main'
                })

    log.info(f"Main Wiki page: extracted {len(roads)} roads")
    return roads


def parse_state_wiki_page(url: str, state_code: str) -> list[dict]:
    """Parse a state-specific Wikipedia toll road page"""
    log.info(f"Fetching {state_code}: {url}")
    html = fetch_url(url)
    if not html:
        return []

    roads = extract_road_names_from_html(html, state_code)
    log.info(f"{state_code}: extracted {len(roads)} roads from {url}")
    return roads


def get_existing_roads(conn: sqlite3.Connection) -> set:
    """Get set of existing (name, state) tuples"""
    cursor = conn.execute("SELECT name, state FROM tolls")
    return {(row[0].lower(), row[1]) for row in cursor.fetchall()}


def insert_roads(conn: sqlite3.Connection, roads: list[dict], existing: set) -> int:
    """Insert new roads, return count inserted"""
    inserted = 0
    for road in roads:
        name = road['name'].strip()
        state = road.get('state', '')
        source = road.get('source', 'wikipedia')

        key = (name.lower(), state)
        if key in existing:
            continue

        try:
            conn.execute(
                "INSERT OR IGNORE INTO tolls (name, state, source) VALUES (?, ?, ?)",
                (name, state, source)
            )
            existing.add(key)
            inserted += 1
        except Exception as e:
            log.debug(f"Insert error: {e}")

    conn.commit()
    return inserted


def load_progress() -> dict:
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE) as f:
            return json.load(f)
    return {'done_urls': [], 'total_inserted': 0}


def save_progress(progress: dict):
    with open(PROGRESS_FILE, 'w') as f:
        json.dump(progress, f)


def main():
    log.info("=== MEDIUM Parser v2 запущен ===")

    # Connect to DB
    conn = sqlite3.connect(DB_PATH)

    # Ensure tolls table exists
    conn.execute('''
        CREATE TABLE IF NOT EXISTS tolls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            state TEXT,
            highway_number TEXT,
            toll_type TEXT,
            source TEXT,
            UNIQUE(name, state)
        )
    ''')
    conn.commit()

    progress = load_progress()
    done_urls = set(progress.get('done_urls', []))
    total_inserted = progress.get('total_inserted', 0)

    existing = get_existing_roads(conn)
    log.info(f"База: {len(existing)} дорог уже есть")

    all_roads = []

    # 1. Parse main Wikipedia page
    main_url = 'https://en.wikipedia.org/wiki/Toll_roads_in_the_United_States'
    if main_url not in done_urls:
        roads = parse_main_wiki_page()
        all_roads.extend(roads)
        inserted = insert_roads(conn, roads, existing)
        total_inserted += inserted
        done_urls.add(main_url)
        log.info(f"Главная страница: +{inserted} новых дорог (итого {total_inserted})")
        save_progress({'done_urls': list(done_urls), 'total_inserted': total_inserted})
        time.sleep(2)

    # 2. Parse state-specific pages
    for url, state_code in WIKI_PAGES:
        if url in done_urls:
            continue

        roads = parse_state_wiki_page(url, state_code)

        # Handle ALL state code - try to detect state from content
        if state_code == 'ALL':
            inserted = insert_roads(conn, roads, existing)
        else:
            inserted = insert_roads(conn, roads, existing)

        total_inserted += inserted
        all_roads.extend(roads)
        done_urls.add(url)

        log.info(f"{state_code}: +{inserted} новых (итого {total_inserted})")
        save_progress({'done_urls': list(done_urls), 'total_inserted': total_inserted})
        time.sleep(1.5)

    # 3. Wikipedia API search for states with no dedicated page
    parsed_states = {code for _, code in WIKI_PAGES}
    for state_name, state_code in US_STATES:
        if state_code in parsed_states:
            continue

        roads = fetch_wiki_api(state_name)
        if roads:
            for r in roads:
                r['state'] = state_code
            inserted = insert_roads(conn, roads, existing)
            total_inserted += inserted
            if inserted:
                log.info(f"{state_code} (API): +{inserted} новых (итого {total_inserted})")

        time.sleep(0.5)

    # Save results
    with open(OUTPUT_JSON, 'w') as f:
        json.dump(all_roads, f, ensure_ascii=False, indent=2)

    # Final count
    cursor = conn.execute("SELECT COUNT(*) FROM tolls")
    final_count = cursor.fetchone()[0]

    log.info(f"=== MEDIUM v2 завершён ===")
    log.info(f"Добавлено новых: {total_inserted}")
    log.info(f"Итого в базе: {final_count}")

    conn.close()


import urllib.parse

if __name__ == '__main__':
    main()
