import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  Alert,
  Share,
  Clipboard,
  ScrollView,
  ActivityIndicator,
  Platform,
} from 'react-native';
import * as Location from 'expo-location';
import { Ionicons } from '@expo/vector-icons';
import { loadTrackingService } from '../services/loadTrackingService';

export default function LoadTrackingScreen() {
  const [destination, setDestination] = useState('');
  const [trackingUrl, setTrackingUrl] = useState(null);
  const [token, setToken] = useState(null);
  const [isActive, setIsActive] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [copied, setCopied] = useState(false);
  const [locationStatus, setLocationStatus] = useState(null); // 'granted'|'denied'|null

  // ── On mount: restore active session if any ────────────
  useEffect(() => {
    loadTrackingService.getActiveSession().then((session) => {
      if (session) {
        setToken(session.token);
        setTrackingUrl(session.trackingUrl);
        setDestination(session.destination || '');
        setIsActive(true);
      }
    });
  }, []);

  // ── Request location permission ────────────────────────
  const ensureLocationPermission = async () => {
    const { status } = await Location.requestForegroundPermissionsAsync();
    setLocationStatus(status);
    if (status !== 'granted') {
      Alert.alert(
        'Location Required',
        'Please enable location permission so brokers can track your load.',
        [{ text: 'OK' }]
      );
      return false;
    }
    return true;
  };

  // ── Start tracking ─────────────────────────────────────
  const handleStart = async () => {
    if (!destination.trim()) {
      Alert.alert('Destination required', 'Enter where you are delivering to.');
      return;
    }

    const hasPermission = await ensureLocationPermission();
    if (!hasPermission) return;

    setIsLoading(true);
    try {
      const result = await loadTrackingService.startTracking(destination.trim());
      setToken(result.token);
      setTrackingUrl(result.trackingUrl);
      setIsActive(true);

      // Send initial position immediately
      const loc = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.Balanced });
      await loadTrackingService.sendLocationUpdate(
        result.token,
        loc.coords.latitude,
        loc.coords.longitude,
        loc.coords.speed ? loc.coords.speed * 2.237 : null // m/s → mph
      );
    } catch (err) {
      Alert.alert('Error', err.message || 'Could not start tracking. Check connection.');
    } finally {
      setIsLoading(false);
    }
  };

  // ── Stop tracking ──────────────────────────────────────
  const handleStop = async () => {
    Alert.alert(
      'Mark as Delivered?',
      'This will end tracking. The broker link will show "Load delivered."',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Mark Delivered',
          style: 'destructive',
          onPress: async () => {
            setIsLoading(true);
            try {
              await loadTrackingService.stopTracking(token);
              setIsActive(false);
              setToken(null);
              setTrackingUrl(null);
            } catch (err) {
              Alert.alert('Error', err.message || 'Could not stop tracking.');
            } finally {
              setIsLoading(false);
            }
          },
        },
      ]
    );
  };

  // ── Copy link ──────────────────────────────────────────
  const handleCopy = useCallback(() => {
    if (!trackingUrl) return;
    Clipboard.setString(trackingUrl);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [trackingUrl]);

  // ── Share link ─────────────────────────────────────────
  const handleShare = useCallback(async () => {
    if (!trackingUrl) return;
    try {
      await Share.share({
        message: `Track my load live: ${trackingUrl}`,
        title: 'Live Load Tracking',
      });
    } catch (err) {
      // User cancelled — ignore
    }
  }, [trackingUrl]);

  // ── Update position manually ───────────────────────────
  const handlePingLocation = useCallback(async () => {
    if (!token) return;
    try {
      const loc = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.Balanced });
      await loadTrackingService.sendLocationUpdate(
        token,
        loc.coords.latitude,
        loc.coords.longitude,
        loc.coords.speed ? loc.coords.speed * 2.237 : null
      );
    } catch (err) {
      Alert.alert('GPS Error', 'Could not get current location.');
    }
  }, [token]);

  // ── Render ─────────────────────────────────────────────
  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">

      {/* Header */}
      <View style={styles.headerRow}>
        <Ionicons name="location" size={28} color="#4fc3f7" />
        <Text style={styles.headerTitle}>Load Tracking</Text>
      </View>
      <Text style={styles.headerSub}>
        Share a live link with your broker — they see your truck on a map in real time.
      </Text>

      {/* ── IDLE STATE ─────────────────────────────────── */}
      {!isActive && (
        <View style={styles.card}>
          <Text style={styles.label}>Destination</Text>
          <TextInput
            style={styles.input}
            value={destination}
            onChangeText={setDestination}
            placeholder="e.g. Dallas, TX"
            placeholderTextColor="#555"
            editable={!isLoading}
          />
          <TouchableOpacity
            style={[styles.btn, styles.btnPrimary, isLoading && styles.btnDisabled]}
            onPress={handleStart}
            disabled={isLoading}
          >
            {isLoading
              ? <ActivityIndicator color="#fff" />
              : <>
                  <Ionicons name="radio" size={18} color="#fff" style={{ marginRight: 8 }} />
                  <Text style={styles.btnText}>Start Load Tracking</Text>
                </>
            }
          </TouchableOpacity>
        </View>
      )}

      {/* ── ACTIVE STATE ───────────────────────────────── */}
      {isActive && trackingUrl && (
        <>
          {/* Status pill */}
          <View style={styles.statusPill}>
            <View style={styles.dot} />
            <Text style={styles.statusText}>Tracking active — broker sees you live</Text>
          </View>

          {/* Destination info */}
          <View style={styles.card}>
            <Text style={styles.label}>Destination</Text>
            <Text style={styles.infoValue}>{destination}</Text>
          </View>

          {/* Link card */}
          <View style={styles.card}>
            <Text style={styles.label}>Broker Link</Text>
            <View style={styles.urlBox}>
              <Text style={styles.urlText} numberOfLines={2} selectable>{trackingUrl}</Text>
            </View>

            <View style={styles.actionRow}>
              <TouchableOpacity style={[styles.btn, styles.btnOutline, styles.flex1]} onPress={handleCopy}>
                <Ionicons name={copied ? 'checkmark' : 'copy-outline'} size={16} color="#4fc3f7" style={{ marginRight: 6 }} />
                <Text style={styles.btnOutlineText}>{copied ? 'Copied!' : 'Copy Link'}</Text>
              </TouchableOpacity>

              <TouchableOpacity style={[styles.btn, styles.btnOutline, styles.flex1]} onPress={handleShare}>
                <Ionicons name="share-social-outline" size={16} color="#4fc3f7" style={{ marginRight: 6 }} />
                <Text style={styles.btnOutlineText}>Share</Text>
              </TouchableOpacity>
            </View>
          </View>

          {/* Ping current position */}
          <TouchableOpacity style={[styles.btn, styles.btnSecondary]} onPress={handlePingLocation}>
            <Ionicons name="locate" size={16} color="#4fc3f7" style={{ marginRight: 8 }} />
            <Text style={styles.btnSecondaryText}>Update My Position Now</Text>
          </TouchableOpacity>

          {/* Stop / Delivered */}
          <TouchableOpacity
            style={[styles.btn, styles.btnDanger, isLoading && styles.btnDisabled]}
            onPress={handleStop}
            disabled={isLoading}
          >
            {isLoading
              ? <ActivityIndicator color="#fff" />
              : <>
                  <Ionicons name="checkmark-circle" size={18} color="#fff" style={{ marginRight: 8 }} />
                  <Text style={styles.btnText}>Mark as Delivered</Text>
                </>
            }
          </TouchableOpacity>
        </>
      )}

      {/* Info note */}
      <View style={styles.note}>
        <Ionicons name="shield-checkmark-outline" size={14} color="#555" style={{ marginRight: 6 }} />
        <Text style={styles.noteText}>
          Brokers see location only — no IFTA data, no history.
          Link expires when you mark delivery.
        </Text>
      </View>

    </ScrollView>
  );
}

