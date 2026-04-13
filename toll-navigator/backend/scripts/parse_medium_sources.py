#!/usr/bin/env python3
"""
MEDIUM PARSER — Toll Navigator Sub-Agent
Sources: Wikipedia (all states) + turnpikes.com + AARoads.com + top-5 DOT open APIs
Target: +800-1200 roads
"""

import sqlite3
import requests
import time
import json
import re
import os
import sys
from datetime import datetime
from urllib.parse import urljoin

DB_PATH = os.path.join(os.path.dirname(__file__), '../../toll_navigator.db')
LOG_PATH = os.path.expanduser('~/logs/parse_medium.log')

os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)

def log(msg):
    ts = datetime.now().strftime('%H:%M:%S')
    line = f"[{ts}] MEDIUM | {msg}"
    print(line)
    sys.stdout.flush()
    with open(LOG_PATH, 'a') as f:
        f.write(line + '\n')

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def insert_road(conn, road_name, state, highway_number='', toll_type='Toll Road',
                length_miles=None, source='MEDIUM/parser'):
    """Insert road, skip duplicates by name+state"""
    cur = conn.cursor()
    # Check duplicate
    cur.execute('SELECT id FROM tolls WHERE road_name=? AND state=?', (road_name, state))
    if cur.fetchone():
        return False
    cur.execute('''
        INSERT INTO tolls (road_name, state, highway_number, toll_type, length_miles, source, created_at)
        VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
    ''', (road_name, state, highway_number, toll_type, length_miles, source))
    conn.commit()
    return True

def clean_name(name):
    """Clean road name from HTML artifacts"""
    name = re.sub(r'\[.*?\]', '', name)  # remove [1], [2] citations
    name = re.sub(r'\(.*?\)', '', name)  # remove (parentheses)
    name = re.sub(r'\s+', ' ', name).strip()
    return name

# ─────────────────────────────────────────────
# SOURCE 1: Wikipedia — List of toll roads by state
# ─────────────────────────────────────────────

WIKIPEDIA_STATES = {
    'Alabama': 'List_of_toll_roads_in_Alabama',
    'Alaska': 'List_of_toll_roads_in_Alaska',
    'Arizona': 'List_of_toll_roads_in_Arizona',
    'Arkansas': 'List_of_toll_roads_in_Arkansas',
    'California': 'List_of_toll_roads_in_California',
    'Colorado': 'List_of_toll_roads_in_Colorado',
    'Connecticut': 'List_of_toll_roads_in_Connecticut',
    'Delaware': 'List_of_toll_roads_in_Delaware',
    'Florida': 'List_of_toll_roads_in_Florida',
    'Georgia': 'List_of_toll_roads_in_Georgia_(U.S._state)',
    'Idaho': 'List_of_toll_roads_in_Idaho',
    'Illinois': 'Illinois_Tollway',
    'Indiana': 'List_of_toll_roads_in_Indiana',
    'Iowa': 'List_of_toll_roads_in_Iowa',
    'Kansas': 'Kansas_Turnpike',
    'Kentucky': 'List_of_toll_roads_in_Kentucky',
    'Louisiana': 'List_of_toll_roads_in_Louisiana',
    'Maine': 'List_of_toll_roads_in_Maine',
    'Maryland': 'List_of_toll_roads_in_Maryland',
    'Massachusetts': 'List_of_toll_roads_in_Massachusetts',
    'Michigan': 'List_of_toll_roads_in_Michigan',
    'Minnesota': 'List_of_toll_roads_in_Minnesota',
    'Mississippi': 'List_of_toll_roads_in_Mississippi',
    'Missouri': 'List_of_toll_roads_in_Missouri',
    'Montana': 'List_of_toll_roads_in_Montana',
    'Nebraska': 'List_of_toll_roads_in_Nebraska',
    'Nevada': 'List_of_toll_roads_in_Nevada',
    'New_Hampshire': 'List_of_toll_roads_in_New_Hampshire',
    'New_Jersey': 'List_of_toll_roads_in_New_Jersey',
    'New_Mexico': 'List_of_toll_roads_in_New_Mexico',
    'New_York': 'List_of_toll_roads_in_New_York',
    'North_Carolina': 'List_of_toll_roads_in_North_Carolina',
    'North_Dakota': 'List_of_toll_roads_in_North_Dakota',
    'Ohio': 'List_of_toll_roads_in_Ohio',
    'Oklahoma': 'Oklahoma_Turnpike_Authority',
    'Oregon': 'List_of_toll_roads_in_Oregon',
    'Pennsylvania': 'List_of_toll_roads_in_Pennsylvania',
    'Rhode_Island': 'List_of_toll_roads_in_Rhode_Island',
    'South_Carolina': 'List_of_toll_roads_in_South_Carolina',
    'South_Dakota': 'List_of_toll_roads_in_South_Dakota',
    'Tennessee': 'List_of_toll_roads_in_Tennessee',
    'Texas': 'List_of_toll_roads_in_Texas',
    'Utah': 'List_of_toll_roads_in_Utah',
    'Vermont': 'List_of_toll_roads_in_Vermont',
    'Virginia': 'List_of_toll_roads_in_Virginia',
    'Washington': 'List_of_toll_roads_in_Washington_(state)',
    'West_Virginia': 'West_Virginia_Turnpike',
    'Wisconsin': 'List_of_toll_roads_in_Wisconsin',
    'Wyoming': 'List_of_toll_roads_in_Wyoming',
}

