import React, { useState, useEffect } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity, Alert
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { getToken } from '../services/auth';
import api from '../services/api';

export default function ResultScreen({ route, navigation }) {
  const { result, from, to, truckType } = route.params;
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    getToken().then((token) => setIsLoggedIn(!!token));
  }, []);

  const totalFormatted = result.total?.toFixed(2) ?? '—';
  const truckLabel = { '2-axle': '2 оси', '3-axle': '3 оси', '5-axle': '5 осей' }[truckType] || truckType;

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

  // Build recommendations based on result
  const recommendations = [];
  if (result.breakdown) {
    const states = result.breakdown.map((b) => b.state);
    const hasNortheast = states.some((s) => ['NY', 'NJ', 'PA', 'MA', 'CT', 'RI', 'NH', 'VT', 'ME', 'MD', 'DE'].includes(s));
    if (hasNortheast) {
      recommendations.push({ icon: '💳', text: 'E-ZPass охватывает этот маршрут — экономия до 30% на сборах' });
    }
    const hasTexas = states.includes('TX');
    if (hasTexas) {
      recommendations.push({ icon: '⭐', text: 'TxTag или EZ TAG даёт скидку на все платные дороги Техаса' });
    }
  }
  if (truckType === '5-axle') {
    recommendations.push({ icon: '🚛', text: '5-осный грузовик — максимальная нагрузка. 3-осный вариант может быть дешевле для небольших грузов' });
  }
  if (truckType === '2-axle') {
    recommendations.push({ icon: '✅', text: '2-осный грузовик — оптимальная ставка сборов на большинстве дорог' });
  }
  recommendations.push({ icon: '⛽', text: 'Заправляйся в штатах без топливного налога: MT, NH, OR для экономии' });

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

      {/* Total */}
      <View style={styles.totalCard}>
        <Text style={styles.totalLabel}>Итого платных дорог</Text>
        <Text style={styles.totalAmount}>${totalFormatted}</Text>
        <Text style={styles.totalSub}>по данным 2026</Text>
      </View>

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
              {saving ? 'Сохраняем...' : saved ? 'Сохранено' : 'Сохранить маршрут'}
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

      {/* Breakdown by state */}
      {result.breakdown && result.breakdown.length > 0 && (
        <View style={styles.card}>
          <Text style={styles.sectionTitle}>📊 Разбивка по штатам</Text>
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
      <View style={styles.card}>
        <Text style={styles.sectionTitle}>🎯 Рекомендации</Text>
        {recommendations.map((r, i) => (
          <View key={i} style={styles.recRow}>
            <Text style={styles.recIcon}>{r.icon}</Text>
            <Text style={styles.recText}>{r.text}</Text>
          </View>
        ))}
      </View>

      {/* Tips */}
      <View style={styles.card}>
        <Text style={styles.sectionTitle}>💡 Советы</Text>
        <Text style={styles.tipText}>• E-ZPass экономит до 30% на большинстве платных дорог северо-востока</Text>
        <Text style={styles.tipText}>• Заправляйся в штатах без топливного налога: MT, NH, OR</Text>
        <Text style={styles.tipText}>• Маршрут рассчитан для {truckLabel.toLowerCase()}</Text>
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
  actionsRow: {
    flexDirection: 'row',
    gap: 10,
    marginBottom: 14,
  },
  actionBtn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    paddingVertical: 12,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#4fc3f7',
    backgroundColor: '#0a1f2e',
  },
  actionBtnSaved: {
    borderColor: '#81c784',
    backgroundColor: '#0a1f0e',
  },
  actionBtnText: { color: '#4fc3f7', fontSize: 13, fontWeight: '700' },
  actionBtnTextSaved: { color: '#81c784' },
  card: {
    backgroundColor: '#161629',
    borderRadius: 14,
    padding: 18,
    marginBottom: 14,
    borderWidth: 1,
    borderColor: '#1e1e3a',
  },
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
