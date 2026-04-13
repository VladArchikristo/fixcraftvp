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
    Socrata API — FHWA Toll Facilities.
    Dataset: https://data.transportation.gov/resource/qea2-tqrm.json
    """
    log.info('[FHWA] Fetching data.transportation.gov ...')
    results = []

    # Попробуем несколько endpoint'ов
    endpoints = [
        'https://data.transportation.gov/resource/qea2-tqrm.json?$limit=2000',
        'https://data.transportation.gov/resource/qea2-tqrm.json?$limit=2000&$offset=0',
    ]

    data = None
    for url in endpoints:
        data = fetch_json(url, timeout=30)
        if data:
            break

    if not data:
        log.warning('[FHWA] No data received, skipping')
        return results

    if not isinstance(data, list):
        log.warning(f'[FHWA] Unexpected format: {type(data)}')
        return results

    log.info(f'[FHWA] Raw records: {len(data)}')

    # Inspect first record to understand schema
    if data:
        log.info(f'[FHWA] Sample keys: {list(data[0].keys())[:10]}')

    for row in data:
        # Пробуем разные варианты имён полей (Socrata может менять их)
        name = (
            row.get('facility_name') or
            row.get('toll_facility_name') or
            row.get('name') or
            row.get('road_name') or
            ''
        )
        state = (
            row.get('state_code') or
            row.get('state') or
            row.get('st') or
            ''
        )
        if not name or not state or len(state) > 3:
            continue

        hwy = row.get('route_number') or row.get('highway') or row.get('route') or ''
        length = 0.0
        try:
            length = float(row.get('length_miles') or row.get('length') or row.get('miles') or 0)
        except (ValueError, TypeError):
            pass

        toll_type_raw = (row.get('facility_type') or row.get('toll_type') or '').lower()
        if 'bridge' in toll_type_raw or 'tunnel' in toll_type_raw:
            toll_type = 'bridge_tunnel'
        elif 'express' in toll_type_raw or 'managed' in toll_type_raw or 'hot' in toll_type_raw:
            toll_type = 'express_lane'
        else:
            toll_type = 'toll_road'

        results.append(make_record(
            name=name,
            state=state,
            highway_number=str(hwy),
            toll_type=toll_type,
            length_miles=length,
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
    Florida DOT GIS — ArcGIS Feature Service.
    Пробуем несколько известных FL GIS endpoints.
    """
    log.info('[FLDOT] Fetching Florida toll roads GIS ...')
    results = []

    # FL GIS открытые данные
    endpoints = [
        # FDOT Open Data ArcGIS: Toll Facilities
        'https://opendata.arcgis.com/datasets/7ae36d6ef5bc4a0b9abff24617a4a2ab_0.geojson',
        # Альтернативный ArcGIS REST
        'https://services1.arcgis.com/O1JpcwDW8sjYuddV/arcgis/rest/services/Toll_Roads/FeatureServer/0/query?where=STATE_CD+%3D+%27FL%27&outFields=*&f=json&resultRecordCount=500',
        # FDOT District GIS
        'https://gis.fdot.gov/arcgis/rest/services/Roadway/FDOT_Toll_Facilities/FeatureServer/0/query?where=1%3D1&outFields=FACILITY_NAME,ROUTE_ID,BEGIN_POST,END_POST,STATE_RD&f=json&resultRecordCount=500',
    ]

    data = None
    used_url = ''
    for url in endpoints:
        log.info(f'[FLDOT] Trying: {url[:80]}...')
        data = fetch_json(url, timeout=30)
        if data:
            used_url = url
            break

    if not data:
        log.warning('[FLDOT] All endpoints failed, skipping FL DOT')
        return results

    # GeoJSON format
    if isinstance(data, dict) and 'features' in data:
        features = data['features']
        log.info(f'[FLDOT] GeoJSON features: {len(features)}')
        if features:
            sample_props = features[0].get('properties', {})
            log.info(f'[FLDOT] Sample props: {list(sample_props.keys())[:8]}')

        for feat in features:
            props = feat.get('properties', {}) or {}
            name = (
                props.get('FACILITY_NAME') or props.get('NAME') or
                props.get('ROAD_NAME') or props.get('name') or ''
            )
            if not name:
                continue
            hwy = props.get('ROUTE_ID') or props.get('ROUTE') or props.get('STATE_RD') or ''
            length = 0.0
            try:
                length = float(props.get('LENGTH_MILES') or props.get('SHAPE_LEN') or 0)
                if length > 1000:  # вероятно в футах или метрах
                    length = length / 5280.0
            except (ValueError, TypeError):
                pass

            results.append(make_record(
                name=name, state='FL', highway_number=str(hwy),
                length_miles=length, source='FLDOT/ArcGIS'
            ))

    # ArcGIS REST format
    elif isinstance(data, dict) and 'features' in data:
        pass  # уже обработано выше

    elif isinstance(data, dict) and data.get('features'):
        features = data['features']
        log.info(f'[FLDOT] ArcGIS REST features: {len(features)}')
        for feat in features:
            attrs = feat.get('attributes', {}) or {}
            name = attrs.get('FACILITY_NAME') or attrs.get('NAME') or ''
            if not name:
                continue
            results.append(make_record(
                name=name, state='FL',
                highway_number=attrs.get('ROUTE_ID', ''),
                source='FLDOT/ArcGIS'
            ))

    log.info(f'[FLDOT] Parsed {len(results)} FL records')
    return results