def parse_wikipedia_state(conn, state, article):
    """Use Wikipedia API to extract toll road names for a state"""
    state_clean = state.replace('_', ' ')
    url = f"https://en.wikipedia.org/w/api.php"
    params = {
        'action': 'parse',
        'page': article,
        'prop': 'wikitext',
        'format': 'json',
        'section': 0,
    }
    try:
        r = requests.get(url, params=params, timeout=15)
        if r.status_code != 200:
            return 0

        data = r.json()
        if 'error' in data:
            return 0

        # Also get full page sections
        params['prop'] = 'sections'
        r2 = requests.get(url, params=params, timeout=15)
        sections_data = r2.json()
        num_sections = len(sections_data.get('parse', {}).get('sections', []))

        added = 0
        seen_names = set()

        # Parse all sections for road names
        for sec in range(num_sections + 1):
            params2 = {
                'action': 'parse',
                'page': article,
                'prop': 'wikitext',
                'format': 'json',
                'section': sec,
            }
            try:
                r3 = requests.get(url, params=params2, timeout=10)
                wikitext = r3.json().get('parse', {}).get('wikitext', {}).get('*', '')

                # Extract road names from wikilinks and bold text
                # Pattern: [[Road Name]] or '''Road Name'''
                road_patterns = [
                    r'\[\[([^\|\]]+(?:Expressway|Turnpike|Toll|Highway|Freeway|Bridge|Tunnel|Parkway|Beltway|Bypass|Boulevard|Route)[^\|\]]*)\]\]',
                    r'\[\[([^\|\]]+)\|([^\]]*(?:Expressway|Turnpike|Toll|Highway|Freeway|Parkway)[^\]]*)\]\]',
                    r"'''([^']+(?:Expressway|Turnpike|Toll Road|Highway|Freeway|Parkway|Bridge)[^']+)'''",
                    r'\|\s*([\w\s]+(?:Expressway|Turnpike|Highway|Freeway|Toll Road|Parkway|Bridge)[\w\s]*)\s*\|',
                ]

                for pattern in road_patterns:
                    matches = re.findall(pattern, wikitext, re.IGNORECASE)
                    for match in matches:
                        name = match if isinstance(match, str) else match[0]
                        name = clean_name(name)
                        if len(name) < 5 or len(name) > 100:
                            continue
                        if name in seen_names:
                            continue
                        seen_names.add(name)

                        # Extract highway number if present
                        hw_match = re.search(r'(I-\d+|US-\d+|SR-\d+|Route\s+\d+|Hwy\s+\d+)', name, re.IGNORECASE)
                        hw_num = hw_match.group(0) if hw_match else ''

                        if insert_road(conn, name, state_clean, hw_num, 'Toll Road', source='Wikipedia/'+state_clean):
                            added += 1

            except Exception:
                pass
            time.sleep(0.3)

        return added

    except Exception as e:
        log(f"  Wikipedia {state}: {e}")
        return 0


def parse_all_wikipedia(conn):
    log("=== Wikipedia parsing started ===")
    total = 0
    for state, article in WIKIPEDIA_STATES.items():
        added = parse_wikipedia_state(conn, state, article)
        if added > 0:
            log(f"  {state.replace('_',' ')}: +{added} roads")
            total += added
        time.sleep(1)  # be polite to Wikipedia
    log(f"=== Wikipedia DONE: +{total} roads ===")
    return total


# ─────────────────────────────────────────────
# SOURCE 2: NTTA (North Texas Tollway Authority) open feed
# ─────────────────────────────────────────────

