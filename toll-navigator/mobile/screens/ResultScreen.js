import React, { useState, useEffect } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity, Alert
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { getToken } from '../services/auth';
import api from '../services/api';

// IFTA Diesel Tax Rates ($ per gallon, 2026)
// Синхронизировано с backend/src/routes/trips.js — единый источник правды на бэкенде
// NOTE: предпочтительно получать ставки с сервера (/api/trips/ifta), эти данные используются
// только для предварительного расчёта на экране результата до запроса к API.
const IFTA_RATES = {
  TX: 0.200, OK: 0.160, KS: 0.260, MO: 0.170, IL: 0.455,
  IN: 0.330, OH: 0.280, PA: 0.741, NY: 0.398, NJ: 0.175,
  VA: 0.162, NC: 0.361, TN: 0.170, GA: 0.326, FL: 0.359,
  AL: 0.190, MS: 0.180, AR: 0.225, LA: 0.200, CA: 0.824,
  AZ: 0.260, NV: 0.270, UT: 0.249, CO: 0.205, NM: 0.210,
  WY: 0.240, MT: 0.2775, ID: 0.320, WA: 0.494, OR: 0.340,
  AK: 0.0895, CT: 0.401, DE: 0.220, IA: 0.325, KY: 0.216,
  ME: 0.319, MD: 0.358, MA: 0.240, MI: 0.470, MN: 0.285,
  NE: 0.278, NH: 0.222, ND: 0.230, RI: 0.340, SC: 0.220,
  SD: 0.280, VT: 0.320, WV: 0.358, WI: 0.329,
};

// fuelPurchases: [{ state: 'TX', gallons: 100 }, ...]
// Если переданы — считаем полный IFTA (с зачётом купленных галлонов)
// Если нет — упрощённая формула (только потреблённые галлоны × ставка)
function calcFuelData(distanceMiles, mpg, fuelPrice, breakdown, fuelPurchases) {
  const totalGallons = distanceMiles / mpg;
  const totalFuelCost = totalGallons * fuelPrice;

  // Индекс купленных галлонов по штатам
  const purchasedByState = {};
  if (fuelPurchases && fuelPurchases.length > 0) {
    fuelPurchases.forEach(p => {
      if (p.state && p.gallons > 0) {
        purchasedByState[p.state] = (purchasedByState[p.state] || 0) + p.gallons;
      }
    });
  }
  const hasRealPurchases = Object.keys(purchasedByState).length > 0;

  const stateBreakdown = (breakdown || []).map(b => {
    const consumedGallons = b.miles_in_state / mpg;
    const fuelCost = consumedGallons * fuelPrice;
    const iftaRate = IFTA_RATES[b.state] || 0;

    let iftaTax;
    let purchasedInState = 0;
    if (hasRealPurchases) {
      // Полная формула IFTA:
      // Net Tax = (consumedGallons × rate) - (purchasedInState × rate)
      purchasedInState = purchasedByState[b.state] || 0;
      iftaTax = (consumedGallons - purchasedInState) * iftaRate;
    } else {
      // Упрощённая — только потреблённые галлоны
      iftaTax = consumedGallons * iftaRate;
    }

    return {
      state: b.state,
      miles: b.miles_in_state,
      gallons: consumedGallons.toFixed(2),
      purchasedGallons: purchasedInState > 0 ? purchasedInState.toFixed(2) : null,
      fuelCost: fuelCost.toFixed(2),
      iftaRate: iftaRate.toFixed(3),
      iftaTax: iftaTax.toFixed(2),
      iftaNetPositive: iftaTax >= 0, // true = доплата, false = возврат
    };
  });

  const totalIftaTax = stateBreakdown.reduce((sum, s) => sum + parseFloat(s.iftaTax), 0);

  return {
    totalGallons: totalGallons.toFixed(1),
    totalFuelCost: totalFuelCost.toFixed(2),
    totalIftaTax: totalIftaTax.toFixed(2),
    stateBreakdown,
    hasRealPurchases,
  };
}

// Авто-сохранение маршрута на сервер с индикатором статуса
// onStatus: (status: 'saving'|'saved'|'failed') => void
async function autoSaveTrip({ result, from, to, truckType, fuelData, fuelPurchases, onStatus }) {
  try {
    const token = await getToken();
    if (!token) return; // не авторизован — не сохраняем

    onStatus?.('saving');

    // Строим state_miles из breakdown
    const stateMiles = {};
    if (result.breakdown) {
      result.breakdown.forEach(b => {
        if (b.state && b.miles_in_state) {
          stateMiles[b.state] = b.miles_in_state;
        }
      });
    }

    const mpg = fuelData?.mpg || 6.5;
    const fuelPrice = fuelData?.fuelPrice || 0;
    const totalGallons = result.distance_miles ? result.distance_miles / mpg : 0;
    const fuelCost = totalGallons * fuelPrice;

    // Нормализуем fuel_purchases
    const normalizedPurchases = (fuelPurchases || []).map(p => ({
      state: p.state,
      gallons: p.gallons,
      price_per_gallon: p.price_per_gallon || fuelPrice || 0,
    }));

    await api.post('/api/trips', {
      from_city: from,
      to_city: to,
      truck_type: truckType,
      total_miles: result.distance_miles || 0,
      state_miles: stateMiles,
      toll_cost: result.total || 0,
      fuel_cost: parseFloat(fuelCost.toFixed(2)),
      mpg,
      fuel_purchases: normalizedPurchases,
    });

    onStatus?.('saved');
  } catch (err) {
    console.error('[autoSaveTrip] failed:', err?.message || err);
    onStatus?.('failed');
    Alert.alert(
      'Поездка не сохранена',
      'Проверьте подключение к интернету и попробуйте ещё раз.',
      [{ text: 'OK' }]
    );
  }
}

