import React, { useState, useCallback } from 'react';
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

  const loadIFTA = useCallback(async (q = quarter, y = year) => {
    setLoading(true);
    try {
      const { data: res } = await api.get('/api/trips/ifta', { params: { quarter: q, year: y } });
      setData(res);
    } catch (err) {
      const msg = err.response?.data?.error || 'Не удалось загрузить IFTA данные';
      Alert.alert('Ошибка', msg);
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [quarter, year]);

  // Загружаем профиль один раз для PDF
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
      Alert.alert('Нет данных', 'Нечего экспортировать');
      return;
    }
    setExportingPdf(true);
    try {
      const html = generateIFTAPDF(data, driverInfo);
      const { uri } = await Print.printToFileAsync({
        html,
        base64: false,
      });

      // Переименовываем файл
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
        Alert.alert('PDF создан', `Сохранён: ${filename}`);
      }
    } catch (err) {
      Alert.alert('Ошибка PDF', err.message || 'Не удалось создать PDF');
      console.error('[IFTA PDF export]', err);
    } finally {
      setExportingPdf(false);
    }
  };

  const exportCSV = async () => {
    if (!data || !data.states || data.states.length === 0) {
      Alert.alert('Нет данных', 'Нечего экспортировать');
      return;
    }
    setExporting(true);

    try {
      // Формируем CSV
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
        Alert.alert('Файл создан', `Сохранён: ${filename}`);
      }
    } catch (err) {
      Alert.alert('Ошибка экспорта', err.message || 'Не удалось создать CSV');
      console.error('[IFTA export]', err);
    } finally {
      setExporting(false);
    }
  };

  const totalDue = data?.total_tax_due ?? 0;
  const isRefund = totalDue < 0;

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.scroll}>

      {/* Заголовок */}
      <Text style={styles.title}>IFTA Dashboard</Text>

      {/* Выбор квартала */}
      <View style={styles.selectorSection}>
        {/* Год */}
        <View style={styles.yearRow}>
          <TouchableOpacity onPress={() => handleYearChange(-1)} style={styles.yearBtn}>
            <Ionicons name="chevron-back" size={18} color="#4fc3f7" />
          </TouchableOpacity>
          <Text style={styles.yearText}>{year}</Text>
          <TouchableOpacity onPress={() => handleYearChange(1)} style={styles.yearBtn}>
            <Ionicons name="chevron-forward" size={18} color="#4fc3f7" />
          </TouchableOpacity>
        </View>

        {/* Кварталы */}
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
          <Text style={styles.loadingText}>Считаем IFTA...</Text>
        </View>
      )}

      {/* Данные */}
      {!loading && data && (
        <>
          {/* Итоговая карточка */}
          <View style={[styles.totalCard, isRefund ? styles.totalCardRefund : styles.totalCardDue]}>
            <Text style={[styles.totalCardLabel, isRefund ? styles.refundText : styles.dueText]}>
              {isRefund ? 'ВОЗВРАТ' : 'К ДОПЛАТЕ'}
            </Text>
            <Text style={[styles.totalCardAmount, isRefund ? styles.refundText : styles.dueText]}>
              ${Math.abs(totalDue).toFixed(2)}
            </Text>
            <Text style={styles.totalCardSub}>
              Q{data.quarter} {data.year} • {data.total_trips} поездок • {data.total_miles} миль • {data.avg_mpg} MPG
            </Text>
          </View>

          {/* Таблица по штатам */}
          {data.states && data.states.length > 0 ? (
            <View style={styles.tableCard}>
              <Text style={styles.tableTitle}>Разбивка по штатам</Text>

              {/* Заголовок таблицы */}
              <View style={styles.tableHeader}>
                <Text style={[styles.thCell, { flex: 0.7 }]}>Штат</Text>
                <Text style={[styles.thCell, { flex: 1 }]}>Мили</Text>
                <Text style={[styles.thCell, { flex: 1 }]}>Потр.</Text>
                <Text style={[styles.thCell, { flex: 1 }]}>Куплено</Text>
                <Text style={[styles.thCell, { flex: 0.9, textAlign: 'right' }]}>Нетто $</Text>
              </View>

              {/* Строки */}
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

              {/* Итог таблицы */}
              <View style={styles.tableTotalRow}>
                <Text style={[styles.tableTotalLabel, { flex: 2.7 }]}>ИТОГО</Text>
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
              <Text style={styles.emptyText}>Нет данных за Q{quarter} {year}</Text>
              <Text style={styles.emptySub}>Рассчитай маршрут или добавь заправки</Text>
            </View>
          )}

          {/* Легенда */}
          <View style={styles.legend}>
            <View style={styles.legendItem}>
              <View style={[styles.legendDot, { backgroundColor: '#ef9a9a' }]} />
              <Text style={styles.legendText}>Красный — доплата штату</Text>
            </View>
            <View style={styles.legendItem}>
              <View style={[styles.legendDot, { backgroundColor: '#81c784' }]} />
              <Text style={styles.legendText}>Зелёный — возврат от штата</Text>
            </View>
          </View>

          {/* Кнопки экспорта */}
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

      {/* Нет данных после загрузки */}
      {!loading && !data && (
        <View style={styles.emptyCard}>
          <Ionicons name="analytics-outline" size={48} color="#333" />
          <Text style={styles.emptyText}>Нет данных</Text>
          <TouchableOpacity style={styles.retryBtn} onPress={() => loadIFTA()}>
            <Text style={styles.retryText}>Повторить</Text>
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
});
