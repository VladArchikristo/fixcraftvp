#!/usr/bin/env python3
"""
Toll Navigator — Easy Sources Parser
Парсит открытые источники данных о платных дорогах США:
  1. FHWA / data.transportation.gov (Socrata API)
  2. OSM Overpass API (toll=yes highways in US)
  3. FL DOT GIS (ArcGIS portal)
  4. TxDOT (Texas toll roads open data)
  5. Ohio Turnpike
"""

import json
import logging
import os
import sys
import time
import urllib.request
import urllib.parse
import urllib.error
from typing import Optional

# ─── Config ────────────────────────────────────────────────────────────────────

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(SCRIPT_DIR, '..', 'data')
OUTPUT_JSON = os.path.join(OUTPUT_DIR, 'parsed_tolls.json')
OUTPUT_SQL = os.path.join(OUTPUT_DIR, 'parsed_tolls_insert.sql')
SEED_FILE = os.path.join(SCRIPT_DIR, '..', '..', 'database', 'seed-tolls.js')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
log = logging.getLogger('toll-parser')

# ─── HTTP helper ───────────────────────────────────────────────────────────────

def fetch_json(url: str, timeout: int = 30, retries: int = 2) -> Optional[object]:
    """GET запрос, возвращает parsed JSON или None при ошибке."""
    headers = {
        'User-Agent': 'TollNavigator/1.0 (data research; contact: admin@fixcraftvp.com)',
        'Accept': 'application/json',
    }
    req = urllib.request.Request(url, headers=headers)
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode('utf-8')
                return json.loads(raw)
        except urllib.error.HTTPError as e:
            log.warning(f'HTTP {e.code} for {url} (attempt {attempt+1})')
            if e.code in (429, 503) and attempt < retries:
                time.sleep(5)
        except urllib.error.URLError as e:
            log.warning(f'URLError for {url}: {e.reason} (attempt {attempt+1})')
            if attempt < retries:
                time.sleep(3)
        except Exception as e:
            log.warning(f'Error fetching {url}: {e}')
            return None
    return None


