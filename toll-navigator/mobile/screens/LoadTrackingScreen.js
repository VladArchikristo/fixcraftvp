import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  Alert,
  Share,
  ScrollView,
  ActivityIndicator,
  Platform,
} from 'react-native';
import * as Clipboard from 'expo-clipboard';
import * as Location from 'expo-location';
import { Ionicons } from '@expo/vector-icons';
import { loadTrackingService } from '../services/loadTrackingService';
import { COLORS, SPACING, RADIUS } from '../theme';

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
    }).catch(() => {
      // Session restore failed — start fresh
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
  const handleCopy = useCallback(async () => {
    if (!trackingUrl) return;
    try {
      await Clipboard.setStringAsync(trackingUrl);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      Alert.alert('Error', 'Could not copy to clipboard.');
    }
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
        <Ionicons name="location" size={28} color={COLORS.primary} />
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
            placeholderTextColor={COLORS.textMuted}
            editable={!isLoading}
          />
          <TouchableOpacity
            style={[styles.btn, styles.btnPrimary, isLoading && styles.btnDisabled]}
            onPress={handleStart}
            disabled={isLoading}
          >
            {isLoading
              ? <ActivityIndicator color={COLORS.textInverse} />
              : <>
                  <Ionicons name="radio" size={18} color={COLORS.textInverse} style={{ marginRight: 8 }} />
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
                <Ionicons name={copied ? 'checkmark' : 'copy-outline'} size={16} color={COLORS.primary} style={{ marginRight: 6 }} />
                <Text style={styles.btnOutlineText}>{copied ? 'Copied!' : 'Copy Link'}</Text>
              </TouchableOpacity>

              <TouchableOpacity style={[styles.btn, styles.btnOutline, styles.flex1]} onPress={handleShare}>
                <Ionicons name="share-social-outline" size={16} color={COLORS.primary} style={{ marginRight: 6 }} />
                <Text style={styles.btnOutlineText}>Share</Text>
              </TouchableOpacity>
            </View>
          </View>

          {/* Ping current position */}
          <TouchableOpacity style={[styles.btn, styles.btnSecondary]} onPress={handlePingLocation}>
            <Ionicons name="locate" size={16} color={COLORS.primary} style={{ marginRight: 8 }} />
            <Text style={styles.btnSecondaryText}>Update My Position Now</Text>
          </TouchableOpacity>

          {/* Stop / Delivered */}
          <TouchableOpacity
            style={[styles.btn, styles.btnDanger, isLoading && styles.btnDisabled]}
            onPress={handleStop}
            disabled={isLoading}
          >
            {isLoading
              ? <ActivityIndicator color={COLORS.textInverse} />
              : <>
                  <Ionicons name="checkmark-circle" size={18} color={COLORS.textInverse} style={{ marginRight: 8 }} />
                  <Text style={styles.btnText}>Mark as Delivered</Text>
                </>
            }
          </TouchableOpacity>
        </>
      )}

      {/* Info note */}
      <View style={styles.note}>
        <Ionicons name="shield-checkmark-outline" size={14} color={COLORS.textMuted} style={{ marginRight: 6 }} />
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
    backgroundColor: COLORS.bg,
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
    color: COLORS.textPrimary,
  },
  headerSub: {
    fontSize: 13,
    color: COLORS.textSecondary,
    marginBottom: SPACING.lg,
    lineHeight: 19,
  },

  card: {
    backgroundColor: COLORS.bgCard,
    borderRadius: RADIUS.md,
    padding: SPACING.md,
    marginBottom: SPACING.md,
    borderWidth: 1,
    borderColor: COLORS.bgCardAlt,
  },
  label: {
    fontSize: 11,
    textTransform: 'uppercase',
    letterSpacing: 0.8,
    color: COLORS.textMuted,
    marginBottom: SPACING.sm,
  },
  infoValue: {
    fontSize: 16,
    fontWeight: '600',
    color: COLORS.textPrimary,
  },

  input: {
    backgroundColor: COLORS.bg,
    borderWidth: 1,
    borderColor: COLORS.border,
    borderRadius: RADIUS.sm,
    color: COLORS.textPrimary,
    fontSize: 15,
    padding: 12,
    marginBottom: SPACING.md,
  },

  urlBox: {
    backgroundColor: COLORS.bg,
    borderWidth: 1,
    borderColor: COLORS.border,
    borderRadius: RADIUS.sm,
    padding: 12,
    marginBottom: 14,
  },
  urlText: {
    color: COLORS.primary,
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
    backgroundColor: COLORS.accent,
    marginBottom: 0,
  },
  btnSecondary: {
    backgroundColor: COLORS.bgCard,
    borderWidth: 1,
    borderColor: COLORS.primary + '55',
  },
  btnOutline: {
    backgroundColor: 'transparent',
    borderWidth: 1,
    borderColor: COLORS.primary + '55',
    marginBottom: 0,
  },
  btnDanger: {
    backgroundColor: COLORS.error,
  },
  btnDisabled: {
    opacity: 0.5,
  },
  btnText: {
    color: COLORS.textInverse,
    fontWeight: '700',
    fontSize: 15,
  },
  btnOutlineText: {
    color: COLORS.primary,
    fontWeight: '600',
    fontSize: 14,
  },
  btnSecondaryText: {
    color: COLORS.primary,
    fontWeight: '600',
    fontSize: 14,
  },

  // Active status pill
  statusPill: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: COLORS.successLight,
    borderWidth: 1,
    borderColor: COLORS.success + '44',
    borderRadius: 20,
    paddingHorizontal: 14,
    paddingVertical: SPACING.sm,
    alignSelf: 'flex-start',
    marginBottom: SPACING.md,
  },
  dot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: COLORS.success,
    marginRight: SPACING.sm,
  },
  statusText: {
    color: COLORS.success,
    fontSize: 13,
    fontWeight: '600',
  },

  note: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    marginTop: SPACING.sm,
    paddingHorizontal: SPACING.xs,
  },
  noteText: {
    color: COLORS.textMuted,
    fontSize: 12,
    flex: 1,
    lineHeight: 17,
  },
});