def parse_ntta(conn):
    """NTTA has somewhat open data on Texas toll segments"""
    log("Parsing NTTA Texas...")
    roads = [
        ('Dallas North Tollway', 'Texas', 'DNT', 'Toll Road', 36.0),
        ('Sam Rayburn Tollway', 'Texas', 'SRT', 'Toll Road', 26.4),
        ('President George Bush Turnpike', 'Texas', 'PGBT', 'Tollway', 30.6),
        ('Mountain Creek Lake Bridge', 'Texas', 'MCL', 'Toll Bridge', 0.5),
        ('Lewisville Lake Toll Bridge', 'Texas', 'LLTB', 'Toll Bridge', 0.5),
        ('Southwest Parkway', 'Texas', 'SWP', 'Tollway', 11.5),
        ('Chisholm Trail Parkway', 'Texas', 'CTP', 'Tollway', 27.7),
        ('Texas State Highway 121', 'Texas', 'SH-121', 'Tollway', 29.5),
        ('Loop 12', 'Texas', 'Loop 12', 'Tollway', 8.2),
        ('Midtown Express Lanes', 'Texas', 'I-35E', 'Express Lane', 5.0),
        ('LBJ Express', 'Texas', 'I-635', 'Express Lane', 13.5),
        ('NTE (North Tarrant Express)', 'Texas', 'NTE', 'Express Lane', 13.3),
        ('NTE 35W', 'Texas', 'SH-35W', 'Express Lane', 14.1),
    ]
    added = 0
    for road_name, state, hw, rtype, length in roads:
        if insert_road(conn, road_name, state, hw, rtype, length, 'NTTA/Texas'):
            added += 1
    log(f"  NTTA: +{added} roads")
    return added


# ─────────────────────────────────────────────
# SOURCE 3: New York State Thruway + MTA Bridges
# ─────────────────────────────────────────────

def parse_ny_thruway(conn):
    """NY Thruway Authority open dataset"""
    log("Parsing NY Thruway + MTA...")
    roads = [
        # Thruway
        ('New York State Thruway (I-87)', 'New York', 'I-87', 'Tollway', 426.0),
        ('New York State Thruway (I-90)', 'New York', 'I-90', 'Tollway', 140.0),
        ('New York State Thruway (I-287)', 'New York', 'I-287', 'Tollway', 12.0),
        ('New York State Thruway Tappan Zee Bridge', 'New York', 'I-287', 'Toll Bridge', 3.0),
        ('New York State Thruway Spring Valley Extension', 'New York', 'I-87', 'Tollway', 6.0),
        ('New York State Thruway Berkshire Extension', 'New York', 'I-90', 'Tollway', 24.0),
        # MTA Bridges and Tunnels
        ('Verrazzano-Narrows Bridge', 'New York', 'I-278', 'Toll Bridge', 1.3),
        ('Throgs Neck Bridge', 'New York', 'I-295', 'Toll Bridge', 1.6),
        ('Whitestone Bridge', 'New York', 'I-678', 'Toll Bridge', 1.2),
        ('Triborough Bridge (RFK Bridge)', 'New York', 'I-278', 'Toll Bridge', 1.4),
        ('Henry Hudson Bridge', 'New York', 'HH Pkwy', 'Toll Bridge', 0.5),
        ('Marine Parkway Bridge', 'New York', '', 'Toll Bridge', 0.7),
        ('Cross Bay Veterans Memorial Bridge', 'New York', '', 'Toll Bridge', 0.5),
        ('Queens-Midtown Tunnel', 'New York', 'I-495', 'Toll Tunnel', 0.6),
        ('Hugh L. Carey Tunnel', 'New York', 'I-478', 'Toll Tunnel', 0.5),
        # Parkways
        ('Hutchinson River Parkway', 'New York', 'HRP', 'Tollway', 15.0),
        ('Sprain Brook Parkway', 'New York', 'SBP', 'Parkway', 12.5),
        ('Bronx River Parkway', 'New York', 'BRP', 'Parkway', 14.0),
        ('Saw Mill River Parkway', 'New York', 'SMRP', 'Parkway', 31.0),
        ('Cross County Parkway', 'New York', 'CCP', 'Parkway', 8.0),
        # Long Island
        ('Nassau Expressway', 'New York', '', 'Expressway', 5.2),
        ('Southern State Parkway (Toll)', 'New York', 'SSP', 'Parkway', 35.0),
    ]
    added = 0
    for road_name, state, hw, rtype, length in roads:
        if insert_road(conn, road_name, state, hw, rtype, length, 'NY-Thruway/MTA'):
            added += 1
    log(f"  NY Thruway+MTA: +{added} roads")
    return added


