import React, { useState, useEffect } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity, Alert
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { getToken } from '../services/auth';
import api from '../services/api';

// IFTA Diesel Tax Rates ($ per gallon, 2026)
const IFTA_RATES = {
  AL: 0.290, AK: 0.0895, AZ: 0.260, AR: 0.285, CA: 0.883,
  CO: 0.205, CT: 0.401, DE: 0.220, FL: 0.350, GA: 0.320,
  ID: 0.320, IL: 0.467, IN: 0.530, IA: 0.325, KS: 0.260,
  KY: 0.216, LA: 0.200, ME: 0.319, MD: 0.358, MA: 0.240,
  MI: 0.470, MN: 0.285, MS: 0.180, MO: 0.170, MT: 0.278,
  NE: 0.278, NV: 0.295, NH: 0.222, NJ: 0.415, NM: 0.210,
  NY: 0.449, NC: 0.375, ND: 0.230, OH: 0.470, OK: 0.190,
  OR: 0.384, PA: 0.745, RI: 0.340, SC: 0.220, SD: 0.280,
  TN: 0.217, TX: 0.200, UT: 0.315, VT: 0.320, VA: 0.274,
  WA: 0.494, WV: 0.358, WI: 0.329, WY: 0.240,
};

function calcFuelData(distanceMiles, mpg, fuelPrice, breakdown) {
  const totalGallons = distanceMiles / mpg;
  const totalFuelCost = totalGallons * fuelPrice;

  const stateBreakdown = (breakdown || []).map(b => {
    const gallons = b.miles_in_state / mpg;
    const fuelCost = gallons * fuelPrice;
    const iftaRate = IFTA_RATES[b.state] || 0;
    const iftaTax = gallons * iftaRate;
    return {
      state: b.state,
      miles: b.miles_in_state,
      gallons: gallons.toFixed(2),
      fuelCost: fuelCost.toFixed(2),
      iftaRate: iftaRate.toFixed(3),
      iftaTax: iftaTax.toFixed(2),
    };
  });

  const totalIftaTax = stateBreakdown.reduce((sum, s) => sum + parseFloat(s.iftaTax), 0);

  return {
    totalGallons: totalGallons.toFixed(1),
    totalFuelCost: totalFuelCost.toFixed(2),
    totalIftaTax: totalIftaTax.toFixed(2),
    stateBreakdown,
  };
}