export default function ResultScreen({ route, navigation }) {
  const { result, from, to, truckType, fuelData, fuelPurchases } = route.params;
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);
  const [showIftaDetail, setShowIftaDetail] = useState(false);
  // Статус авто-сохранения: null | 'saving' | 'saved' | 'failed'
  const [saveStatus, setSaveStatus] = useState(null);

  useEffect(() => {
    getToken().then((token) => {
      setIsLoggedIn(!!token);
      // Авто-сохранение маршрута при открытии экрана результата
      if (token) {
        autoSaveTrip({
          result, from, to, truckType, fuelData, fuelPurchases,
          onStatus: setSaveStatus,
        });
      }
    });
  }, []);

  const tollCost = result.total || 0;
  const totalFormatted = tollCost.toFixed(2);
  const truckLabel = {
    '2-axle': '2 оси', '3-axle': '3 оси', '5-axle': '5 осей',
    '2axle': '2 оси', '3axle': '3 оси', '5axle': '5 осей',
  }[truckType] || truckType;

  // Fuel calculations
  const fuel = fuelData
    ? calcFuelData(result.distance_miles, fuelData.mpg, fuelData.fuelPrice, result.breakdown, fuelPurchases)
    : null;

  const grandTotal = fuel
    ? (tollCost + parseFloat(fuel.totalFuelCost) + parseFloat(fuel.totalIftaTax)).toFixed(2)
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
          <Text style={styles.grandTotalSub}>толлы + топливо + IFTA • {result.distance_miles} миль</Text>
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

      {/* Индикатор авто-сохранения */}
      {saveStatus === 'saving' && (
        <Text style={styles.autoSaveStatus}>💾 Сохраняем поездку...</Text>
      )}
      {saveStatus === 'saved' && (
        <Text style={[styles.autoSaveStatus, styles.autoSaveOk]}>✓ Поездка сохранена</Text>
      )}
      {saveStatus === 'failed' && (
        <Text style={[styles.autoSaveStatus, styles.autoSaveFail]}>✗ Не удалось сохранить</Text>
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
              <Text style={styles.iftaBadgeText}>
                {fuel.hasRealPurchases ? 'НЕТТО: ' : 'ИТОГО: '}${fuel.totalIftaTax}
              </Text>
            </View>
            <Ionicons
              name={showIftaDetail ? 'chevron-up' : 'chevron-down'}
              size={16}
              color="#888"
            />
          </TouchableOpacity>

          {showIftaDetail && (
            <>
              {fuel.hasRealPurchases ? (
                <>
                  <View style={styles.iftaTableHeader}>
                    <Text style={[styles.iftaCol, { flex: 0.7 }]}>Штат</Text>
                    <Text style={[styles.iftaCol, { flex: 0.9 }]}>Мили</Text>
                    <Text style={[styles.iftaCol, { flex: 0.9 }]}>Потр.</Text>
                    <Text style={[styles.iftaCol, { flex: 0.9 }]}>Куплено</Text>
                    <Text style={[styles.iftaCol, { flex: 1, textAlign: 'right' }]}>Нетто</Text>
                  </View>
                  {fuel.stateBreakdown.map((s, i) => (
                    <View key={i} style={styles.iftaRow}>
                      <Text style={[styles.iftaState, { flex: 0.7 }]}>{s.state}</Text>
                      <Text style={[styles.iftaData, { flex: 0.9 }]}>{s.miles}</Text>
                      <Text style={[styles.iftaData, { flex: 0.9 }]}>{s.gallons}</Text>
                      <Text style={[styles.iftaData, { flex: 0.9, color: '#81c784' }]}>
                        {s.purchasedGallons || '—'}
                      </Text>
                      <Text style={[
                        styles.iftaCost,
                        { flex: 1, textAlign: 'right' },
                        s.iftaNetPositive ? styles.iftaTaxDue : styles.iftaTaxRefund
                      ]}>
                        {s.iftaNetPositive ? '+' : ''}{s.iftaTax}
                      </Text>
                    </View>
                  ))}
                  <View style={styles.iftaNote}>
                    <Text style={styles.iftaNoteText}>
                      Нетто = (потреблённые − купленные) × ставка штата.
                      {'\n'}+ красный → доплата штату  |  − зелёный → возврат от штата.
                    </Text>
                  </View>
                </>
              ) : (
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
                      * Упрощённый расчёт — заправки по штатам не указаны.
                      Добавь данные о заправках для точного IFTA.
                    </Text>
                  </View>
                </>
              )}
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
  iftaTaxDue: { color: '#ef9a9a', fontSize: 13, fontWeight: '700' },    // доплата = красный
  iftaTaxRefund: { color: '#81c784', fontSize: 13, fontWeight: '700' }, // возврат = зелёный
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

  // Auto-save status indicator
  autoSaveStatus: {
    textAlign: 'center', fontSize: 12, color: '#888',
    marginBottom: 8, paddingVertical: 4,
  },
  autoSaveOk: { color: '#81c784' },
  autoSaveFail: { color: '#ef9a9a' },
});