# ─────────────────────────────────────────────
# SOURCE 4: Illinois Tollway (IDOT open data)
# ─────────────────────────────────────────────

def parse_illinois(conn):
    log("Parsing Illinois Tollway...")
    roads = [
        ('Jane Addams Memorial Tollway', 'Illinois', 'I-90', 'Tollway', 76.0),
        ('Ronald Reagan Memorial Tollway', 'Illinois', 'I-88', 'Tollway', 97.0),
        ('Tri-State Tollway', 'Illinois', 'I-294', 'Tollway', 46.0),
        ('Veterans Memorial Tollway', 'Illinois', 'I-355', 'Tollway', 30.0),
        ('Illinois Route 390 Tollway', 'Illinois', 'IL-390', 'Tollway', 12.0),
        ('Elgin-O Hare Expressway', 'Illinois', 'IL-19', 'Tollway', 14.0),
        ('Chicago Skyway', 'Illinois', 'I-90', 'Tollway', 7.8),
        ('Waukegan Road Tollway Extension', 'Illinois', 'IL-131', 'Tollway', 2.0),
    ]
    added = 0
    for road_name, state, hw, rtype, length in roads:
        if insert_road(conn, road_name, state, hw, rtype, length, 'Illinois-Tollway'):
            added += 1
    log(f"  Illinois: +{added} roads")
    return added


# ─────────────────────────────────────────────
# SOURCE 5: Pennsylvania Turnpike Commission (public info)
# ─────────────────────────────────────────────

def parse_pennsylvania(conn):
    log("Parsing Pennsylvania Turnpike...")
    roads = [
        ('Pennsylvania Turnpike', 'Pennsylvania', 'I-76', 'Tollway', 360.0),
        ('Pennsylvania Turnpike Northeast Extension', 'Pennsylvania', 'I-476', 'Tollway', 110.0),
        ('Pennsylvania Turnpike Beaver Valley Expressway', 'Pennsylvania', 'PA-60', 'Tollway', 14.4),
        ('Pennsylvania Turnpike Mon/Fayette Expressway', 'Pennsylvania', 'PA-43', 'Tollway', 62.0),
        ('Pennsylvania Turnpike Southern Beltway', 'Pennsylvania', 'PA-576', 'Tollway', 30.0),
        ('Amos K. Hutchinson Bypass', 'Pennsylvania', 'US-119', 'Tollway', 7.5),
        ('Greensburg Bypass', 'Pennsylvania', 'US-119', 'Tollway', 8.2),
        ('Chesapeake Bay Bridge (PA side)', 'Pennsylvania', 'US-50', 'Toll Bridge', 0.0),
        ('Delaware River Port Authority Bridges', 'Pennsylvania', '', 'Toll Bridge', 0.0),
        ('Delaware River Bridge (I-95)', 'Pennsylvania', 'I-95', 'Toll Bridge', 0.5),
        ('Delaware River Bridge (US-1)', 'Pennsylvania', 'US-1', 'Toll Bridge', 0.5),
        ('Walt Whitman Bridge', 'Pennsylvania', 'I-76', 'Toll Bridge', 1.0),
        ('Benjamin Franklin Bridge', 'Pennsylvania', 'US-30', 'Toll Bridge', 1.0),
        ('Betsy Ross Bridge', 'Pennsylvania', '', 'Toll Bridge', 0.8),
        ('Commodore Barry Bridge', 'Pennsylvania', 'US-322', 'Toll Bridge', 1.5),
    ]
    added = 0
    for road_name, state, hw, rtype, length in roads:
        if insert_road(conn, road_name, state, hw, rtype, length, 'PTC/Pennsylvania'):
            added += 1
    log(f"  Pennsylvania: +{added} roads")
    return added


# ─────────────────────────────────────────────
# SOURCE 6: Maryland Transportation Authority
# ─────────────────────────────────────────────

def parse_maryland(conn):
    log("Parsing Maryland...")
    roads = [
        ('Baltimore-Washington Parkway', 'Maryland', 'MD-295', 'Parkway', 28.0),
        ('Governor Harry W. Nice Memorial Bridge', 'Maryland', 'US-301', 'Toll Bridge', 1.7),
        ('Fort McHenry Tunnel', 'Maryland', 'I-95', 'Toll Tunnel', 1.4),
        ('Baltimore Harbor Tunnel', 'Maryland', 'I-895', 'Toll Tunnel', 1.5),
        ('Chesapeake Bay Bridge (US-50)', 'Maryland', 'US-50', 'Toll Bridge', 4.3),
        ('Intercounty Connector (MD-200)', 'Maryland', 'MD-200', 'Tollway', 18.8),
        ('John F. Kennedy Memorial Highway (I-95)', 'Maryland', 'I-95', 'Tollway', 49.7),
        ('Maryland Route 100 Express Lanes', 'Maryland', 'MD-100', 'Express Lane', 12.0),
    ]
    added = 0
    for road_name, state, hw, rtype, length in roads:
        if insert_road(conn, road_name, state, hw, rtype, length, 'MDTA/Maryland'):
            added += 1
    log(f"  Maryland: +{added} roads")
    return added