// ── Styles ─────────────────────────────────────────────────────────────────────
const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0d0d1a',
  },
  content: {
    padding: 20,
    paddingBottom: 40,
  },

  headerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    marginBottom: 6,
    marginTop: Platform.OS === 'ios' ? 10 : 0,
  },
  headerTitle: {
    fontSize: 22,
    fontWeight: '700',
    color: '#fff',
  },
  headerSub: {
    fontSize: 13,
    color: '#888',
    marginBottom: 24,
    lineHeight: 19,
  },

  card: {
    backgroundColor: '#131326',
    borderRadius: 12,
    padding: 16,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: '#1e1e3a',
  },
  label: {
    fontSize: 11,
    textTransform: 'uppercase',
    letterSpacing: 0.8,
    color: '#666',
    marginBottom: 8,
  },
  infoValue: {
    fontSize: 16,
    fontWeight: '600',
    color: '#fff',
  },

  input: {
    backgroundColor: '#0d0d1a',
    borderWidth: 1,
    borderColor: '#2a2a4a',
    borderRadius: 8,
    color: '#fff',
    fontSize: 15,
    padding: 12,
    marginBottom: 16,
  },

  urlBox: {
    backgroundColor: '#0d0d1a',
    borderWidth: 1,
    borderColor: '#2a2a4a',
    borderRadius: 8,
    padding: 12,
    marginBottom: 14,
  },
  urlText: {
    color: '#4fc3f7',
    fontSize: 13,
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
  },

  actionRow: {
    flexDirection: 'row',
    gap: 10,
  },
  flex1: { flex: 1 },

  btn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 10,
    padding: 14,
    marginBottom: 12,
  },
  btnPrimary: {
    backgroundColor: '#4fc3f7',
    marginBottom: 0,
  },
  btnSecondary: {
    backgroundColor: '#131326',
    borderWidth: 1,
    borderColor: '#4fc3f755',
  },
  btnOutline: {
    backgroundColor: 'transparent',
    borderWidth: 1,
    borderColor: '#4fc3f755',
    marginBottom: 0,
  },
  btnDanger: {
    backgroundColor: '#c62828',
  },
  btnDisabled: {
    opacity: 0.5,
  },
  btnText: {
    color: '#fff',
    fontWeight: '700',
    fontSize: 15,
  },
  btnOutlineText: {
    color: '#4fc3f7',
    fontWeight: '600',
    fontSize: 14,
  },
  btnSecondaryText: {
    color: '#4fc3f7',
    fontWeight: '600',
    fontSize: 14,
  },

  // Active status pill
  statusPill: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(76,175,80,0.12)',
    borderWidth: 1,
    borderColor: '#66bb6a44',
    borderRadius: 20,
    paddingHorizontal: 14,
    paddingVertical: 8,
    alignSelf: 'flex-start',
    marginBottom: 16,
  },
  dot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: '#66bb6a',
    marginRight: 8,
  },
  statusText: {
    color: '#66bb6a',
    fontSize: 13,
    fontWeight: '600',
  },

  note: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    marginTop: 8,
    paddingHorizontal: 4,
  },
  noteText: {
    color: '#555',
    fontSize: 12,
    flex: 1,
    lineHeight: 17,
  },
});
