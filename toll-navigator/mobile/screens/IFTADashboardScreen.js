import React, { useState, useCallback, useEffect } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  ActivityIndicator, Alert, Platform,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useFocusEffect } from '@react-navigation/native';
import * as FileSystem from 'expo-file-system';
import * as Sharing from 'expo-sharing';
import * as Print from 'expo-print';
import api from '../services/api';
import { generateIFTAPDF } from '../ifta/quarterlyCalculator';
import {
  startBackgroundTracking,
  stopBackgroundTracking,
  isTrackingActive,
} from '../services/backgroundLocationService';
import { getTodayMiles, getCurrentState } from '../services/iftaMileageTracker';
import { getStateName } from '../services/stateDetectionService';
import { COLORS, SPACING, RADIUS } from '../theme';

const CURRENT_YEAR = new Date().getFullYear();
const QUARTERS = [1, 2, 3, 4];

function getDefaultQuarter() {
  return Math.ceil((new Date().getMonth() + 1) / 3);
}

export default function IFTADashboardScreen() {
  const [quarter, setQuarter] = useState(getDefaultQuarter());
  const [year, setYear] = useState(CURRENT_YEAR);

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [exportingPdf, setExportingPdf] = useState(false);
  const [driverInfo, setDriverInfo] = useState({ name: '', company: '', usdot: '' });

  // GPS tracking state
  const [tracking, setTracking] = useState(false);
  const [trackingLoading, setTrackingLoading] = useState(false);
  const [todayMiles, setTodayMiles] = useState(0);
  const [currentState, setCurrentState] = useState(null);

  // ── Tracking helpers ──────────────────────────────────────────────────────

  const refreshTrackingStatus = useCallback(async () => {
    try {
      const [active, miles, state] = await Promise.all([
        isTrackingActive(),
        getTodayMiles(),
        getCurrentState(),
      ]);
      setTracking(active);
      setTodayMiles(miles);
      setCurrentState(state);
    } catch (err) {
      console.warn('[IFTA] refreshTrackingStatus error:', err.message);
    }
  }, []);

  // Poll tracking stats every 30s while the screen is focused
  useEffect(() => {
    refreshTrackingStatus();
    const interval = setInterval(refreshTrackingStatus, 30000);
    return () => clearInterval(interval);
  }, [refreshTrackingStatus]);

  const handleToggleTracking = async () => {
    setTrackingLoading(true);
    try {
      if (tracking) {
        const result = await stopBackgroundTracking();
        if (!result.success) {
          Alert.alert('Error', result.error || 'Could not stop tracking');
        } else {
          setTracking(false);
        }
      } else {
        const result = await startBackgroundTracking();
        if (!result.success) {
          // Show user-friendly permission instructions
          Alert.alert(
            'Location Permission Required',
            result.error ||
              'Please allow "Always" location access in Settings to enable background GPS tracking for IFTA.',
            [{ text: 'OK' }]
          );
        } else {
          setTracking(true);
        }
      }
    } catch (err) {
      Alert.alert('Error', err.message);
    } finally {
      setTrackingLoading(false);
      refreshTrackingStatus();
    }
  };

  // ─────────────────────────────────────────────────────────────────────────

  const loadIFTA = useCallback(async (q = quarter, y = year) => {
    setLoading(true);
    try {
      const { data: res } = await api.get('/api/trips/ifta', { params: { quarter: q, year: y } });
      setData(res);
    } catch (err) {
      const msg = err.response?.data?.error || 'Failed to load IFTA data';
      Alert.alert('Error', msg);
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [quarter, year]);

  // Load profile once for PDF
  useFocusEffect(
    useCallback(() => {
      loadIFTA(quarter, year);
      api.get('/api/users/profile').then(res => {
        const d = res.data;
        setDriverInfo({
          name: d.name || 'Owner-Operator',
          company: d.company || '',
          usdot: d.usdot || '',
        });
      }).catch(() => {});
    }, [quarter, year])
  );

  const handleQuarterChange = (q) => {
    setQuarter(q);
    loadIFTA(q, year);
  };

  const handleYearChange = (delta) => {
    const newYear = year + delta;
    setYear(newYear);
    loadIFTA(quarter, newYear);
  };

  const exportPDF = async () => {
    if (!data) {
      Alert.alert('No data', 'Nothing to export');
      return;
    }
    setExportingPdf(true);
    try {
      const html = generateIFTAPDF(data, driverInfo);
      const { uri } = await Print.printToFileAsync({
        html,
        base64: false,
      });

      // Rename file
      const filename = `ifta_q${data.quarter}_${data.year}.pdf`;
      const destUri = FileSystem.cacheDirectory + filename;
      await FileSystem.copyAsync({ from: uri, to: destUri });

      if (await Sharing.isAvailableAsync()) {
        await Sharing.shareAsync(destUri, {
          mimeType: 'application/pdf',
          dialogTitle: `IFTA Q${data.quarter} ${data.year}`,
          UTI: 'com.adobe.pdf',
        });
      } else {
        Alert.alert('PDF Created', `Saved: ${filename}`);
      }
    } catch (err) {
      Alert.alert('Error PDF', err.message || 'Failed to create PDF');
      console.error('[IFTA PDF export]', err);
    } finally {
      setExportingPdf(false);
    }
  };

  const exportCSV = async () => {
    if (!data || !data.states || data.states.length === 0) {
      Alert.alert('No data', 'Nothing to export');
      return;
    }
    setExporting(true);

    try {
      // Generate CSV
      const header = 'State,Miles,Consumed Gal,Purchased Gal,Net Gal,Tax Rate,Tax Due ($),Refund\n';
      const rows = data.states.map(s =>
        [
          s.state,
          s.total_miles,
          s.consumed_gallons,
          s.purchased_gallons,
          s.net_gallons,
          s.tax_rate,
          s.tax_due.toFixed(4),
          s.refund ? 'YES' : 'NO',
        ].join(',')
      ).join('\n');

      const totalLine = `\nTOTAL,${data.total_miles},,,,, ${data.total_tax_due.toFixed(4)},`;
      const csvContent = `IFTA Report Q${data.quarter} ${data.year}\n\n${header}${rows}${totalLine}`;

      const filename = `ifta_q${data.quarter}_${data.year}.csv`;
      const fileUri = FileSystem.cacheDirectory + filename;

      await FileSystem.writeAsStringAsync(fileUri, csvContent, { encoding: FileSystem.EncodingType.UTF8 });

      if (await Sharing.isAvailableAsync()) {
        await Sharing.shareAsync(fileUri, {
          mimeType: 'text/csv',
          dialogTitle: `IFTA Q${data.quarter} ${data.year}`,
          UTI: 'public.comma-separated-values-text',
        });
      } else {
        Alert.alert('File Created', `Saved: ${filename}`);
      }
    } catch (err) {
      Alert.alert('Export Error', err.message || 'Failed to create CSV');
      console.error('[IFTA export]', err);
    } finally {
      setExporting(false);
    }
  };

  const totalDue = data?.total_tax_due ?? 0;
  const isRefund = totalDue < 0;

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.scroll}>

      {/* Header */}
      <Text style={styles.title}>IFTA Dashboard</Text>

      {/* GPS Tracking Card */}
      <View style={[styles.trackingCard, tracking ? styles.trackingCardActive : styles.trackingCardIdle]}>
        {/* Status row */}
        <View style={styles.trackingRow}>
          <View style={styles.trackingStatusLeft}>
            <View style={[styles.trackingDot, { backgroundColor: tracking ? COLORS.success : COLORS.error }]} />
            <Text style={[styles.trackingStatusText, { color: tracking ? COLORS.success : COLORS.error }]}>
              {tracking ? 'Tracking Active' : 'Tracking Stopped'}
            </Text>
          </View>

          <TouchableOpacity
            style={[
              styles.trackingBtn,
              tracking ? styles.trackingBtnStop : styles.trackingBtnStart,
              trackingLoading && styles.exportBtnDisabled,
            ]}
            onPress={handleToggleTracking}
            disabled={trackingLoading}
          >
            {trackingLoading ? (
              <ActivityIndicator size="small" color={COLORS.textInverse} />
            ) : (
              <Ionicons
                name={tracking ? 'stop-circle-outline' : 'navigate-outline'}
                size={16}
                color={COLORS.textInverse}
              />
            )}
            <Text style={styles.trackingBtnText}>
              {trackingLoading ? '...' : tracking ? 'Stop' : 'Start Tracking'}
            </Text>
          </TouchableOpacity>
        </View>

        {/* Live stats */}
        <View style={styles.trackingStats}>
          <View style={styles.trackingStatItem}>
            <Text style={styles.trackingStatLabel}>Today</Text>
            <Text style={styles.trackingStatValue}>{todayMiles.toFixed(1)} mi</Text>
          </View>
          <View style={styles.trackingStatDivider} />
          <View style={styles.trackingStatItem}>
            <Text style={styles.trackingStatLabel}>Current State</Text>
            <Text style={styles.trackingStatValue}>
              {currentState
                ? `${currentState} · ${getStateName(currentState)}`
                : '—'}
            </Text>
          </View>
        </View>

        {/* EAS-only notice */}
        {!tracking && (
          <Text style={styles.trackingNotice}>
            Requires EAS Build — not available in Expo Go
          </Text>
        )}
      </View>

      {/* Quarter selection */}
      <View style={styles.selectorSection}>
        {/* Year */}
        <View style={styles.yearRow}>
          <TouchableOpacity onPress={() => handleYearChange(-1)} style={styles.yearBtn}>
            <Ionicons name="chevron-back" size={18} color={COLORS.primary} />
          </TouchableOpacity>
          <Text style={styles.yearText}>{year}</Text>
          <TouchableOpacity onPress={() => handleYearChange(1)} style={styles.yearBtn}>
            <Ionicons name="chevron-forward" size={18} color={COLORS.primary} />
          </TouchableOpacity>
        </View>

        {/* Quarters */}
        <View style={styles.quarterRow}>
          {QUARTERS.map((q) => (
            <TouchableOpacity
              key={q}
              style={[styles.quarterBtn, quarter === q && styles.quarterBtnActive]}
              onPress={() => handleQuarterChange(q)}
            >
              <Text style={[styles.quarterBtnText, quarter === q && styles.quarterBtnTextActive]}>
                Q{q}
              </Text>
            </TouchableOpacity>
          ))}
        </View>
      </View>

      {/* Loading */}
      {loading && (
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={COLORS.accent} />
          <Text style={styles.loadingText}>Calculating IFTA...</Text>
        </View>
      )}

      {/* Data */}
      {!loading && data && (
        <>
          {/* Summary card */}
          <View style={[styles.totalCard, isRefund ? styles.totalCardRefund : styles.totalCardDue]}>
            <Text style={[styles.totalCardLabel, isRefund ? styles.refundText : styles.dueText]}>
              {isRefund ? 'REFUND' : 'AMOUNT DUE'}
            </Text>
            <Text style={[styles.totalCardAmount, isRefund ? styles.refundText : styles.dueText]}>
              ${Math.abs(totalDue).toFixed(2)}
            </Text>
            <Text style={styles.totalCardSub}>
              Q{data.quarter} {data.year} • {data.total_trips} trips • {data.total_miles} mi • {data.avg_mpg} MPG
            </Text>
          </View>

          {/* State breakdown table */}
          {data.states && data.states.length > 0 ? (
            <View style={styles.tableCard}>
              <Text style={styles.tableTitle}>State breakdown</Text>

              {/* Table header */}
              <View style={styles.tableHeader}>
                <Text style={[styles.thCell, { flex: 0.7 }]}>State</Text>
                <Text style={[styles.thCell, { flex: 1 }]}>Miles</Text>
                <Text style={[styles.thCell, { flex: 1 }]}>Used</Text>
                <Text style={[styles.thCell, { flex: 1 }]}>Purchased</Text>
                <Text style={[styles.thCell, { flex: 0.9, textAlign: 'right' }]}>Net $</Text>
              </View>

              {/* Rows */}
              {data.states.map((s) => (
                <View key={s.state} style={styles.tableRow}>
                  <Text style={[styles.tdState, { flex: 0.7 }]}>{s.state}</Text>
                  <Text style={[styles.tdCell, { flex: 1 }]}>{s.total_miles}</Text>
                  <Text style={[styles.tdCell, { flex: 1 }]}>{s.consumed_gallons}</Text>
                  <Text style={[styles.tdCell, { flex: 1, color: COLORS.success }]}>
                    {s.purchased_gallons > 0 ? s.purchased_gallons : '—'}
                  </Text>
                  <Text style={[
                    styles.tdNet,
                    { flex: 0.9, textAlign: 'right' },
                    s.refund ? styles.refundText : styles.dueText,
                  ]}>
                    {s.tax_due >= 0 ? '+' : ''}{s.tax_due.toFixed(2)}
                  </Text>
                </View>
              ))}

              {/* Table total */}
              <View style={styles.tableTotalRow}>
                <Text style={[styles.tableTotalLabel, { flex: 2.7 }]}>TOTAL</Text>
                <Text style={[styles.tableTotalLabel, { flex: 1 }]}>{data.total_miles}</Text>
                <Text style={[styles.tableTotalLabel, { flex: 0.9 }]}></Text>
                <Text style={[
                  styles.tableTotalAmount,
                  { flex: 0.9, textAlign: 'right' },
                  isRefund ? styles.refundText : styles.dueText,
                ]}>
                  ${totalDue.toFixed(2)}
                </Text>
              </View>
            </View>
          ) : (
            <View style={styles.emptyCard}>
              <Ionicons name="document-text-outline" size={40} color={COLORS.textMuted} />
              <Text style={styles.emptyText}>No data for Q{quarter} {year}</Text>
              <Text style={styles.emptySub}>Calculate a route or add fuel purchases</Text>
            </View>
          )}

          {/* Legend */}
          <View style={styles.legend}>
            <View style={styles.legendItem}>
              <View style={[styles.legendDot, { backgroundColor: COLORS.error }]} />
              <Text style={styles.legendText}>Red — amount due to state</Text>
            </View>
            <View style={styles.legendItem}>
              <View style={[styles.legendDot, { backgroundColor: COLORS.success }]} />
              <Text style={styles.legendText}>Green — refund from state</Text>
            </View>
          </View>

          {/* Export buttons */}
          {data.states && data.states.length > 0 && (
            <View style={styles.exportRow}>
              <TouchableOpacity
                style={[styles.exportBtn, styles.exportBtnPdf, exportingPdf && styles.exportBtnDisabled]}
                onPress={exportPDF}
                disabled={exportingPdf || exporting}
              >
                {exportingPdf
                  ? <ActivityIndicator size="small" color={COLORS.textInverse} />
                  : <Ionicons name="document-text-outline" size={18} color={COLORS.textInverse} />
                }
                <Text style={styles.exportBtnTextPdf}>
                  {exportingPdf ? 'PDF...' : 'PDF Report'}
                </Text>
              </TouchableOpacity>

              <TouchableOpacity
                style={[styles.exportBtn, styles.exportBtnCsv, exporting && styles.exportBtnDisabled]}
                onPress={exportCSV}
                disabled={exporting || exportingPdf}
              >
                {exporting
                  ? <ActivityIndicator size="small" color={COLORS.primary} />
                  : <Ionicons name="download-outline" size={18} color={COLORS.primary} />
                }
                <Text style={styles.exportBtnText}>
                  {exporting ? 'CSV...' : 'Export CSV'}
                </Text>
              </TouchableOpacity>
            </View>
          )}
        </>
      )}

      {/* No data after loading */}
      {!loading && !data && (
        <View style={styles.emptyCard}>
          <Ionicons name="analytics-outline" size={48} color={COLORS.textMuted} />
          <Text style={styles.emptyText}>No data</Text>
          <TouchableOpacity style={styles.retryBtn} onPress={() => loadIFTA()}>
            <Text style={styles.retryText}>Retry</Text>
          </TouchableOpacity>
        </View>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.bg },
  scroll: { padding: SPACING.md, paddingBottom: 40 },

  title: { color: COLORS.textPrimary, fontSize: 22, fontWeight: '800', marginBottom: SPACING.md },

  // Selector
  selectorSection: { marginBottom: SPACING.md },
  yearRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 12,
    gap: SPACING.md,
  },
  yearBtn: {
    padding: SPACING.sm,
    borderRadius: RADIUS.sm,
    borderWidth: 1,
    borderColor: COLORS.border,
    backgroundColor: COLORS.primaryLight,
  },
  yearText: { color: COLORS.textPrimary, fontSize: 20, fontWeight: '800', minWidth: 60, textAlign: 'center' },
  quarterRow: { flexDirection: 'row', gap: 10 },
  quarterBtn: {
    flex: 1,
    paddingVertical: 12,
    borderRadius: 10,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: COLORS.bgCardAlt,
    backgroundColor: COLORS.bgCard,
  },
  quarterBtnActive: { backgroundColor: COLORS.primaryLight, borderColor: COLORS.primary },
  quarterBtnText: { color: COLORS.textMuted, fontSize: 14, fontWeight: '700' },
  quarterBtnTextActive: { color: COLORS.primary },

  // Loading
  loadingContainer: { alignItems: 'center', paddingVertical: 40 },
  loadingText: { color: COLORS.textMuted, fontSize: 14, marginTop: 12 },

  // Total card
  totalCard: {
    borderRadius: 14,
    padding: SPACING.lg,
    alignItems: 'center',
    marginBottom: 14,
    borderWidth: 2,
  },
  totalCardDue: { backgroundColor: COLORS.errorLight, borderColor: COLORS.error },
  totalCardRefund: { backgroundColor: COLORS.successLight, borderColor: COLORS.success },
  totalCardLabel: { fontSize: 11, fontWeight: '800', letterSpacing: 2, marginBottom: SPACING.sm },
  totalCardAmount: { fontSize: 52, fontWeight: '900', letterSpacing: -1 },
  totalCardSub: { color: COLORS.textMuted, fontSize: 12, marginTop: SPACING.sm, textAlign: 'center' },
  dueText: { color: COLORS.error },
  refundText: { color: COLORS.success },

  // Table
  tableCard: {
    backgroundColor: COLORS.bgCard,
    borderRadius: 14,
    padding: SPACING.md,
    marginBottom: 14,
    borderWidth: 1,
    borderColor: COLORS.bgCardAlt,
  },
  tableTitle: { color: COLORS.textSecondary, fontSize: 11, fontWeight: '700', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 12 },
  tableHeader: {
    flexDirection: 'row',
    paddingBottom: SPACING.sm,
    borderBottomWidth: 1,
    borderBottomColor: COLORS.border,
    marginBottom: SPACING.xs,
  },
  thCell: { color: COLORS.textMuted, fontSize: 10, fontWeight: '700', textTransform: 'uppercase' },
  tableRow: {
    flexDirection: 'row',
    paddingVertical: 9,
    borderBottomWidth: 1,
    borderBottomColor: COLORS.borderLight,
    alignItems: 'center',
  },
  tdState: { color: COLORS.textPrimary, fontSize: 14, fontWeight: '700' },
  tdCell: { color: COLORS.textMuted, fontSize: 12 },
  tdNet: { fontSize: 12, fontWeight: '700' },
  tableTotalRow: {
    flexDirection: 'row',
    paddingTop: 10,
    marginTop: SPACING.xs,
    alignItems: 'center',
    borderTopWidth: 1,
    borderTopColor: COLORS.border,
  },
  tableTotalLabel: { color: COLORS.textSecondary, fontSize: 11, fontWeight: '700' },
  tableTotalAmount: { fontSize: 14, fontWeight: '900' },

  // Empty
  emptyCard: {
    backgroundColor: COLORS.bgCard,
    borderRadius: 14,
    padding: 32,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: COLORS.bgCardAlt,
    marginBottom: 14,
  },
  emptyText: { color: COLORS.textMuted, fontSize: 15, fontWeight: '700', marginTop: 12 },
  emptySub: { color: COLORS.textMuted, fontSize: 12, marginTop: 6, textAlign: 'center' },
  retryBtn: {
    marginTop: SPACING.md,
    paddingHorizontal: 20,
    paddingVertical: 10,
    borderRadius: RADIUS.sm,
    borderWidth: 1,
    borderColor: COLORS.primary,
  },
  retryText: { color: COLORS.primary, fontSize: 13, fontWeight: '700' },

  // Legend
  legend: {
    gap: SPACING.sm,
    marginBottom: SPACING.md,
    paddingHorizontal: SPACING.xs,
  },
  legendItem: { flexDirection: 'row', alignItems: 'center', gap: SPACING.sm },
  legendDot: { width: 10, height: 10, borderRadius: 5 },
  legendText: { color: COLORS.textMuted, fontSize: 12 },

  // Export
  exportRow: {
    flexDirection: 'row',
    gap: 10,
    marginBottom: SPACING.xs,
  },
  exportBtn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: SPACING.sm,
    paddingVertical: 14,
    borderRadius: RADIUS.md,
  },
  exportBtnPdf: {
    backgroundColor: COLORS.accent,
  },
  exportBtnCsv: {
    borderWidth: 1,
    borderColor: COLORS.primary,
    backgroundColor: COLORS.primaryLight,
  },
  exportBtnDisabled: { opacity: 0.5 },
  exportBtnText: { color: COLORS.primary, fontSize: 14, fontWeight: '700' },
  exportBtnTextPdf: { color: COLORS.textInverse, fontSize: 14, fontWeight: '700' },

  // GPS Tracking Card
  trackingCard: {
    borderRadius: 14,
    padding: SPACING.md,
    marginBottom: SPACING.md,
    borderWidth: 1,
  },
  trackingCardActive: {
    backgroundColor: COLORS.successLight,
    borderColor: COLORS.success,
  },
  trackingCardIdle: {
    backgroundColor: COLORS.bgCard,
    borderColor: COLORS.bgCardAlt,
  },
  trackingRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 14,
  },
  trackingStatusLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: SPACING.sm,
  },
  trackingDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
  },
  trackingStatusText: {
    fontSize: 13,
    fontWeight: '700',
  },
  trackingBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingVertical: SPACING.sm,
    paddingHorizontal: 14,
    borderRadius: 10,
  },
  trackingBtnStart: {
    backgroundColor: COLORS.accent,
  },
  trackingBtnStop: {
    backgroundColor: COLORS.error,
  },
  trackingBtnText: {
    color: COLORS.textInverse,
    fontSize: 13,
    fontWeight: '700',
  },
  trackingStats: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  trackingStatItem: {
    flex: 1,
  },
  trackingStatDivider: {
    width: 1,
    height: 32,
    backgroundColor: COLORS.bgCardAlt,
    marginHorizontal: SPACING.md,
  },
  trackingStatLabel: {
    color: COLORS.textMuted,
    fontSize: 10,
    fontWeight: '700',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginBottom: 3,
  },
  trackingStatValue: {
    color: COLORS.textPrimary,
    fontSize: 14,
    fontWeight: '700',
  },
  trackingNotice: {
    color: COLORS.textMuted,
    fontSize: 10,
    marginTop: 12,
    textAlign: 'center',
    fontStyle: 'italic',
  },
});