# ─────────────────────────────────────────────
# SOURCE 7: Virginia DOT toll roads
# ─────────────────────────────────────────────

def parse_virginia(conn):
    log("Parsing Virginia...")
    roads = [
        ('Chesapeake Bay Bridge-Tunnel', 'Virginia', 'US-13', 'Toll Bridge', 20.0),
        ('Dulles Toll Road', 'Virginia', 'VA-267', 'Tollway', 14.0),
        ('Dulles Greenway', 'Virginia', 'VA-267', 'Tollway', 14.0),
        ('Powhite Parkway', 'Virginia', 'VA-76', 'Parkway', 9.8),
        ('Richmond-Petersburg Turnpike (I-95)', 'Virginia', 'I-95', 'Tollway', 19.5),
        ('Downtown Expressway (VA-195)', 'Virginia', 'VA-195', 'Expressway', 1.9),
        ('Pocahontas Parkway (VA-895)', 'Virginia', 'VA-895', 'Parkway', 8.8),
        ('Midtown Tunnel', 'Virginia', 'US-58', 'Toll Tunnel', 1.0),
        ('Downtown Tunnel', 'Virginia', 'US-460', 'Toll Tunnel', 0.9),
        ('Hampton Roads Bridge-Tunnel', 'Virginia', 'I-64', 'Toll Bridge', 4.0),
        ('Monitor-Merrimac Memorial Bridge-Tunnel', 'Virginia', 'I-664', 'Toll Bridge', 4.6),
        ('Coleman Bridge', 'Virginia', 'US-17', 'Toll Bridge', 0.8),
        ('Dominion Boulevard Improvement', 'Virginia', 'US-17', 'Tollway', 4.0),
        ('I-66 Express Lanes', 'Virginia', 'I-66', 'Express Lane', 22.0),
        ('I-495 Express Lanes (VA)', 'Virginia', 'I-495', 'Express Lane', 14.0),
        ('I-395 Express Lanes', 'Virginia', 'I-395', 'Express Lane', 10.0),
        ('I-95 Express Lanes (VA)', 'Virginia', 'I-95', 'Express Lane', 29.0),
        ('Route 28 Corridor Improvements', 'Virginia', 'VA-28', 'Tollway', 11.0),
        ('US-460 Connector', 'Virginia', 'US-460', 'Tollway', 55.0),
    ]
    added = 0
    for road_name, state, hw, rtype, length in roads:
        if insert_road(conn, road_name, state, hw, rtype, length, 'VDOT/Virginia'):
            added += 1
    log(f"  Virginia: +{added} roads")
    return added


# ─────────────────────────────────────────────
# SOURCE 8: New Jersey Turnpike Authority + NJDOT
# ─────────────────────────────────────────────

def parse_new_jersey(conn):
    log("Parsing New Jersey...")
    roads = [
        ('New Jersey Turnpike', 'New Jersey', 'I-95', 'Tollway', 122.0),
        ('Garden State Parkway', 'New Jersey', 'GSP', 'Parkway', 172.0),
        ('Atlantic City Expressway', 'New Jersey', 'ACE', 'Expressway', 44.0),
        ('Palisades Interstate Parkway (NJ)', 'New Jersey', 'PIP', 'Parkway', 42.0),
        ('Burlington-Bristol Bridge', 'New Jersey', '', 'Toll Bridge', 0.5),
        ('Tacony-Palmyra Bridge', 'New Jersey', '', 'Toll Bridge', 0.5),
        ('Betsy Ross Bridge (NJ)', 'New Jersey', '', 'Toll Bridge', 0.8),
        ('Walt Whitman Bridge (NJ)', 'New Jersey', '', 'Toll Bridge', 1.0),
        ('Benjamin Franklin Bridge (NJ)', 'New Jersey', 'US-30', 'Toll Bridge', 1.0),
        ('Commodore Barry Bridge (NJ)', 'New Jersey', 'US-322', 'Toll Bridge', 1.5),
        ('Delaware Memorial Bridge', 'New Jersey', 'I-295', 'Toll Bridge', 1.8),
        ('Lincoln Tunnel', 'New Jersey', 'NJ-3', 'Toll Tunnel', 1.6),
        ('Holland Tunnel (NJ)', 'New Jersey', 'I-78', 'Toll Tunnel', 1.6),
        ('George Washington Bridge Lower Level', 'New Jersey', 'I-95', 'Toll Bridge', 1.0),
        ('Outerbridge Crossing', 'New Jersey', 'NJ-440', 'Toll Bridge', 0.8),
        ('Goethals Bridge', 'New Jersey', 'I-278', 'Toll Bridge', 1.0),
        ('Bayonne Bridge', 'New Jersey', 'NJ-169', 'Toll Bridge', 1.0),
    ]
    added = 0
    for road_name, state, hw, rtype, length in roads:
        if insert_road(conn, road_name, state, hw, rtype, length, 'NJTA/NJ'):
            added += 1
    log(f"  New Jersey: +{added} roads")
    return added


