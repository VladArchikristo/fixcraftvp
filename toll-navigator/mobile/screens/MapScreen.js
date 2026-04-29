import React, { useState, useEffect } from 'react';
import {
  View, Text, StyleSheet, TouchableOpacity, ActivityIndicator
} from 'react-native';
import { WebView } from 'react-native-webview';
import { Ionicons } from '@expo/vector-icons';
import { COLORS, SPACING, RADIUS } from '../theme';

// City coordinates lookup (top US cities)
const CITY_COORDS = {
  'dallas, tx': [32.7767, -96.7970],
  'houston, tx': [29.7604, -95.3698],
  'san antonio, tx': [29.4241, -98.4936],
  'austin, tx': [30.2672, -97.7431],
  'fort worth, tx': [32.7555, -97.3308],
  'los angeles, ca': [34.0522, -118.2437],
  'san francisco, ca': [37.7749, -122.4194],
  'san diego, ca': [32.7157, -117.1611],
  'sacramento, ca': [38.5816, -121.4944],
  'miami, fl': [25.7617, -80.1918],
  'orlando, fl': [28.5383, -81.3792],
  'tampa, fl': [27.9506, -82.4572],
  'jacksonville, fl': [30.3322, -81.6557],
  'chicago, il': [41.8781, -87.6298],
  'new york, ny': [40.7128, -74.0060],
  'philadelphia, pa': [39.9526, -75.1652],
  'atlanta, ga': [33.7490, -84.3880],
  'charlotte, nc': [35.2271, -80.8431],
  'nashville, tn': [36.1627, -86.7816],
  'memphis, tn': [35.1495, -90.0490],
  'denver, co': [39.7392, -104.9903],
  'phoenix, az': [33.4484, -112.0740],
  'las vegas, nv': [36.1699, -115.1398],
  'seattle, wa': [47.6062, -122.3321],
  'portland, or': [45.5051, -122.6750],
  'boston, ma': [42.3601, -71.0589],
  'detroit, mi': [42.3314, -83.0458],
  'columbus, oh': [39.9612, -82.9988],
  'cleveland, oh': [41.4993, -81.6944],
  'pittsburgh, pa': [40.4406, -79.9959],
  'kansas city, mo': [39.0997, -94.5786],
  'st. louis, mo': [38.6270, -90.1994],
  'minneapolis, mn': [44.9778, -93.2650],
  'new orleans, la': [29.9511, -90.0715],
  'louisville, ky': [38.2527, -85.7585],
  'indianapolis, in': [39.7684, -86.1581],
};

function getCityCoords(cityStr) {
  const key = cityStr.toLowerCase().trim();
  if (CITY_COORDS[key]) return CITY_COORDS[key];
  const found = Object.keys(CITY_COORDS).find((k) => k.includes(key) || key.includes(k.split(',')[0]));
  return found ? CITY_COORDS[found] : null;
}

async function geocodeAddress(address) {
  try {
    const url = `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(address)}&limit=1`;
    const res = await fetch(url, { headers: { 'User-Agent': 'HaulWallet/1.0' } });
    const data = await res.json();
    if (data && data.length > 0) {
      return [parseFloat(data[0].lat), parseFloat(data[0].lon)];
    }
  } catch (e) {
    console.warn('[MapScreen] Geocode failed:', e.message);
  }
  return null;
}

async function resolveCoords(input) {
  // First try hardcoded cities (fast + no network)
  const cached = getCityCoords(input);
  if (cached) return cached;
  // Fallback to OpenStreetMap geocoding
  return await geocodeAddress(input);
}

