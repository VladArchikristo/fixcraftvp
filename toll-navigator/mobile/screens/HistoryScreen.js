import React, { useState, useCallback } from 'react';
import {
  View, Text, StyleSheet, FlatList,
  TouchableOpacity, ActivityIndicator, RefreshControl
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useFocusEffect } from '@react-navigation/native';
import api from '../services/api';
import { getToken } from '../services/auth';

export default function HistoryScreen({ navigation }) {
  const [routes, setRoutes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [noAuth, setNoAuth] = useState(false);

  const loadHistory = async () => {
    try {
      const token = await getToken();
      if (!token) {
        setNoAuth(true);
        setLoading(false);
        return;
      }
      const res = await api.get('/api/tolls/history');
      setRoutes(res.data || []);
      setNoAuth(false);
    } catch (err) {
      if (err.response?.status === 401) {
        setNoAuth(true);
      }
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useFocusEffect(
    useCallback(() => {
      setLoading(true);
      loadHistory();
    }, [])
  );

  const formatDate = (dateStr) => {
    if (!dateStr) return '';
    const d = new Date(dateStr);
    return d.toLocaleDateString('ru-RU', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });
  };

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color="#4fc3f7" />
      </View>
    );
  }

  if (noAuth) {
    return (
      <View style={styles.center}>
        <Ionicons name="lock-closed-outline" size={48} color="#333" />
        <Text style={styles.emptyTitle}>История недоступна</Text>
        <Text style={styles.emptyText}>Войдите в аккаунт чтобы сохранять маршруты</Text>
        <TouchableOpacity style={styles.actionBtn} onPress={() => navigation.navigate('Calc')}>
          <Text style={styles.actionBtnText}>Рассчитать маршрут</Text>
        </TouchableOpacity>
      </View>
    );
  }

  if (routes.length === 0) {
    return (
      <View style={styles.center}>
        <Ionicons name="time-outline" size={48} color="#333" />
        <Text style={styles.emptyTitle}>История пуста</Text>
        <Text style={styles.emptyText}>Рассчитанные маршруты появятся здесь</Text>
        <TouchableOpacity style={styles.actionBtn} onPress={() => navigation.navigate('Calc')}>
          <Text style={styles.actionBtnText}>Первый расчёт →</Text>
        </TouchableOpacity>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <FlatList
        data={routes}
        keyExtractor={(item, i) => String(item.id ?? i)}
        contentContainerStyle={styles.list}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={() => { setRefreshing(true); loadHistory(); }}
            tintColor="#4fc3f7"
          />
        }
        renderItem={({ item }) => (
          <View style={styles.card}>
            <View style={styles.routeRow}>
              <Text style={styles.city} numberOfLines={1}>{item.origin}</Text>
              <Ionicons name="arrow-forward" size={16} color="#4fc3f7" style={styles.arrow} />
              <Text style={styles.city} numberOfLines={1}>{item.destination}</Text>
            </View>
            <View style={styles.bottomRow}>
              <Text style={styles.date}>{formatDate(item.created_at)}</Text>
              <Text style={styles.cost}>${Number(item.toll_cost).toFixed(2)}</Text>
            </View>
            <Text style={styles.meta}>{item.distance_miles} миль</Text>
          </View>
        )}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0d0d1a' },
  center: { flex: 1, backgroundColor: '#0d0d1a', alignItems: 'center', justifyContent: 'center', padding: 40 },
  list: { padding: 16 },
  card: {
    backgroundColor: '#161629',
    borderRadius: 14,
    padding: 16,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: '#1e1e3a',
  },
  routeRow: { flexDirection: 'row', alignItems: 'center', marginBottom: 10 },
  arrow: { marginHorizontal: 8 },
  city: { flex: 1, color: '#fff', fontSize: 15, fontWeight: '700' },
  bottomRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  date: { color: '#555', fontSize: 12 },
  cost: { color: '#4fc3f7', fontSize: 20, fontWeight: '900' },
  meta: { color: '#444', fontSize: 12, marginTop: 4 },
  emptyTitle: { color: '#fff', fontSize: 18, fontWeight: '700', marginTop: 16, marginBottom: 8 },
  emptyText: { color: '#555', fontSize: 14, textAlign: 'center', lineHeight: 20 },
  actionBtn: {
    marginTop: 24, backgroundColor: '#4fc3f7', borderRadius: 12,
    paddingHorizontal: 24, paddingVertical: 12,
  },
  actionBtnText: { color: '#0d0d1a', fontWeight: '800', fontSize: 15 },
});