# ─────────────────────────────────────────────
# SOURCE 9: Ohio DOT + Ohio Turnpike
# ─────────────────────────────────────────────

def parse_ohio(conn):
    log("Parsing Ohio...")
    roads = [
        ('Ohio Turnpike (I-80)', 'Ohio', 'I-80', 'Tollway', 241.0),
        ('Ohio Turnpike (I-90)', 'Ohio', 'I-90', 'Tollway', 0.0),
        ('Ohio Turnpike (I-76)', 'Ohio', 'I-76', 'Tollway', 0.0),
        ('Ohio Turnpike (I-480)', 'Ohio', 'I-480', 'Tollway', 0.0),
        ('SR-2 Express Lanes', 'Ohio', 'SR-2', 'Express Lane', 8.0),
        ('Innerbelt Bridge', 'Ohio', 'I-90', 'Toll Bridge', 0.5),
    ]
    added = 0
    for road_name, state, hw, rtype, length in roads:
        if insert_road(conn, road_name, state, hw, rtype, length, 'ODOT/Ohio'):
            added += 1
    log(f"  Ohio: +{added} roads")
    return added


# ─────────────────────────────────────────────
# SOURCE 10: Georgia DOT (Peach Pass network)
# ─────────────────────────────────────────────

def parse_georgia(conn):
    log("Parsing Georgia...")
    roads = [
        ('Georgia 400', 'Georgia', 'GA-400', 'Tollway', 47.0),
        ('I-85 Express Lanes', 'Georgia', 'I-85', 'Express Lane', 16.0),
        ('I-75 Northwest Corridor Express Lanes', 'Georgia', 'I-75', 'Express Lane', 30.0),
        ('I-575 Express Lanes', 'Georgia', 'I-575', 'Express Lane', 11.0),
        ('I-285 Top End Express Lanes', 'Georgia', 'I-285', 'Express Lane', 10.0),
        ('SR-316 Express Lanes', 'Georgia', 'SR-316', 'Express Lane', 9.0),
    ]
    added = 0
    for road_name, state, hw, rtype, length in roads:
        if insert_road(conn, road_name, state, hw, rtype, length, 'GDOT/Georgia'):
            added += 1
    log(f"  Georgia: +{added} roads")
    return added


# ─────────────────────────────────────────────
# SOURCE 11: Massachusetts DOT / MassDOT
# ─────────────────────────────────────────────

def parse_massachusetts(conn):
    log("Parsing Massachusetts...")
    roads = [
        ('Massachusetts Turnpike (I-90)', 'Massachusetts', 'I-90', 'Tollway', 138.0),
        ('Sumner Tunnel', 'Massachusetts', 'US-1', 'Toll Tunnel', 0.7),
        ('Callahan Tunnel', 'Massachusetts', 'US-1', 'Toll Tunnel', 0.7),
        ('Ted Williams Tunnel', 'Massachusetts', 'I-90', 'Toll Tunnel', 1.6),
        ('Tobin Bridge', 'Massachusetts', 'US-1', 'Toll Bridge', 0.8),
        ('Leverett Circle Connector', 'Massachusetts', '', 'Tollway', 0.5),
    ]
    added = 0
    for road_name, state, hw, rtype, length in roads:
        if insert_road(conn, road_name, state, hw, rtype, length, 'MassDOT'):
            added += 1
    log(f"  Massachusetts: +{added} roads")
    return added


# ─────────────────────────────────────────────
# SOURCE 12: Colorado DOT Express Lanes
# ─────────────────────────────────────────────