async function fetchOSRMRoute(fromCoords, toCoords) {
  const url = `https://router.project-osrm.org/route/v1/driving/${fromCoords[1]},${fromCoords[0]};${toCoords[1]},${toCoords[0]}?overview=full&geometries=geojson`;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 10000);
  try {
    const res = await fetch(url, { signal: controller.signal });
    clearTimeout(timer);
    const data = await res.json();
    if (data.code === 'Ok' && data.routes && data.routes.length > 0) {
      // GeoJSON coordinates are [lng, lat], convert to [lat, lng] for Leaflet
      return data.routes[0].geometry.coordinates.map(c => [c[1], c[0]]);
    }
  } catch (e) {
    console.warn('[MapScreen] OSRM fetch failed:', e.message);
  }
  return null;
}

function buildLeafletHTML(fromCoords, toCoords, fromLabel, toLabel, total, routeCoords) {
  const centerLat = (fromCoords[0] + toCoords[0]) / 2;
  const centerLng = (fromCoords[1] + toCoords[1]) / 2;

  // If we have OSRM route coords, use them; otherwise fallback to straight line
  const useFallback = !routeCoords || routeCoords.length === 0;
  const latlngsJSON = useFallback
    ? JSON.stringify([[fromCoords[0], fromCoords[1]], [toCoords[0], toCoords[1]]])
    : JSON.stringify(routeCoords);
  const lineStyle = useFallback
    ? `{ color: '#1B3A5C', weight: 3, opacity: 0.8, dashArray: '8, 6' }`
    : `{ color: '#1B3A5C', weight: 4, opacity: 0.9 }`;

  return `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Route Map</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  <style>
    body { margin: 0; padding: 0; background: #FFFFFF; }
    #map { height: 100vh; width: 100vw; }
    .cost-badge {
      position: absolute;
      bottom: 20px;
      left: 50%;
      transform: translateX(-50%);
      background: rgba(255,255,255,0.95);
      color: #1B3A5C;
      border: 2px solid #FF8C00;
      border-radius: 12px;
      padding: 10px 20px;
      font-family: -apple-system, sans-serif;
      font-size: 18px;
      font-weight: 800;
      z-index: 1000;
      white-space: nowrap;
      box-shadow: 0 2px 8px rgba(0,0,0,0.15);
    }
  </style>
</head>
<body>
  <div id="map"></div>
  <div class="cost-badge">\u{1F4B0} $${total.toFixed(2)}</div>
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <script>
    var map = L.map('map', {
      center: [${centerLat}, ${centerLng}],
      zoom: 5,
      zoomControl: true,
    });

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '\u00a9 OpenStreetMap',
      maxZoom: 18,
    }).addTo(map);

    var fromIcon = L.divIcon({
      html: '<div style="background:#1B3A5C;border:3px solid #fff;border-radius:50%;width:18px;height:18px;box-shadow:0 2px 8px rgba(0,0,0,0.3)"></div>',
      iconSize: [18, 18],
      iconAnchor: [9, 9],
      className: '',
    });
    var toIcon = L.divIcon({
      html: '<div style="background:#2E7D32;border:3px solid #fff;border-radius:50%;width:18px;height:18px;box-shadow:0 2px 8px rgba(0,0,0,0.3)"></div>',
      iconSize: [18, 18],
      iconAnchor: [9, 9],
      className: '',
    });

    var fromMarker = L.marker([${fromCoords[0]}, ${fromCoords[1]}], { icon: fromIcon })
      .addTo(map)
      .bindPopup('<b style="color:#1B3A5C">\u{1F4CD} ${fromLabel.replace(/'/g, "\\'")}</b><br>From')
      .openPopup();

    var toMarker = L.marker([${toCoords[0]}, ${toCoords[1]}], { icon: toIcon })
      .addTo(map)
      .bindPopup('<b style="color:#2E7D32">\u{1F3C1} ${toLabel.replace(/'/g, "\\'")}</b><br>To');

    var latlngs = ${latlngsJSON};
    var polyline = L.polyline(latlngs, ${lineStyle}).addTo(map);

    map.fitBounds(polyline.getBounds(), { padding: [40, 40] });
  </script>
</body>
</html>`;
}

