import React, { useState, useCallback, useRef } from 'react';
import {
  View, Text, StyleSheet, FlatList, TouchableOpacity,
  RefreshControl, ActivityIndicator, Alert, TextInput,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useFocusEffect } from '@react-navigation/native';
import api from '../services/api';

const PAGE_LIMIT = 20;

const DATE_FILTERS = [
  { label: '7 days', value: '7d' },
  { label: '30 days', value: '30d' },
  { label: 'Quarter', value: 'quarter' },
  { label: 'All', value: 'all' },
];

function getDateRange(filterValue) {
  const now = new Date();
  const today = now.toISOString().split('T')[0];
  if (filterValue === '7d') {
    const from = new Date(now);
    from.setDate(from.getDate() - 7);
    return { from: from.toISOString().split('T')[0], to: today };
  }
  if (filterValue === '30d') {
    const from = new Date(now);
    from.setDate(from.getDate() - 30);
    return { from: from.toISOString().split('T')[0], to: today };
  }
  if (filterValue === 'quarter') {
    const month = now.getMonth();
    const qStart = Math.floor(month / 3) * 3;
    const from = new Date(now.getFullYear(), qStart, 1).toISOString().split('T')[0];
    return { from, to: today };
  }
  return { from: null, to: null };
}

function formatDate(dateStr) {
  if (!dateStr) return '';
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return dateStr;
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

function TripCard({ trip, onPress }) {
  const totalCost = ((trip.toll_cost || 0) + (trip.fuel_cost || 0)).toFixed(2);
  const stateMiles = trip.state_miles || {};
  const stateCount = Object.keys(stateMiles).length;

  return (
    <TouchableOpacity style={styles.card} onPress={() => onPress(trip)} activeOpacity={0.75}>
      {/* Route */}
      <View style={styles.routeRow}>
        <View style={styles.cityBlock}>
          <Text style={styles.cityLabel}>FROM</Text>
          <Text style={styles.cityName} numberOfLines={1}>{trip.from_city}</Text>
        </View>
        <Ionicons name="arrow-forward" size={16} color="#4fc3f7" style={styles.arrow} />
        <View style={[styles.cityBlock, { alignItems: 'flex-end' }]}>
          <Text style={styles.cityLabel}>TO</Text>
          <Text style={styles.cityName} numberOfLines={1}>{trip.to_city}</Text>
        </View>
      </View>

      {/* Metadata */}
      <View style={styles.metaRow}>
        <View style={styles.metaItem}>
          <Ionicons name="calendar-outline" size={13} color="#555" />
          <Text style={styles.metaText}>{formatDate(trip.created_at)}</Text>
        </View>
        <View style={styles.metaItem}>
          <Ionicons name="navigate-outline" size={13} color="#555" />
          <Text style={styles.metaText}>{(trip.total_miles || 0).toFixed(0)} mi</Text>
        </View>
        {stateCount > 0 && (
          <View style={styles.metaItem}>
            <Ionicons name="map-outline" size={13} color="#555" />
            <Text style={styles.metaText}>{stateCount} state{stateCount > 1 ? 's' : ''}</Text>
          </View>
        )}
      </View>

      {/* Cost */}
      <View style={styles.costsRow}>
        {trip.toll_cost > 0 && (
          <View style={styles.costItem}>
            <Text style={styles.costLabel}>Tolls</Text>
            <Text style={styles.costValue}>${(trip.toll_cost || 0).toFixed(2)}</Text>
          </View>
        )}
        {trip.fuel_cost > 0 && (
          <View style={styles.costItem}>
            <Text style={styles.costLabel}>Fuel</Text>
            <Text style={styles.costValue}>${(trip.fuel_cost || 0).toFixed(2)}</Text>
          </View>
        )}
        <View style={[styles.costItem, styles.costTotal]}>
          <Text style={styles.costTotalLabel}>Total</Text>
          <Text style={styles.costTotalValue}>${totalCost}</Text>
        </View>
      </View>

      {/* Quarter */}
      <View style={styles.quarterBadge}>
        <Text style={styles.quarterText}>Q{trip.quarter} {trip.year}</Text>
      </View>
    </TouchableOpacity>
  );
}

export default function TripHistoryScreen({ navigation }) {
  const [trips, setTrips] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);
  const [total, setTotal] = useState(0);

  // Filters
  const [searchText, setSearchText] = useState('');
  const [dateFilter, setDateFilter] = useState('all');

  const searchTimeout = useRef(null);

  const loadTrips = useCallback(async ({ pageNum = 1, refresh = false, search = searchText, dFilter = dateFilter } = {}) => {
    if (pageNum === 1) {
      if (refresh) setRefreshing(true);
      else setLoading(true);
    } else {
      setLoadingMore(true);
    }
    setError(null);

    try {
      const { from, to } = getDateRange(dFilter);
      const params = { page: pageNum, limit: PAGE_LIMIT };
      if (search.trim()) params.search = search.trim();
      if (from) params.from = from;
      if (to) params.to = to;

      const { data } = await api.get('/api/trips/history', { params });

      if (pageNum === 1) {
        setTrips(data.trips || []);
      } else {
        setTrips(prev => [...prev, ...(data.trips || [])]);
      }
      setTotal(data.total || 0);
      setHasMore(data.hasMore || false);
      setPage(pageNum);
    } catch (err) {
      const msg = err.response?.data?.error || 'Failed to load history';
      setError(msg);
      if (refresh) Alert.alert('Error', msg);
    } finally {
      setLoading(false);
      setLoadingMore(false);
      setRefreshing(false);
    }
  }, [searchText, dateFilter]);

  useFocusEffect(
    useCallback(() => {
      loadTrips({ pageNum: 1 });
    }, [dateFilter])
  );

  const handleSearchChange = (text) => {
    setSearchText(text);
    if (searchTimeout.current) clearTimeout(searchTimeout.current);
    searchTimeout.current = setTimeout(() => {
      loadTrips({ pageNum: 1, search: text });
    }, 400);
  };

  const handleDateFilter = (value) => {
    setDateFilter(value);
    loadTrips({ pageNum: 1, dFilter: value });
  };

  const handleLoadMore = () => {
    if (!loadingMore && hasMore) {
      loadTrips({ pageNum: page + 1 });
    }
  };

  const handleTripPress = (trip) => {
    navigation.navigate('TripDetail', { tripId: trip.id });
  };

  const renderFooter = () => {
    if (!loadingMore) return null;
    return (
      <View style={styles.footerLoader}>
        <ActivityIndicator size="small" color="#4fc3f7" />
      </View>
    );
  };

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color="#4fc3f7" />
        <Text style={styles.loadingText}>Loading history...</Text>
      </View>
    );
  }

  if (error && trips.length === 0) {
    return (
      <View style={styles.center}>
        <Ionicons name="alert-circle-outline" size={48} color="#ef9a9a" />
        <Text style={styles.errorText}>{error}</Text>
        <TouchableOpacity style={styles.retryBtn} onPress={() => loadTrips({ pageNum: 1 })}>
          <Text style={styles.retryText}>Retry</Text>
        </TouchableOpacity>
      </View>
    );
  }

  const ListHeader = (
    <View>
      <View style={styles.header}>
        <Text style={styles.headerTitle}>Trip History</Text>
        <Text style={styles.headerSub}>{total} route{total !== 1 ? 's' : ''}</Text>
      </View>

      {/* Search bar */}
      <View style={styles.searchRow}>
        <Ionicons name="search-outline" size={16} color="#555" style={styles.searchIcon} />
        <TextInput
          style={styles.searchInput}
          placeholder="Search by state or route..."
          placeholderTextColor="#444"
          value={searchText}
          onChangeText={handleSearchChange}
          returnKeyType="search"
        />
        {searchText.length > 0 && (
          <TouchableOpacity onPress={() => handleSearchChange('')}>
            <Ionicons name="close-circle" size={16} color="#555" />
          </TouchableOpacity>
        )}
      </View>

      {/* Date filter */}
      <View style={styles.filterRow}>
        {DATE_FILTERS.map(f => (
          <TouchableOpacity
            key={f.value}
            style={[styles.filterBtn, dateFilter === f.value && styles.filterBtnActive]}
            onPress={() => handleDateFilter(f.value)}
          >
            <Text style={[styles.filterBtnText, dateFilter === f.value && styles.filterBtnTextActive]}>
              {f.label}
            </Text>
          </TouchableOpacity>
        ))}
      </View>
    </View>
  );

  const EmptyState = (
    <View style={styles.emptyState}>
      <Text style={styles.emptyIcon}>🚛</Text>
      <Text style={styles.emptyTitle}>No trips yet</Text>
      <Text style={styles.emptySubtitle}>
        {searchText || dateFilter !== 'all'
          ? 'Nothing found — try different filters'
          : 'Calculate a route to start tracking'}
      </Text>
    </View>
  );

  return (
    <FlatList
      style={styles.container}
      contentContainerStyle={styles.listContent}
      data={trips}
      keyExtractor={(item) => String(item.id)}
      renderItem={({ item }) => <TripCard trip={item} onPress={handleTripPress} />}
      refreshControl={
        <RefreshControl
          refreshing={refreshing}
          onRefresh={() => loadTrips({ pageNum: 1, refresh: true })}
          tintColor="#4fc3f7"
          colors={['#4fc3f7']}
        />
      }
      ListHeaderComponent={ListHeader}
      ListEmptyComponent={EmptyState}
      ListFooterComponent={renderFooter}
      onEndReached={handleLoadMore}
      onEndReachedThreshold={0.3}
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
  retryBtn: {
    marginTop: 20,
    paddingHorizontal: 24,
    paddingVertical: 12,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#4fc3f7',
  },
  retryText: { color: '#4fc3f7', fontSize: 14, fontWeight: '700' },

  header: { marginBottom: 12 },
  headerTitle: { color: '#fff', fontSize: 22, fontWeight: '800' },
  headerSub: { color: '#555', fontSize: 13, marginTop: 4 },

  searchRow: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#161629',
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#1e1e3a',
    paddingHorizontal: 12,
    marginBottom: 10,
    gap: 8,
  },
  searchIcon: { marginRight: 2 },
  searchInput: {
    flex: 1,
    color: '#fff',
    fontSize: 14,
    paddingVertical: 11,
  },

  filterRow: {
    flexDirection: 'row',
    gap: 8,
    marginBottom: 16,
  },
  filterBtn: {
    flex: 1,
    paddingVertical: 8,
    borderRadius: 8,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: '#1e1e3a',
    backgroundColor: '#161629',
  },
  filterBtnActive: { backgroundColor: '#0a1f2e', borderColor: '#4fc3f7' },
  filterBtnText: { color: '#555', fontSize: 12, fontWeight: '600' },
  filterBtnTextActive: { color: '#4fc3f7' },

  // Empty state
  emptyState: {
    alignItems: 'center',
    paddingVertical: 48,
    paddingHorizontal: 24,
  },
  emptyIcon: { fontSize: 48, marginBottom: 12 },
  emptyTitle: { color: '#555', fontSize: 18, fontWeight: '700', marginBottom: 8 },
  emptySubtitle: { color: '#333', fontSize: 13, textAlign: 'center', lineHeight: 20 },

  footerLoader: { paddingVertical: 16, alignItems: 'center' },

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