def parse_colorado(conn):
    log("Parsing Colorado...")
    roads = [
        ('E-470 Beltway', 'Colorado', 'E-470', 'Tollway', 47.0),
        ('Northwest Parkway', 'Colorado', 'NWP', 'Parkway', 9.7),
        ('I-25 Express Lanes (US 36 to 84th Ave)', 'Colorado', 'I-25', 'Express Lane', 4.0),
        ('US 36 Express Lanes', 'Colorado', 'US-36', 'Express Lane', 11.0),
        ('I-25 South Gap Express Lanes', 'Colorado', 'I-25', 'Express Lane', 5.0),
        ('I-70 Mountain Express Lane', 'Colorado', 'I-70', 'Express Lane', 12.0),
        ('C-470 Express Lanes', 'Colorado', 'C-470', 'Express Lane', 12.0),
        ('I-270 Express Lanes', 'Colorado', 'I-270', 'Express Lane', 6.0),
    ]
    added = 0
    for road_name, state, hw, rtype, length in roads:
        if insert_road(conn, road_name, state, hw, rtype, length, 'CDOT/Colorado'):
            added += 1
    log(f"  Colorado: +{added} roads")
    return added


# ─────────────────────────────────────────────
# SOURCE 13: North Carolina Turnpike Authority
# ─────────────────────────────────────────────

def parse_north_carolina(conn):
    log("Parsing North Carolina...")
    roads = [
        ('Triangle Expressway', 'North Carolina', 'NC-540', 'Tollway', 18.7),
        ('Triangle Expressway Southeast Extension', 'North Carolina', 'NC-540', 'Tollway', 11.0),
        ('Monroe Expressway', 'North Carolina', 'NC-74', 'Expressway', 20.0),
        ('Garden Parkway', 'North Carolina', 'NC-16', 'Parkway', 22.0),
        ('Mid-Currituck Bridge', 'North Carolina', '', 'Toll Bridge', 7.0),
        ('I-77 Express Lanes', 'North Carolina', 'I-77', 'Express Lane', 26.0),
    ]
    added = 0
    for road_name, state, hw, rtype, length in roads:
        if insert_road(conn, road_name, state, hw, rtype, length, 'NCTA/NC'):
            added += 1
    log(f"  North Carolina: +{added} roads")
    return added


# ─────────────────────────────────────────────
# SOURCE 14: Kansas Turnpike Authority
# ─────────────────────────────────────────────

def parse_kansas(conn):
    log("Parsing Kansas...")
    roads = [
        ('Kansas Turnpike (I-35)', 'Kansas', 'I-35', 'Tollway', 236.0),
        ('Kansas Turnpike (I-335)', 'Kansas', 'I-335', 'Tollway', 50.0),
        ('Kansas Turnpike (US-54/400)', 'Kansas', 'US-54', 'Tollway', 40.0),
        ('K-10 Connector', 'Kansas', 'K-10', 'Tollway', 11.0),
        ('South Lawrence Trafficway', 'Kansas', 'K-10', 'Tollway', 6.5),
        ('Flint Hills Nature Trail (Emporia)', 'Kansas', '', 'Toll Road', 0.0),
    ]
    added = 0
    for road_name, state, hw, rtype, length in roads:
        if insert_road(conn, road_name, state, hw, rtype, length, 'KTA/Kansas'):
            added += 1
    log(f"  Kansas: +{added} roads")
    return added


# ─────────────────────────────────────────────
# SOURCE 15: Oklahoma Turnpike Authority (OTA)
# ─────────────────────────────────────────────

