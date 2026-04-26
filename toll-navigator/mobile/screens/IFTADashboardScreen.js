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
            <View style={[styles.trackingDot, { backgroundColor: tracking ? '#66bb6a' : '#ef5350' }]} />
            <Text style={[styles.trackingStatusText, { color: tracking ? '#66bb6a' : '#ef5350' }]}>
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
              <ActivityIndicator size="small" color="#fff" />
            ) : (
              <Ionicons
                name={tracking ? 'stop-circle-outline' : 'navigate-outline'}
                size={16}
                color="#fff"
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
            <Ionicons name="chevron-back" size={18} color="#4fc3f7" />
          </TouchableOpacity>
          <Text style={styles.yearText}>{year}</Text>
          <TouchableOpacity onPress={() => handleYearChange(1)} style={styles.yearBtn}>
            <Ionicons name="chevron-forward" size={18} color="#4fc3f7" />
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
          <ActivityIndicator size="large" color="#4fc3f7" />
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
                  <Text style={[styles.tdCell, { flex: 1, color: '#81c784' }]}>
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
              <Ionicons name="document-text-outline" size={40} color="#333" />
              <Text style={styles.emptyText}>No data for Q{quarter} {year}</Text>
              <Text style={styles.emptySub}>Calculate a route or add fuel purchases</Text>
            </View>
          )}

          {/* Legend */}
          <View style={styles.legend}>
            <View style={styles.legendItem}>
              <View style={[styles.legendDot, { backgroundColor: '#ef9a9a' }]} />
              <Text style={styles.legendText}>Red — amount due to state</Text>
            </View>
            <View style={styles.legendItem}>
              <View style={[styles.legendDot, { backgroundColor: '#81c784' }]} />
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
                  ? <ActivityIndicator size="small" color="#fff" />
                  : <Ionicons name="document-text-outline" size={18} color="#fff" />
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
                  ? <ActivityIndicator size="small" color="#4fc3f7" />
                  : <Ionicons name="download-outline" size={18} color="#4fc3f7" />
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
          <Ionicons name="analytics-outline" size={48} color="#333" />
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
  container: { flex: 1, backgroundColor: '#0d0d1a' },
  scroll: { padding: 16, paddingBottom: 40 },

  title: { color: '#fff', fontSize: 22, fontWeight: '800', marginBottom: 16 },

  // Selector
  selectorSection: { marginBottom: 16 },
  yearRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 12,
    gap: 16,
  },
  yearBtn: {
    padding: 8,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#1e3a50',
    backgroundColor: '#0a1520',
  },
  yearText: { color: '#fff', fontSize: 20, fontWeight: '800', minWidth: 60, textAlign: 'center' },
  quarterRow: { flexDirection: 'row', gap: 10 },
  quarterBtn: {
    flex: 1,
    paddingVertical: 12,
    borderRadius: 10,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: '#1e1e3a',
    backgroundColor: '#161629',
  },
  quarterBtnActive: { backgroundColor: '#0a1f2e', borderColor: '#4fc3f7' },
  quarterBtnText: { color: '#555', fontSize: 14, fontWeight: '700' },
  quarterBtnTextActive: { color: '#4fc3f7' },

  // Loading
  loadingContainer: { alignItems: 'center', paddingVertical: 40 },
  loadingText: { color: '#555', fontSize: 14, marginTop: 12 },

  // Total card
  totalCard: {
    borderRadius: 14,
    padding: 24,
    alignItems: 'center',
    marginBottom: 14,
    borderWidth: 2,
  },
  totalCardDue: { backgroundColor: '#1a0a0a', borderColor: '#ef9a9a' },
  totalCardRefund: { backgroundColor: '#0a1a0a', borderColor: '#81c784' },
  totalCardLabel: { fontSize: 11, fontWeight: '800', letterSpacing: 2, marginBottom: 8 },
  totalCardAmount: { fontSize: 52, fontWeight: '900', letterSpacing: -1 },
  totalCardSub: { color: '#555', fontSize: 12, marginTop: 8, textAlign: 'center' },
  dueText: { color: '#ef9a9a' },
  refundText: { color: '#81c784' },

  // Table
  tableCard: {
    backgroundColor: '#161629',
    borderRadius: 14,
    padding: 16,
    marginBottom: 14,
    borderWidth: 1,
    borderColor: '#1e1e3a',
  },
  tableTitle: { color: '#888', fontSize: 11, fontWeight: '700', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 12 },
  tableHeader: {
    flexDirection: 'row',
    paddingBottom: 8,
    borderBottomWidth: 1,
    borderBottomColor: '#2a2a4a',
    marginBottom: 4,
  },
  thCell: { color: '#444', fontSize: 10, fontWeight: '700', textTransform: 'uppercase' },
  tableRow: {
    flexDirection: 'row',
    paddingVertical: 9,
    borderBottomWidth: 1,
    borderBottomColor: '#1a1a2a',
    alignItems: 'center',
  },
  tdState: { color: '#fff', fontSize: 14, fontWeight: '700' },
  tdCell: { color: '#666', fontSize: 12 },
  tdNet: { fontSize: 12, fontWeight: '700' },
  tableTotalRow: {
    flexDirection: 'row',
    paddingTop: 10,
    marginTop: 4,
    alignItems: 'center',
    borderTopWidth: 1,
    borderTopColor: '#2a2a4a',
  },
  tableTotalLabel: { color: '#888', fontSize: 11, fontWeight: '700' },
  tableTotalAmount: { fontSize: 14, fontWeight: '900' },

  // Empty
  emptyCard: {
    backgroundColor: '#161629',
    borderRadius: 14,
    padding: 32,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: '#1e1e3a',
    marginBottom: 14,
  },
  emptyText: { color: '#555', fontSize: 15, fontWeight: '700', marginTop: 12 },
  emptySub: { color: '#333', fontSize: 12, marginTop: 6, textAlign: 'center' },
  retryBtn: {
    marginTop: 16,
    paddingHorizontal: 20,
    paddingVertical: 10,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#4fc3f7',
  },
  retryText: { color: '#4fc3f7', fontSize: 13, fontWeight: '700' },

  // Legend
  legend: {
    gap: 8,
    marginBottom: 16,
    paddingHorizontal: 4,
  },
  legendItem: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  legendDot: { width: 10, height: 10, borderRadius: 5 },
  legendText: { color: '#555', fontSize: 12 },

  // Export
  exportRow: {
    flexDirection: 'row',
    gap: 10,
    marginBottom: 4,
  },
  exportBtn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    paddingVertical: 14,
    borderRadius: 12,
  },
  exportBtnPdf: {
    backgroundColor: '#1565c0',
  },
  exportBtnCsv: {
    borderWidth: 1,
    borderColor: '#4fc3f7',
    backgroundColor: '#0a1520',
  },
  exportBtnDisabled: { opacity: 0.5 },
  exportBtnText: { color: '#4fc3f7', fontSize: 14, fontWeight: '700' },
  exportBtnTextPdf: { color: '#fff', fontSize: 14, fontWeight: '700' },

  // GPS Tracking Card
  trackingCard: {
    borderRadius: 14,
    padding: 16,
    marginBottom: 16,
    borderWidth: 1,
  },
  trackingCardActive: {
    backgroundColor: '#071a0f',
    borderColor: '#2e7d32',
  },
  trackingCardIdle: {
    backgroundColor: '#161629',
    borderColor: '#1e1e3a',
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
    gap: 8,
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
    paddingVertical: 8,
    paddingHorizontal: 14,
    borderRadius: 10,
  },
  trackingBtnStart: {
    backgroundColor: '#1565c0',
  },
  trackingBtnStop: {
    backgroundColor: '#b71c1c',
  },
  trackingBtnText: {
    color: '#fff',
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
    backgroundColor: '#1e1e3a',
    marginHorizontal: 16,
  },
  trackingStatLabel: {
    color: '#555',
    fontSize: 10,
    fontWeight: '700',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginBottom: 3,
  },
  trackingStatValue: {
    color: '#fff',
    fontSize: 14,
    fontWeight: '700',
  },
  trackingNotice: {
    color: '#333',
    fontSize: 10,
    marginTop: 12,
    textAlign: 'center',
    fontStyle: 'italic',
  },
});
