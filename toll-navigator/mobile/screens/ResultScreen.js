import React from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';

export default function ResultScreen({ route, navigation }) {
  const { result, from, to, truckType } = route.params;

  const totalFormatted = result.total?.toFixed(2) ?? '—';
  const truckLabel = { '2-axle': '2 оси', '3-axle': '3 оси', '5-axle': '5 осей' }[truckType] || truckType;

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
  tipText: { color: '#666', fontSize: 13, marginBottom: 8, lineHeight: 20 },
  backBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    gap: 8, padding: 16, borderRadius: 14,
    borderWidth: 1, borderColor: '#4fc3f7', marginTop: 8,
  },
  backBtnText: { color: '#4fc3f7', fontSize: 15, fontWeight: '700' },
});