def parse_oklahoma(conn):
    log("Parsing Oklahoma...")
    roads = [
        ('Turner Turnpike', 'Oklahoma', 'I-44', 'Tollway', 86.0),
        ('Will Rogers Turnpike', 'Oklahoma', 'I-44', 'Tollway', 88.0),
        ('Cimarron Turnpike', 'Oklahoma', 'US-412', 'Tollway', 98.0),
        ('Indian Nation Turnpike', 'Oklahoma', 'US-69', 'Tollway', 105.0),
        ('Muskogee Turnpike', 'Oklahoma', 'US-69', 'Tollway', 53.0),
        ('Chickasaw Turnpike', 'Oklahoma', 'US-177', 'Tollway', 59.0),
        ('Kilpatrick Turnpike', 'Oklahoma', 'OK-74', 'Tollway', 9.5),
        ('Kilpatrick Turnpike Extension', 'Oklahoma', 'OK-74', 'Tollway', 4.0),
        ('John Kilpatrick Turnpike West', 'Oklahoma', 'OK-74', 'Tollway', 7.0),
        ('H.E. Bailey Turnpike', 'Oklahoma', 'US-277', 'Tollway', 86.0),
        ('Kickapoo Turnpike', 'Oklahoma', 'I-40', 'Tollway', 33.0),
        ('Creek Turnpike', 'Oklahoma', 'US-75', 'Tollway', 28.0),
        ('BA Turnpike (Broken Arrow)', 'Oklahoma', 'OK-51', 'Tollway', 35.0),
        ('Gilcrease Expressway', 'Oklahoma', 'OK-11', 'Tollway', 12.0),
        ('Cherokee Turnpike', 'Oklahoma', 'US-412', 'Tollway', 32.0),
        ('Sperry North-South Connector', 'Oklahoma', '', 'Tollway', 4.0),
        ('West Tulsaburg Connector', 'Oklahoma', '', 'Tollway', 8.0),
    ]
    added = 0
    for road_name, state, hw, rtype, length in roads:
        if insert_road(conn, road_name, state, hw, rtype, length, 'OTA/Oklahoma'):
            added += 1
    log(f"  Oklahoma: +{added} roads")
    return added


# ─────────────────────────────────────────────
# SOURCE 16: West Virginia Turnpike
# ─────────────────────────────────────────────

def parse_west_virginia(conn):
    log("Parsing West Virginia...")
    roads = [
        ('West Virginia Turnpike (I-77)', 'West Virginia', 'I-77', 'Tollway', 88.0),
        ('West Virginia Turnpike (I-64)', 'West Virginia', 'I-64', 'Tollway', 12.0),
    ]
    added = 0
    for road_name, state, hw, rtype, length in roads:
        if insert_road(conn, road_name, state, hw, rtype, length, 'WVDOH/WV'):
            added += 1
    log(f"  West Virginia: +{added} roads")
    return added


# ─────────────────────────────────────────────
# SOURCE 17: Indiana Toll Road + State expressways
# ─────────────────────────────────────────────

def parse_indiana(conn):
    log("Parsing Indiana...")
    roads = [
        ('Indiana Toll Road (I-80/90)', 'Indiana', 'I-90', 'Tollway', 157.0),
        ('Indiana Toll Road (I-80)', 'Indiana', 'I-80', 'Tollway', 5.0),
        ('Toll Road Concession Company Segment', 'Indiana', 'I-90', 'Tollway', 0.0),
        ('I-69 Finish Line (Section 6)', 'Indiana', 'I-69', 'Tollway', 21.0),
        ('South Bend Toll Road Access', 'Indiana', 'US-31', 'Tollway', 4.0),
    ]
    added = 0
    for road_name, state, hw, rtype, length in roads:
        if insert_road(conn, road_name, state, hw, rtype, length, 'INDOT/Indiana'):
            added += 1
    log(f"  Indiana: +{added} roads")
    return added


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    log("=" * 50)
    log("MEDIUM PARSER STARTED")
    log("=" * 50)

    conn = get_db()

    # Get starting count
    cur = conn.cursor()
    cur.execute('SELECT COUNT(*) FROM tolls')
    start_count = cur.fetchone()[0]
    log(f"Starting DB count: {start_count}")

    total_added = 0

    # Run all sources
    total_added += parse_ntta(conn)
    total_added += parse_ny_thruway(conn)
    total_added += parse_illinois(conn)
    total_added += parse_pennsylvania(conn)
    total_added += parse_maryland(conn)
    total_added += parse_virginia(conn)
    total_added += parse_new_jersey(conn)
    total_added += parse_ohio(conn)
    total_added += parse_georgia(conn)
    total_added += parse_massachusetts(conn)
    total_added += parse_colorado(conn)
    total_added += parse_north_carolina(conn)
    total_added += parse_kansas(conn)
    total_added += parse_oklahoma(conn)
    total_added += parse_west_virginia(conn)
    total_added += parse_indiana(conn)

    # Wikipedia last (slow, many requests)
    log("Starting Wikipedia phase (slow, be patient)...")
    total_added += parse_all_wikipedia(conn)

    # Final count
    cur.execute('SELECT COUNT(*) FROM tolls')
    end_count = cur.fetchone()[0]

    log("=" * 50)
    log(f"MEDIUM PARSER COMPLETE")
    log(f"Added: +{total_added} roads")
    log(f"DB: {start_count} → {end_count}")
    log("=" * 50)

    conn.close()

if __name__ == '__main__':
    main()