# ─── Source 4: TxDOT (Texas) ──────────────────────────────────────────────────

def parse_txdot() -> list:
    """
    TxDOT открытые данные — Texas toll roads.
    Пробуем TxDOT open data portal и ArcGIS REST.
    """
    log.info('[TxDOT] Fetching Texas toll roads ...')
    results = []

    endpoints = [
        # TxDOT Open Data ArcGIS
        'https://services.arcgis.com/KTcxiTD9dsQw4r7Z/arcgis/rest/services/TxDOT_Highways/FeatureServer/0/query?where=TOLL_ROAD+%3D+%27Y%27&outFields=RTE_NM,HWY_NM,BEGIN_DFO,END_DFO&f=json&resultRecordCount=500',
        # Альтернатива через data.texas.gov (Socrata)
        'https://data.texas.gov/resource/e8td-6dxb.json?$limit=500',
        # TxDOT Pavement & Roadway
        'https://opendata.arcgis.com/datasets/0b3d6e1bf6f64f7cac6e98cced9c86eb_0.geojson',
    ]

    data = None
    for url in endpoints:
        log.info(f'[TxDOT] Trying: {url[:80]}...')
        data = fetch_json(url, timeout=30)
        if data:
            break

    if not data:
        log.warning('[TxDOT] All endpoints failed, skipping TxDOT')
        return results

    # ArcGIS REST
    if isinstance(data, dict) and 'features' in data:
        features = data.get('features', [])
        log.info(f'[TxDOT] ArcGIS features: {len(features)}')
        if features:
            sample = features[0].get('attributes', {})
            log.info(f'[TxDOT] Sample attrs: {list(sample.keys())[:8]}')

        for feat in features:
            attrs = feat.get('attributes', {}) or {}
            name = attrs.get('HWY_NM') or attrs.get('RTE_NM') or attrs.get('NAME') or ''
            if not name:
                continue
            hwy = attrs.get('RTE_NM') or attrs.get('ROUTE') or ''
            results.append(make_record(
                name=name, state='TX', highway_number=str(hwy),
                source='TxDOT/ArcGIS'
            ))

    # GeoJSON
    elif isinstance(data, dict) and 'type' in data and data.get('type') == 'FeatureCollection':
        features = data.get('features', [])
        log.info(f'[TxDOT] GeoJSON features: {len(features)}')
        for feat in features:
            props = feat.get('properties', {}) or {}
            name = props.get('HWY_NM') or props.get('NAME') or props.get('name') or ''
            if not name:
                continue
            results.append(make_record(
                name=name, state='TX',
                highway_number=props.get('RTE_NM', ''),
                source='TxDOT/GeoJSON'
            ))

    # Socrata JSON array
    elif isinstance(data, list):
        log.info(f'[TxDOT] Socrata records: {len(data)}')
        if data:
            log.info(f'[TxDOT] Sample keys: {list(data[0].keys())[:8]}')
        for row in data:
            name = row.get('highway_name') or row.get('name') or row.get('road_name') or ''
            state = row.get('state') or 'TX'
            if not name:
                continue
            results.append(make_record(
                name=name, state=state,
                highway_number=row.get('route_number', ''),
                source='TxDOT/Socrata'
            ))

    log.info(f'[TxDOT] Parsed {len(results)} TX records')
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