export default function MapScreen({ route, navigation }) {
  const { from, to, total } = route.params;
  const [loading, setLoading] = useState(true);
  const [routeCoords, setRouteCoords] = useState(null);
  const [fetchingRoute, setFetchingRoute] = useState(false);
  const [fromCoords, setFromCoords] = useState(null);
  const [toCoords, setToCoords] = useState(null);
  const [geoError, setGeoError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setGeoError(null);
      const [fc, tc] = await Promise.all([resolveCoords(from), resolveCoords(to)]);
      if (cancelled) return;
      if (!fc || !tc) {
        setGeoError(!fc && !tc ? 'Could not find both addresses' : !fc ? `Could not find origin: "${from}"` : `Could not find destination: "${to}"`);
        setLoading(false);
        return;
      }
      setFromCoords(fc);
      setToCoords(tc);
      setFetchingRoute(true);
      const osrmRoute = await fetchOSRMRoute(fc, tc);
      if (cancelled) return;
      setRouteCoords(osrmRoute);
      setFetchingRoute(false);
      setLoading(false);
    })();
    return () => { cancelled = true; };
  }, []);

  const hasCoords = fromCoords && toCoords;

  const html = hasCoords && !fetchingRoute
    ? buildLeafletHTML(fromCoords, toCoords, from, to, total ?? 0, routeCoords)
    : null;

  return (
    <View style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity style={styles.backBtn} onPress={() => navigation.goBack()}>
          <Ionicons name="arrow-back" size={22} color={COLORS.primary} />
        </TouchableOpacity>
        <View style={styles.headerInfo}>
          <Text style={styles.headerRoute} numberOfLines={1}>
            {from} → {to}
          </Text>
          {total != null && (
            <Text style={styles.headerCost}>Tolls: ${total.toFixed(2)}</Text>
          )}
        </View>
      </View>

      {geoError ? (
        <View style={styles.noCoords}>
          <Text style={styles.noCoordsIcon}>🗺️</Text>
          <Text style={styles.noCoordsText}>{geoError}</Text>
          <Text style={styles.noCoordsHint}>Try using format: "14228 Plantation Park Blvd, Charlotte, NC"</Text>
        </View>
      ) : loading || fetchingRoute ? (
        <View style={styles.loadingOverlay}>
          <ActivityIndicator size="large" color={COLORS.primary} />
          <Text style={styles.loadingText}>
            {fetchingRoute ? 'Building driving route...' : 'Looking up addresses...'}
          </Text>
        </View>
      ) : (
        <>
          <WebView
            source={{ html }}
            style={styles.webview}
            onLoadEnd={() => setLoading(false)}
            originWhitelist={['*']}
            javaScriptEnabled
            domStorageEnabled
            startInLoadingState={false}
          />
        </>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.bg },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: SPACING.md,
    paddingVertical: 12,
    backgroundColor: COLORS.bg,
    borderBottomWidth: 1,
    borderBottomColor: COLORS.bgCardAlt,
  },
  backBtn: { padding: SPACING.xs, marginRight: 12 },
  headerInfo: { flex: 1 },
  headerRoute: { color: COLORS.textPrimary, fontSize: 14, fontWeight: '700' },
  headerCost: { color: COLORS.primary, fontSize: 12, marginTop: 2 },
  webview: { flex: 1 },
  loadingOverlay: {
    position: 'absolute',
    top: 70,
    left: 0,
    right: 0,
    bottom: 0,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: COLORS.bg,
    zIndex: 10,
  },
  loadingText: { color: COLORS.primary, marginTop: 12, fontSize: 14 },
  noCoords: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 40,
  },
  noCoordsIcon: { fontSize: 60, marginBottom: SPACING.md },
  noCoordsText: { color: COLORS.textPrimary, fontSize: 16, fontWeight: '700', textAlign: 'center', marginBottom: SPACING.sm },
  noCoordsHint: { color: COLORS.textMuted, fontSize: 13, textAlign: 'center' },
});
