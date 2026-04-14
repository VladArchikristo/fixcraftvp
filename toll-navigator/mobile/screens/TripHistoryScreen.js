import React, { useState, useCallback } from 'react';
import {
  View, Text, StyleSheet, FlatList, TouchableOpacity,
  RefreshControl, ActivityIndicator, Alert,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useFocusEffect } from '@react-navigation/native';
import api from '../services/api';

function formatDate(dateStr) {
  if (!dateStr) return '';
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return dateStr;
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

function TripCard({ trip }) {
  const totalCost = ((trip.toll_cost || 0) + (trip.fuel_cost || 0)).toFixed(2);
  const stateMiles = trip.state_miles || {};
  const stateCount = Object.keys(stateMiles).length;

  return (
    <View style={styles.card}>
      {/* Маршрут */}
      <View style={styles.routeRow}>
        <View style={styles.cityBlock}>
          <Text style={styles.cityLabel}>ИЗ</Text>
          <Text style={styles.cityName} numberOfLines={1}>{trip.from_city}</Text>
        </View>
        <Ionicons name="arrow-forward" size={16} color="#4fc3f7" style={styles.arrow} />
        <View style={[styles.cityBlock, { alignItems: 'flex-end' }]}>
          <Text style={styles.cityLabel}>В</Text>
          <Text style={styles.cityName} numberOfLines={1}>{trip.to_city}</Text>
        </View>
      </View>

      {/* Метаданные */}
      <View style={styles.metaRow}>
        <View style={styles.metaItem}>
          <Ionicons name="calendar-outline" size={13} color="#555" />
          <Text style={styles.metaText}>{formatDate(trip.created_at)}</Text>
        </View>
        <View style={styles.metaItem}>
          <Ionicons name="navigate-outline" size={13} color="#555" />
          <Text style={styles.metaText}>{(trip.total_miles || 0).toFixed(0)} миль</Text>
        </View>
        {stateCount > 0 && (
          <View style={styles.metaItem}>
            <Ionicons name="map-outline" size={13} color="#555" />
            <Text style={styles.metaText}>{stateCount} штат{stateCount > 1 ? 'ов' : ''}</Text>
          </View>
        )}
      </View>

      {/* Стоимость */}
      <View style={styles.costsRow}>
        {trip.toll_cost > 0 && (
          <View style={styles.costItem}>
            <Text style={styles.costLabel}>Толлы</Text>
            <Text style={styles.costValue}>${(trip.toll_cost || 0).toFixed(2)}</Text>
          </View>
        )}
        {trip.fuel_cost > 0 && (
          <View style={styles.costItem}>
            <Text style={styles.costLabel}>Топливо</Text>
            <Text style={styles.costValue}>${(trip.fuel_cost || 0).toFixed(2)}</Text>
          </View>
        )}
        <View style={[styles.costItem, styles.costTotal]}>
          <Text style={styles.costTotalLabel}>Итого</Text>
          <Text style={styles.costTotalValue}>${totalCost}</Text>
        </View>
      </View>

      {/* Квартал */}
      <View style={styles.quarterBadge}>
        <Text style={styles.quarterText}>Q{trip.quarter} {trip.year}</Text>
      </View>
    </View>
  );
}

export default function TripHistoryScreen() {
  const [trips, setTrips] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);

  const loadTrips = async (showRefresh = false) => {
    if (showRefresh) setRefreshing(true);
    else setLoading(true);
    setError(null);

    try {
      const { data } = await api.get('/api/trips/history');
      setTrips(data.trips || []);
    } catch (err) {
      const msg = err.response?.data?.error || 'Не удалось загрузить историю';
      setError(msg);
      if (showRefresh) Alert.alert('Ошибка', msg);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  // Обновляем при фокусе (возврат с другого экрана)
  useFocusEffect(
    useCallback(() => {
      loadTrips();
    }, [])
  );

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color="#4fc3f7" />
        <Text style={styles.loadingText}>Загружаем историю...</Text>
      </View>
    );
  }

  if (error && trips.length === 0) {
    return (
      <View style={styles.center}>
        <Ionicons name="alert-circle-outline" size={48} color="#ef9a9a" />
        <Text style={styles.errorText}>{error}</Text>
        <TouchableOpacity style={styles.retryBtn} onPress={() => loadTrips()}>
          <Text style={styles.retryText}>Повторить</Text>
        </TouchableOpacity>
      </View>
    );
  }

  if (trips.length === 0) {
    return (
      <View style={styles.center}>
        <Ionicons name="time-outline" size={56} color="#333" />
        <Text style={styles.emptyTitle}>История пуста</Text>
        <Text style={styles.emptySubtitle}>Рассчитай маршрут — он сохранится здесь автоматически</Text>
      </View>
    );
  }

  return (
    <FlatList
      style={styles.container}
      contentContainerStyle={styles.listContent}
      data={trips}
      keyExtractor={(item) => String(item.id)}
      renderItem={({ item }) => <TripCard trip={item} />}
      refreshControl={
        <RefreshControl
          refreshing={refreshing}
          onRefresh={() => loadTrips(true)}
          tintColor="#4fc3f7"
          colors={['#4fc3f7']}
        />
      }
      ListHeaderComponent={
        <View style={styles.header}>
          <Text style={styles.headerTitle}>История поездок</Text>
          <Text style={styles.headerSub}>{trips.length} маршрут{trips.length !== 1 ? 'ов' : ''}</Text>
        </View>
      }
      showsVerticalScrollIndicator={false}
    />
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0d0d1a' },
  listContent: { padding: 16, paddingBottom: 40 },

  center: {
    flex: 1,
    backgroundColor: '#0d0d1a',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 32,
  },
  loadingText: { color: '#555', fontSize: 14, marginTop: 12 },
  errorText: { color: '#ef9a9a', fontSize: 14, textAlign: 'center', marginTop: 12 },
  emptyTitle: { color: '#555', fontSize: 18, fontWeight: '700', marginTop: 16 },
  emptySubtitle: { color: '#333', fontSize: 13, textAlign: 'center', marginTop: 8, lineHeight: 20 },
  retryBtn: {
    marginTop: 20,
    paddingHorizontal: 24,
    paddingVertical: 12,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#4fc3f7',
  },
  retryText: { color: '#4fc3f7', fontSize: 14, fontWeight: '700' },

  header: { marginBottom: 16 },
  headerTitle: { color: '#fff', fontSize: 22, fontWeight: '800' },
  headerSub: { color: '#555', fontSize: 13, marginTop: 4 },

  card: {
    backgroundColor: '#161629',
    borderRadius: 14,
    padding: 16,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: '#1e1e3a',
  },

  routeRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 12,
  },
  cityBlock: { flex: 1 },
  arrow: { marginHorizontal: 8 },
  cityLabel: { color: '#444', fontSize: 10, fontWeight: '700', letterSpacing: 1, marginBottom: 2 },
  cityName: { color: '#fff', fontSize: 14, fontWeight: '700' },

  metaRow: {
    flexDirection: 'row',
    gap: 14,
    marginBottom: 12,
  },
  metaItem: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  metaText: { color: '#555', fontSize: 12 },

  costsRow: {
    flexDirection: 'row',
    gap: 10,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: '#1e1e3a',
  },
  costItem: { flex: 1, alignItems: 'center' },
  costLabel: { color: '#555', fontSize: 10, fontWeight: '700', textTransform: 'uppercase', marginBottom: 3 },
  costValue: { color: '#aaa', fontSize: 13, fontWeight: '700' },
  costTotal: {
    borderLeftWidth: 1,
    borderLeftColor: '#1e1e3a',
    paddingLeft: 10,
  },
  costTotalLabel: { color: '#888', fontSize: 10, fontWeight: '700', textTransform: 'uppercase', marginBottom: 3 },
  costTotalValue: { color: '#4fc3f7', fontSize: 15, fontWeight: '800' },

  quarterBadge: {
    position: 'absolute',
    top: 12,
    right: 12,
    backgroundColor: '#0a1520',
    borderRadius: 6,
    paddingHorizontal: 7,
    paddingVertical: 3,
    borderWidth: 1,
    borderColor: '#1e3a50',
  },
  quarterText: { color: '#4fc3f7', fontSize: 10, fontWeight: '700' },
});