export default function ResultScreen({ route, navigation }) {
  const { result, from, to, truckType, fuelData } = route.params;
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);
  const [showIftaDetail, setShowIftaDetail] = useState(false);

  useEffect(() => {
    getToken().then((token) => setIsLoggedIn(!!token));
  }, []);

  const tollCost = result.total || 0;
  const totalFormatted = tollCost.toFixed(2);
  const truckLabel = {
    '2-axle': '2 оси', '3-axle': '3 оси', '5-axle': '5 осей',
    '2axle': '2 оси', '3axle': '3 оси', '5axle': '5 осей',
  }[truckType] || truckType;

  // Fuel calculations
  const fuel = fuelData
    ? calcFuelData(result.distance_miles, fuelData.mpg, fuelData.fuelPrice, result.breakdown)
    : null;

  const grandTotal = fuel
    ? (tollCost + parseFloat(fuel.totalFuelCost)).toFixed(2)
    : null;

  const handleSave = async () => {
    if (saving || saved) return;
    setSaving(true);
    try {
      await api.post('/api/tolls/history', {
        from_city: from,
        to_city: to,
        truck_type: truckType,
        total_toll: result.total,
        distance_miles: result.distance_miles,
      });
      setSaved(true);
      Alert.alert('Сохранено', 'Маршрут добавлен в историю');
    } catch (err) {
      Alert.alert('Ошибка', err.response?.data?.error || 'Не удалось сохранить маршрут');
    } finally {
      setSaving(false);
    }
  };

  // Recommendations
  const recommendations = [];
  if (result.breakdown) {
    const states = result.breakdown.map((b) => b.state);
    const hasNortheast = states.some((s) =>
      ['NY', 'NJ', 'PA', 'MA', 'CT', 'RI', 'NH', 'VT', 'ME', 'MD', 'DE'].includes(s)
    );
    if (hasNortheast) {
      recommendations.push({ icon: '💳', text: 'E-ZPass охватывает этот маршрут — экономия до 30% на сборах' });
    }
    if (states.includes('TX')) {
      recommendations.push({ icon: '⭐', text: 'TxTag или EZ TAG даёт скидку на все платные дороги Техаса' });
    }
    // Cheapest fuel states
    const cheapFuelStates = states.filter(s => ['MT', 'NH', 'OR', 'WY', 'MS', 'MO'].includes(s));
    if (cheapFuelStates.length > 0) {
      recommendations.push({ icon: '⛽', text: `Заправляйся в ${cheapFuelStates.join(', ')} — низкий налог на топливо` });
    }
  }
  if (truckType === '5-axle' || truckType === '5axle') {
    recommendations.push({ icon: '🚛', text: '5-осный — максимальная нагрузка. 3-осный может быть дешевле для небольших грузов' });
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.scroll}>
      {/* Route header */}
      <View style={styles.routeCard}>
        <View style={styles.routeRow}>
          <View style={styles.cityBlock}>
            <Text style={styles.cityLabel}>ОТКУДА</Text>
            <Text style={styles.cityName}>{from}</Text>
          </View>
          <Ionicons name="arrow-forward" size={24} color="#4fc3f7" />
          <View style={styles.cityBlock}>
            <Text style={styles.cityLabel}>КУДА</Text>
            <Text style={styles.cityName}>{to}</Text>
          </View>
        </View>
        <Text style={styles.truckInfo}>🚛 {truckLabel} • {result.distance_miles} миль</Text>
      </View>

      {/* GRAND TOTAL (if fuel included) */}
      {fuel && grandTotal && (
        <View style={styles.grandTotalCard}>
          <Text style={styles.grandTotalLabel}>💰 ИТОГО РЕЙС</Text>
          <Text style={styles.grandTotalAmount}>${grandTotal}</Text>
          <Text style={styles.grandTotalSub}>толлы + топливо • {result.distance_miles} миль</Text>
          {/* Breakdown row */}
          <View style={styles.grandBreakRow}>
            <View style={styles.grandBreakItem}>
              <Text style={styles.grandBreakLabel}>🛣️ Толлы</Text>
              <Text style={styles.grandBreakValue}>${totalFormatted}</Text>
            </View>
            <View style={styles.grandBreakDivider} />
            <View style={styles.grandBreakItem}>
              <Text style={styles.grandBreakLabel}>⛽ Топливо</Text>
              <Text style={styles.grandBreakValue}>${fuel.totalFuelCost}</Text>
            </View>
            <View style={styles.grandBreakDivider} />
            <View style={styles.grandBreakItem}>
              <Text style={styles.grandBreakLabel}>🏛️ IFTA</Text>
              <Text style={styles.grandBreakValue}>${fuel.totalIftaTax}</Text>
            </View>
          </View>
        </View>
      )}

      {/* Toll Cost (always shown) */}
      {!fuel && (
        <View style={styles.totalCard}>
          <Text style={styles.totalLabel}>Итого платных дорог</Text>
          <Text style={styles.totalAmount}>${totalFormatted}</Text>
          <Text style={styles.totalSub}>по данным 2026</Text>
        </View>
      )}

      {/* Fuel Summary Card */}
      {fuel && (
        <View style={styles.fuelSummaryCard}>
          <Text style={styles.fuelSummaryTitle}>⛽ Топливо — детали</Text>
          <View style={styles.fuelSummaryRow}>
            <Text style={styles.fuelSummaryKey}>Расход топлива:</Text>
            <Text style={styles.fuelSummaryVal}>{fuel.totalGallons} галлонов</Text>
          </View>
          <View style={styles.fuelSummaryRow}>
            <Text style={styles.fuelSummaryKey}>Цена дизеля:</Text>
            <Text style={styles.fuelSummaryVal}>${fuelData.fuelPrice}/галлон</Text>
          </View>
          <View style={styles.fuelSummaryRow}>
            <Text style={styles.fuelSummaryKey}>Расход (MPG):</Text>
            <Text style={styles.fuelSummaryVal}>{fuelData.mpg} MPG</Text>
          </View>
          <View style={[styles.fuelSummaryRow, styles.fuelSummaryTotal]}>
            <Text style={styles.fuelSummaryTotalKey}>Стоимость топлива:</Text>
            <Text style={styles.fuelSummaryTotalVal}>${fuel.totalFuelCost}</Text>
          </View>
        </View>
      )}

      {/* Action buttons */}
      <View style={styles.actionsRow}>
        {isLoggedIn && (
          <TouchableOpacity
            style={[styles.actionBtn, saved && styles.actionBtnSaved]}
            onPress={handleSave}
            disabled={saving || saved}
          >
            <Ionicons name={saved ? 'checkmark-circle' : 'bookmark-outline'} size={18} color={saved ? '#81c784' : '#4fc3f7'} />
            <Text style={[styles.actionBtnText, saved && styles.actionBtnTextSaved]}>
              {saving ? 'Сохраняем...' : saved ? 'Сохранено' : 'Сохранить'}
            </Text>
          </TouchableOpacity>
        )}
        <TouchableOpacity
          style={styles.actionBtn}
          onPress={() => navigation.navigate('Map', { from, to, total: result.total })}
        >
          <Ionicons name="map-outline" size={18} color="#4fc3f7" />
          <Text style={styles.actionBtnText}>Карта 🗺️</Text>
        </TouchableOpacity>
      </View>

      {/* IFTA Breakdown */}
      {fuel && fuel.stateBreakdown.length > 0 && (
        <View style={styles.card}>
          <TouchableOpacity
            style={styles.iftaHeader}
            onPress={() => setShowIftaDetail(!showIftaDetail)}
          >
            <Text style={styles.sectionTitle}>🏛️ IFTA — разбивка по штатам</Text>
            <View style={styles.iftaBadge}>
              <Text style={styles.iftaBadgeText}>ИТОГО: ${fuel.totalIftaTax}</Text>
            </View>
            <Ionicons
              name={showIftaDetail ? 'chevron-up' : 'chevron-down'}
              size={16}
              color="#888"
            />
          </TouchableOpacity>

          {showIftaDetail && (
            <>
              <View style={styles.iftaTableHeader}>
                <Text style={[styles.iftaCol, { flex: 0.8 }]}>Штат</Text>
                <Text style={[styles.iftaCol, { flex: 1 }]}>Мили</Text>
                <Text style={[styles.iftaCol, { flex: 1 }]}>Галлоны</Text>
                <Text style={[styles.iftaCol, { flex: 1 }]}>Ставка</Text>
                <Text style={[styles.iftaCol, { flex: 1, textAlign: 'right' }]}>Налог</Text>
              </View>
              {fuel.stateBreakdown.map((s, i) => (
                <View key={i} style={styles.iftaRow}>
                  <Text style={[styles.iftaState, { flex: 0.8 }]}>{s.state}</Text>
                  <Text style={[styles.iftaData, { flex: 1 }]}>{s.miles}</Text>
                  <Text style={[styles.iftaData, { flex: 1 }]}>{s.gallons}</Text>
                  <Text style={[styles.iftaData, { flex: 1 }]}>${s.iftaRate}</Text>
                  <Text style={[styles.iftaCost, { flex: 1, textAlign: 'right' }]}>${s.iftaTax}</Text>
                </View>
              ))}
              <View style={styles.iftaNote}>
                <Text style={styles.iftaNoteText}>
                  * IFTA — это квартальный отчёт по топливным налогам между штатами.
                  Сумма показывает приблизительный налог, не учитывая заправки в штатах.
                </Text>
              </View>
            </>
          )}

          {!showIftaDetail && (
            <Text style={styles.iftaExpandHint}>
              Нажми чтобы увидеть разбивку по {fuel.stateBreakdown.length} штатам
            </Text>
          )}
        </View>
      )}

      {/* Toll Breakdown by state */}
      {result.breakdown && result.breakdown.length > 0 && (
        <View style={styles.card}>
          <Text style={styles.sectionTitle}>🛣️ Толлы — разбивка по штатам</Text>
          {result.breakdown.map((b, i) => (
            <View key={i} style={styles.breakdownRow}>
              <View>
                <Text style={styles.stateCode}>{b.state}</Text>
                <Text style={styles.stateMiles}>{b.miles_in_state} миль • {b.roads} дороги</Text>
              </View>
              <Text style={styles.stateCost}>
                ${((result.total / result.distance_miles) * b.miles_in_state).toFixed(2)}
              </Text>
            </View>
          ))}
        </View>
      )}

      {/* Recommendations */}
      {recommendations.length > 0 && (
        <View style={styles.card}>
          <Text style={styles.sectionTitle}>🎯 Рекомендации</Text>
          {recommendations.map((r, i) => (
            <View key={i} style={styles.recRow}>
              <Text style={styles.recIcon}>{r.icon}</Text>
              <Text style={styles.recText}>{r.text}</Text>
            </View>
          ))}
        </View>
      )}

      {/* Tips */}
      <View style={styles.card}>
        <Text style={styles.sectionTitle}>💡 Советы</Text>
        <Text style={styles.tipText}>• E-ZPass экономит до 30% на большинстве платных дорог северо-востока</Text>
        <Text style={styles.tipText}>• IFTA отчёт сдаётся раз в квартал — экономь на бухгалтере с этими данными</Text>
        <Text style={styles.tipText}>• Маршрут рассчитан для {truckLabel.toLowerCase()}</Text>
        {fuel && <Text style={styles.tipText}>• Заправляйся в MO, MS, OK — ставка IFTA от $0.17/галлон</Text>}
      </View>

      {/* Back button */}
      <TouchableOpacity style={styles.backBtn} onPress={() => navigation.goBack()}>
        <Ionicons name="arrow-back" size={18} color="#4fc3f7" />
        <Text style={styles.backBtnText}>Новый расчёт</Text>
      </TouchableOpacity>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0d0d1a' },
  scroll: { padding: 20, paddingBottom: 40 },
  routeCard: {
    backgroundColor: '#161629',
    borderRadius: 14,
    padding: 20,
    marginBottom: 14,
    borderWidth: 1,
    borderColor: '#1e1e3a',
  },
  routeRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 },
  cityBlock: { flex: 1 },
  cityLabel: { color: '#555', fontSize: 10, fontWeight: '700', letterSpacing: 1, marginBottom: 4 },
  cityName: { color: '#fff', fontSize: 15, fontWeight: '700' },
  truckInfo: { color: '#888', fontSize: 13, textAlign: 'center' },

  // Grand Total Card
  grandTotalCard: {
    backgroundColor: '#0a2010',
    borderRadius: 14,
    padding: 24,
    alignItems: 'center',
    marginBottom: 14,
    borderWidth: 2,
    borderColor: '#81c784',
  },
  grandTotalLabel: { color: '#81c784', fontSize: 12, fontWeight: '800', letterSpacing: 2, marginBottom: 8 },
  grandTotalAmount: { color: '#fff', fontSize: 56, fontWeight: '900', letterSpacing: -2 },
  grandTotalSub: { color: '#555', fontSize: 12, marginTop: 4, marginBottom: 16 },
  grandBreakRow: {
    flexDirection: 'row',
    width: '100%',
    justifyContent: 'space-around',
    borderTopWidth: 1,
    borderTopColor: '#1a3020',
    paddingTop: 14,
  },
  grandBreakItem: { alignItems: 'center', flex: 1 },
  grandBreakDivider: { width: 1, backgroundColor: '#1a3020' },
  grandBreakLabel: { color: '#666', fontSize: 11, marginBottom: 4 },
  grandBreakValue: { color: '#81c784', fontSize: 16, fontWeight: '800' },

  // Toll total card (no fuel mode)
  totalCard: {
    backgroundColor: '#0a1f2e',
    borderRadius: 14,
    padding: 28,
    alignItems: 'center',
    marginBottom: 14,
    borderWidth: 1,
    borderColor: '#4fc3f7',
  },
  totalLabel: { color: '#4fc3f7', fontSize: 13, fontWeight: '600', marginBottom: 8 },
  totalAmount: { color: '#fff', fontSize: 52, fontWeight: '900', letterSpacing: -1 },
  totalSub: { color: '#555', fontSize: 12, marginTop: 4 },

  // Fuel summary
  fuelSummaryCard: {
    backgroundColor: '#0a1520',
    borderRadius: 14,
    padding: 16,
    marginBottom: 14,
    borderWidth: 1,
    borderColor: '#2a4a5a',
  },
  fuelSummaryTitle: { color: '#4fc3f7', fontSize: 13, fontWeight: '700', marginBottom: 12 },
  fuelSummaryRow: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 8 },
  fuelSummaryKey: { color: '#777', fontSize: 13 },
  fuelSummaryVal: { color: '#aaa', fontSize: 13, fontWeight: '600' },
  fuelSummaryTotal: { borderTopWidth: 1, borderTopColor: '#1a3040', paddingTop: 10, marginTop: 4 },
  fuelSummaryTotalKey: { color: '#4fc3f7', fontSize: 14, fontWeight: '700' },
  fuelSummaryTotalVal: { color: '#4fc3f7', fontSize: 18, fontWeight: '900' },

  // Actions
  actionsRow: { flexDirection: 'row', gap: 10, marginBottom: 14 },
  actionBtn: {
    flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    gap: 8, paddingVertical: 12, borderRadius: 12,
    borderWidth: 1, borderColor: '#4fc3f7', backgroundColor: '#0a1f2e',
  },
  actionBtnSaved: { borderColor: '#81c784', backgroundColor: '#0a1f0e' },
  actionBtnText: { color: '#4fc3f7', fontSize: 13, fontWeight: '700' },
  actionBtnTextSaved: { color: '#81c784' },

  // IFTA
  card: {
    backgroundColor: '#161629', borderRadius: 14, padding: 18,
    marginBottom: 14, borderWidth: 1, borderColor: '#1e1e3a',
  },
  iftaHeader: {
    flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 4,
  },
  iftaBadge: {
    backgroundColor: '#1a2a1a', borderRadius: 8, paddingHorizontal: 8, paddingVertical: 3,
    borderWidth: 1, borderColor: '#2a4a2a', marginLeft: 'auto',
  },
  iftaBadgeText: { color: '#81c784', fontSize: 11, fontWeight: '800' },
  iftaExpandHint: { color: '#444', fontSize: 12, textAlign: 'center', marginTop: 8 },
  iftaTableHeader: {
    flexDirection: 'row', marginTop: 12, marginBottom: 6,
    borderBottomWidth: 1, borderBottomColor: '#2a2a4a', paddingBottom: 6,
  },
  iftaCol: { color: '#555', fontSize: 11, fontWeight: '700', textTransform: 'uppercase' },
  iftaRow: {
    flexDirection: 'row', paddingVertical: 8,
    borderBottomWidth: 1, borderBottomColor: '#1a1a2a', alignItems: 'center',
  },
  iftaState: { color: '#fff', fontSize: 14, fontWeight: '700' },
  iftaData: { color: '#666', fontSize: 13 },
  iftaCost: { color: '#81c784', fontSize: 13, fontWeight: '700' },
  iftaNote: { marginTop: 12, padding: 10, backgroundColor: '#0d1a0d', borderRadius: 8 },
  iftaNoteText: { color: '#555', fontSize: 11, lineHeight: 16 },

  sectionTitle: { color: '#888', fontSize: 12, fontWeight: '700', marginBottom: 14, textTransform: 'uppercase', letterSpacing: 0.5 },
  breakdownRow: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: '#1a1a2e',
  },
  stateCode: { color: '#fff', fontSize: 16, fontWeight: '700' },
  stateMiles: { color: '#666', fontSize: 12, marginTop: 2 },
  stateCost: { color: '#4fc3f7', fontSize: 16, fontWeight: '700' },
  recRow: { flexDirection: 'row', alignItems: 'flex-start', gap: 10, marginBottom: 10 },
  recIcon: { fontSize: 16, marginTop: 1 },
  recText: { flex: 1, color: '#aaa', fontSize: 13, lineHeight: 20 },
  tipText: { color: '#666', fontSize: 13, marginBottom: 8, lineHeight: 20 },
  backBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    gap: 8, padding: 16, borderRadius: 14,
    borderWidth: 1, borderColor: '#4fc3f7', marginTop: 8,
  },
  backBtnText: { color: '#4fc3f7', fontSize: 15, fontWeight: '700' },
});