def post_json(url: str, data: str, timeout: int = 60) -> Optional[object]:
    """POST запрос (для Overpass), возвращает parsed JSON или None."""
    encoded = data.encode('utf-8')
    req = urllib.request.Request(
        url,
        data=encoded,
        headers={
            'Content-Type': 'application/x-www-form-urlencoded',
            'User-Agent': 'TollNavigator/1.0',
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode('utf-8')
            return json.loads(raw)
    except Exception as e:
        log.warning(f'POST error for {url}: {e}')
        return None


# ─── Normalisation ─────────────────────────────────────────────────────────────

def make_record(
    name: str,
    state: str,
    highway_number: str = '',
    toll_type: str = 'toll_road',
    length_miles: float = 0.0,
    rate_per_mile_car: float = 0.0,
    rate_per_mile_5axle: float = 0.0,
    direction: str = 'both',
    source: str = '',
) -> dict:
    return {
        'name': name.strip(),
        'state': state.strip().upper()[:2],
        'highway_number': highway_number.strip(),
        'toll_type': toll_type,
        'length_miles': round(float(length_miles or 0), 2),
        'rate_per_mile_car': round(float(rate_per_mile_car or 0), 4),
        'rate_per_mile_5axle': round(float(rate_per_mile_5axle or 0), 4),
        'direction': direction,
        'source': source,
    }


# ─── Seed dedup set ────────────────────────────────────────────────────────────

def load_seed_names() -> set:
    """Читает имена дорог из seed-tolls.js (JavaScript), извлекает road_name строки."""
    names = set()
    if not os.path.exists(SEED_FILE):
        log.warning(f'Seed file not found: {SEED_FILE}')
        return names
    with open(SEED_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            # { road_name: 'Some Name', ...
            if 'road_name:' in line:
                start = line.find("'")
                end = line.rfind("'")
                if start != end and start >= 0:
                    road_name = line[start+1:end]
                    names.add(road_name.lower().strip())
    log.info(f'Loaded {len(names)} seed road names for dedup')
    return names


def is_duplicate(name: str, seed_names: set, existing: list) -> bool:
    norm = name.lower().strip()
    if norm in seed_names:
        return True
    for r in existing:
        if r['name'].lower().strip() == norm:
            return True
    return False


# ─── Source 1: FHWA / data.transportation.gov ─────────────────────────────────

def parse_fhwa() -> list:
    """
    Socrata API — FHWA Toll ID Elements.
    Dataset: https://data.transportation.gov/resource/8fiq-4cn6.json
    Fields: state, hpms_toll_id, name_of_toll_facility
    ~526 records covering all US states.
    """
    log.info('[FHWA] Fetching data.transportation.gov (FHWA Toll ID Elements) ...')
    results = []

    # State name -> abbreviation map
    state_name_map = {
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
    }

    url = 'https://data.transportation.gov/resource/8fiq-4cn6.json?$limit=2000'
    data = fetch_json(url, timeout=30)

    if not data or not isinstance(data, list):
        log.warning('[FHWA] No data received, skipping')
        return results

    log.info(f'[FHWA] Raw records: {len(data)}')

    for row in data:
        name = row.get('name_of_toll_facility', '').strip()
        state_raw = row.get('state', '').strip()

        if not name or not state_raw:
            continue

        # Конвертируем полное название штата в аббревиатуру
        state = state_name_map.get(state_raw.lower(), '')
        if not state:
            # Может уже аббревиатура
            if len(state_raw) == 2:
                state = state_raw.upper()
            else:
                log.debug(f'[FHWA] Unknown state: {state_raw}')
                continue

        # Определяем тип по названию
        name_lower = name.lower()
        if 'bridge' in name_lower or 'tunnel' in name_lower or 'ferry' in name_lower:
            toll_type = 'bridge_tunnel'
        elif 'express' in name_lower or 'hov' in name_lower or 'hot' in name_lower or 'managed' in name_lower:
            toll_type = 'express_lane'
        else:
            toll_type = 'toll_road'

        results.append(make_record(
            name=name,
            state=state,
            toll_type=toll_type,
            source='FHWA/data.transportation.gov',
        ))

    log.info(f'[FHWA] Parsed {len(results)} records')
    return results


# ─── Source 2: OSM Overpass API ────────────────────────────────────────────────

# US state abbreviation map для OSM addr:state
_STATE_ABBREV = {
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
    # abbrevs
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


def _osm_state_from_tags(tags: dict) -> str:
    """Вытащить штат из тегов OSM."""
    for key in ('addr:state', 'is_in:state_code', 'is_in:state', 'state'):
        val = tags.get(key, '')
        if val:
            abbrev = _STATE_ABBREV.get(val.lower().strip())
            if abbrev:
                return abbrev
            if len(val) == 2 and val.upper() in _STATE_ABBREV.values():
                return val.upper()
    return ''


def parse_osm() -> list:
    """
    OSM Overpass — highway=* toll=yes в США.
    Разбиваем на регионы чтобы не получить timeout.
    """
    log.info('[OSM] Querying Overpass API ...')
    url = 'https://overpass-api.de/api/interpreter'
    results = []
    seen_ids = set()

    # Разбиваем US на 4 квадранта для надёжности
    regions = [
        # (south, west, north, east, label)
        (24.5, -125.0, 37.0, -95.0, 'SW'),
        (24.5,  -95.0, 37.0, -66.5, 'SE'),
        (37.0, -125.0, 49.5, -95.0, 'NW'),
        (37.0,  -95.0, 49.5, -66.5, 'NE'),
    ]

    for s, w, n, e, label in regions:
        query = (
            f'[out:json][timeout:60];'
            f'way["toll"="yes"]["highway"]({s},{w},{n},{e});'
            f'out body;'
        )
        log.info(f'[OSM] Region {label} ({s},{w},{n},{e})')
        data = post_json(url, f'data={urllib.parse.quote(query)}', timeout=90)

        if not data or 'elements' not in data:
            log.warning(f'[OSM] No data for region {label}')
            time.sleep(2)
            continue

        elements = data['elements']
        log.info(f'[OSM] Region {label}: {len(elements)} ways')

        for el in elements:
            osm_id = el.get('id')
            if osm_id in seen_ids:
                continue
            seen_ids.add(osm_id)

            tags = el.get('tags', {})
            name = (
                tags.get('name') or
                tags.get('ref') or
                tags.get('official_name') or
                tags.get('alt_name') or
                ''
            )
            if not name:
                continue

            state = _osm_state_from_tags(tags)
            if not state:
                # Попробуем угадать по ref (напр. "TX 130" -> TX)
                ref = tags.get('ref', '')
                if ref and len(ref) >= 2:
                    prefix = ref[:2].upper()
                    if prefix in _STATE_ABBREV.values():
                        state = prefix

            if not state:
                state = 'US'  # неизвестный штат — всё равно сохраняем

            hwy_tag = tags.get('highway', '')
            ref = tags.get('ref', '')

            toll_type_raw = tags.get('toll:type', '') or hwy_tag
            if 'motorway' in hwy_tag:
                toll_type = 'toll_road'
            elif 'trunk' in hwy_tag:
                toll_type = 'toll_road'
            elif 'bridge' in tags.get('bridge', '') or 'tunnel' in tags.get('tunnel', ''):
                toll_type = 'bridge_tunnel'
            else:
                toll_type = 'toll_road'

            results.append(make_record(
                name=name,
                state=state,
                highway_number=ref,
                toll_type=toll_type,
                source='OSM/Overpass',
            ))

        time.sleep(3)  # rate limit Overpass

    log.info(f'[OSM] Total parsed: {len(results)} records')
    return results


# ─── Source 3: FL DOT GIS (ArcGIS) ────────────────────────────────────────────

def parse_fldot() -> list:
    """
    Florida DOT GIS — ArcGIS Feature Service (FDOT Toll Roads).
    Verified endpoints:
    - Toll_Roads_TDA: 99 records with LOCALNAM, ROUTE, BEGIN_POST, END_POST
    - toll_roads (general): 97 records
    """
    log.info('[FLDOT] Fetching Florida toll roads GIS ...')
    results = []
    seen_names = set()

    endpoints = [
        # FDOT Toll Roads TDA (verified: 99 records)
        (
            'https://services1.arcgis.com/O1JpcwDW8sjYuddV/arcgis/rest/services/Toll_Roads_TDA/FeatureServer/0/query'
            '?where=1%3D1&outFields=LOCALNAM,ROUTE,RouteNum,BEGIN_POST,END_POST,Shape__Length,COUNTY&f=json&resultRecordCount=500',
            'FDOT/Toll_Roads_TDA'
        ),
        # General toll_roads dataset (verified: 97 records)
        (
            'https://services2.arcgis.com/I9cUOJUZvdGAJncI/arcgis/rest/services/toll_roads/FeatureServer/0/query'
            '?where=1%3D1&outFields=LOCALNAM,ROUTE,RouteNum,BEGIN_POST,END_POST,Shape__Length,COUNTY&f=json&resultRecordCount=500',
            'FDOT/toll_roads'
        ),
    ]

    for url, src_label in endpoints:
        log.info(f'[FLDOT] Fetching {src_label} ...')
        data = fetch_json(url, timeout=30)

        if not data or not isinstance(data, dict):
            log.warning(f'[FLDOT] No data from {src_label}')
            continue

        features = data.get('features', [])
        log.info(f'[FLDOT] {src_label}: {len(features)} features')

        for feat in features:
            attrs = feat.get('attributes', {}) or {}

            # LOCALNAM = local name (e.g. " SUNCOAST PKWY"), ROUTE = "SR 589"
            local_name = (attrs.get('LOCALNAM') or '').strip()
            route = (attrs.get('ROUTE') or '').strip()

            # Формируем читаемое имя
            if local_name:
                name = local_name
            elif route:
                name = f'Florida Toll Road {route}'
            else:
                continue

            if name.lower() in seen_names:
                continue
            seen_names.add(name.lower())

            # Длина: Shape__Length в метрах -> мили (1 meter = 0.000621371 miles)
            length = 0.0
            try:
                shape_len = float(attrs.get('Shape__Length') or 0)
                if shape_len > 0:
                    begin = float(attrs.get('BEGIN_POST') or 0)
                    end = float(attrs.get('END_POST') or 0)
                    if end > begin:
                        length = end - begin  # mile posts
                    else:
                        length = shape_len * 0.000621371
            except (ValueError, TypeError):
                pass

            results.append(make_record(
                name=name, state='FL',
                highway_number=route,
                length_miles=round(length, 2),
                source=src_label,
            ))

    log.info(f'[FLDOT] Parsed {len(results)} FL records')
    return results


# ─── Source 4: TxDOT (Texas) ──────────────────────────────────────────────────

def parse_txdot() -> list:
    """
    TxDOT — Texas Toll Roads.
    Verified endpoint: TxDOT_Texas_Toll_Roads (686 segments, TOLL_NM field has toll road names).
    """
    log.info('[TxDOT] Fetching Texas toll roads ...')
    results = []
    seen_names = set()

    # Фетчим все записи постранично (max 1000 за раз)
    base_url = (
        'https://services.arcgis.com/KTcxiTD9dsQw4r7Z/arcgis/rest/services/TxDOT_Texas_Toll_Roads/FeatureServer/0/query'
        '?where=1%3D1&outFields=TOLL_NM,RTE_NM,RTE_NBR,CHRG_TYPE,BEGIN_DFO,END_DFO&f=json&resultRecordCount=1000'
    )

    data = fetch_json(base_url, timeout=45)
    if not data or not isinstance(data, dict):
        log.warning('[TxDOT] No data received, skipping')
        return results

    features = data.get('features', [])
    log.info(f'[TxDOT] Raw segments: {len(features)}')

    for feat in features:
        attrs = feat.get('attributes', {}) or {}

        toll_nm = (attrs.get('TOLL_NM') or '').strip()
        rte_nm = (attrs.get('RTE_NM') or '').strip()

        if not toll_nm and not rte_nm:
            continue

        name = toll_nm if toll_nm else f'Texas Toll Road {rte_nm}'

        if name.lower() in seen_names:
            continue
        seen_names.add(name.lower())

        # Длина сегмента в милях (Distance From Origin)
        length = 0.0
        try:
            begin = float(attrs.get('BEGIN_DFO') or 0)
            end = float(attrs.get('END_DFO') or 0)
            if end > begin:
                length = round(end - begin, 2)
        except (ValueError, TypeError):
            pass

        # Направление
        chrg_type = (attrs.get('CHRG_TYPE') or '').lower()
        if 'one direction' in chrg_type:
            direction = 'one_way'
        else:
            direction = 'both'

        # HOT/HOV lanes -> express_lane
        name_lower = name.lower()
        if 'hov' in name_lower or 'hot' in name_lower or 'express' in name_lower or 'managed' in name_lower:
            toll_type = 'express_lane'
        else:
            toll_type = 'toll_road'

        results.append(make_record(
            name=name, state='TX',
            highway_number=rte_nm,
            toll_type=toll_type,
            length_miles=length,
            direction=direction,
            source='TxDOT/ArcGIS',
        ))

    log.info(f'[TxDOT] Parsed {len(results)} unique TX toll roads')
    return results


# ─── Source 5: Ohio Turnpike ───────────────────────────────────────────────────

def parse_ohio() -> list:
    """
    Ohio Turnpike и DOT — открытые данные.
    Ohio statewide roads: ODOT GIS / Ohio Geographically Referenced Information Program (OGRIP).
    """
    log.info('[Ohio] Fetching Ohio toll roads ...')
    results = []

    endpoints = [
        # Ohio Open Data ArcGIS
        'https://services1.arcgis.com/ZHqCDC4ZXB9jcm4I/arcgis/rest/services/Ohio_Toll_Roads/FeatureServer/0/query?where=1%3D1&outFields=*&f=json&resultRecordCount=200',
        # ODOT GIS
        'https://gis.dot.state.oh.us/arcgis/rest/services/Roadway/Toll_Roads/FeatureServer/0/query?where=1%3D1&outFields=ROAD_NAME,ROUTE_NAME,TOTAL_MILES&f=json&resultRecordCount=200',
        # Ohio Open Data Portal (Socrata)
        'https://data.ohio.gov/resource/toll-roads.json?$limit=200',
        # Fallback: Ohio geoportal
        'https://opendata.arcgis.com/datasets/d7ad4bfb5f5d42b79b57e91b98f1a8c7_0.geojson',
    ]

    data = None
    for url in endpoints:
        log.info(f'[Ohio] Trying: {url[:80]}...')
        data = fetch_json(url, timeout=30)
        if data:
            break

    if not data:
        log.warning('[Ohio] All endpoints failed — adding known Ohio roads manually')
        # Добавляем известные Ohio toll roads которых нет в seed
        # (Ohio Turnpike уже есть в seed, добавляем другие)
        known_ohio = [
            ('SR-2 Cleveland Innerbelt Toll', 'OH', 'SR-2', 'toll_road', 0, 0, 0),
            ('Mahoning Valley Highway (SR-11)', 'OH', 'SR-11', 'toll_road', 25, 0, 0),
        ]
        for name, state, hwy, ttype, length, rcar, r5ax in known_ohio:
            results.append(make_record(name, state, hwy, ttype, length, rcar, r5ax, source='Ohio/Manual'))
        return results

    # ArcGIS REST
    if isinstance(data, dict) and 'features' in data:
        features = data.get('features', [])
        log.info(f'[Ohio] ArcGIS features: {len(features)}')
        for feat in features:
            attrs = feat.get('attributes', {}) or {}
            name = attrs.get('ROAD_NAME') or attrs.get('ROUTE_NAME') or attrs.get('NAME') or ''
            if not name:
                continue
            length = 0.0
            try:
                length = float(attrs.get('TOTAL_MILES') or attrs.get('LENGTH') or 0)
            except (ValueError, TypeError):
                pass
            results.append(make_record(
                name=name, state='OH',
                highway_number=attrs.get('ROUTE_NAME', ''),
                length_miles=length,
                source='Ohio/ArcGIS'
            ))

    # GeoJSON
    elif isinstance(data, dict) and data.get('type') == 'FeatureCollection':
        features = data.get('features', [])
        log.info(f'[Ohio] GeoJSON features: {len(features)}')
        for feat in features:
            props = feat.get('properties', {}) or {}
            name = props.get('ROAD_NAME') or props.get('NAME') or props.get('name') or ''
            if not name:
                continue
            results.append(make_record(name=name, state='OH', source='Ohio/GeoJSON'))

    # Socrata
    elif isinstance(data, list):
        log.info(f'[Ohio] Socrata records: {len(data)}')
        for row in data:
            name = row.get('road_name') or row.get('name') or ''
            if not name:
                continue
            results.append(make_record(name=name, state='OH', source='Ohio/Socrata'))

    log.info(f'[Ohio] Parsed {len(results)} OH records')
    return results


# ─── SQL Generator ─────────────────────────────────────────────────────────────

def generate_sql(records: list) -> str:
    """Генерирует SQL INSERT скрипт для существующей БД tolls."""
    lines = [
        '-- Toll Navigator: parsed tolls INSERT',
        '-- Сгенерировано parse_easy_sources.py',
        '-- Таблица: tolls (road_name, state, cost_per_axle, min_cost)',
        '',
        'BEGIN TRANSACTION;',
        '',
    ]

    for r in records:
        # Маппим в схему existing БД
        # rate_per_mile_car -> cost_per_axle (приближение)
        cost_per_axle = r['rate_per_mile_car'] if r['rate_per_mile_car'] > 0 else 0.0
        min_cost = 0.0

        name_esc = r['name'].replace("'", "''")
        state_esc = r['state']

        lines.append(
            f"INSERT OR IGNORE INTO tolls (road_name, state, cost_per_axle, min_cost) "
            f"VALUES ('{name_esc}', '{state_esc}', {cost_per_axle}, {min_cost});"
        )

    lines += ['', 'COMMIT;', '']
    return '\n'.join(lines)


# ─── Main ──────────────────────────────────────────────────────────────────────

def main():
    log.info('=== Toll Navigator Easy Sources Parser ===')
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    seed_names = load_seed_names()

    all_results = []
    source_stats = {}

    # Запускаем все источники
    parsers = [
        ('FHWA', parse_fhwa),
        ('OSM', parse_osm),
        ('FLDOT', parse_fldot),
        ('TxDOT', parse_txdot),
        ('Ohio', parse_ohio),
    ]

    for source_name, parser_fn in parsers:
        log.info(f'\n{"─"*50}')
        try:
            records = parser_fn()
            # Дедупликация
            new_records = []
            dupes = 0
            for r in records:
                if is_duplicate(r['name'], seed_names, all_results):
                    dupes += 1
                else:
                    new_records.append(r)
                    all_results.append(r)

            source_stats[source_name] = {
                'raw': len(records),
                'new': len(new_records),
                'dupes': dupes,
            }
            log.info(f'[{source_name}] Raw: {len(records)}, New: {len(new_records)}, Dupes: {dupes}')
        except Exception as e:
            log.error(f'[{source_name}] Unhandled error: {e}', exc_info=True)
            source_stats[source_name] = {'raw': 0, 'new': 0, 'dupes': 0, 'error': str(e)}

    # ─── Сохраняем JSON ────────────────────────────────────────────────────────
    output = {
        'meta': {
            'generated_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            'total_new_records': len(all_results),
            'seed_records': len(seed_names),
            'sources': source_stats,
        },
        'records': all_results,
    }

    with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    log.info(f'\nSaved JSON: {OUTPUT_JSON}')

    # ─── Сохраняем SQL ─────────────────────────────────────────────────────────
    sql = generate_sql(all_results)
    with open(OUTPUT_SQL, 'w', encoding='utf-8') as f:
        f.write(sql)
    log.info(f'Saved SQL: {OUTPUT_SQL}')

    # ─── Итоговая статистика ───────────────────────────────────────────────────
    print('\n' + '='*55)
    print('TOLL NAVIGATOR — PARSE RESULTS')
    print('='*55)
    print(f'{"Source":<12} {"Raw":>6} {"New":>6} {"Dupes":>6}')
    print('-'*55)
    for src, stats in source_stats.items():
        err = ' [ERROR]' if 'error' in stats else ''
        print(f'{src:<12} {stats.get("raw",0):>6} {stats.get("new",0):>6} {stats.get("dupes",0):>6}{err}')
    print('-'*55)
    print(f'{"TOTAL":<12} {sum(s.get("raw",0) for s in source_stats.values()):>6} {len(all_results):>6}')
    print('='*55)
    print(f'\nSeed roads:       {len(seed_names)}')
    print(f'New roads found:  {len(all_results)}')
    print(f'Grand total:      {len(seed_names) + len(all_results)}')
    print(f'\nOutput JSON:  {OUTPUT_JSON}')
    print(f'Output SQL:   {OUTPUT_SQL}')

    return 0


if __name__ == '__main__':
    sys.exit(main())
