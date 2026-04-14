import React, { useState, useCallback, useRef } from 'react';
import {
  View, Text, StyleSheet, FlatList, TouchableOpacity,
  RefreshControl, ActivityIndicator, Alert, TextInput,
  ScrollView,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useFocusEffect } from '@react-navigation/native';
import { getBrokers } from '../services/brokers';

const PAGE_LIMIT = 20;

const US_STATES = [
  'Все', 'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA',
  'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD',
  'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ',
  'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC',
  'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY',
];

const RATING_FILTERS = [
  { label: 'Все', value: 0 },
  { label: '4+ ⭐', value: 4 },
  { label: '3+ ⭐', value: 3 },
  { label: '2+ ⭐', value: 2 },
];

function getRatingColor(rating) {
  if (rating >= 4) return '#81c784';
  if (rating >= 3) return '#ffb74d';
  return '#ef9a9a';
}

function StarRating({ rating, size = 12 }) {
  const full = Math.floor(rating);
  const stars = [];
  for (let i = 1; i <= 5; i++) {
    stars.push(
      <Ionicons
        key={i}
        name={i <= full ? 'star' : 'star-outline'}
        size={size}
        color={i <= full ? '#ffb74d' : '#333'}
      />
    );
  }
  return <View style={styles.starsRow}>{stars}</View>;
}

function BrokerCard({ broker, onPress }) {
  const rating = parseFloat(broker.avg_rating || 0);
  const ratingColor = getRatingColor(rating);

  return (
    <TouchableOpacity style={styles.card} onPress={() => onPress(broker)} activeOpacity={0.75}>
      <View style={styles.cardHeader}>
        <View style={styles.cardTitleBlock}>
          <Text style={styles.brokerName} numberOfLines={1}>{broker.name}</Text>
          {broker.mc_number ? (
            <Text style={styles.mcNumber}>MC# {broker.mc_number}</Text>
          ) : null}
        </View>
        <View style={[styles.ratingBadge, { borderColor: ratingColor }]}>
          <Text style={[styles.ratingValue, { color: ratingColor }]}>
            {rating > 0 ? rating.toFixed(1) : '—'}
          </Text>
          <Ionicons name="star" size={10} color={ratingColor} />
        </View>
      </View>

      <View style={styles.cardMeta}>
        {broker.state ? (
          <View style={styles.metaItem}>
            <Ionicons name="location-outline" size={13} color="#555" />
            <Text style={styles.metaText}>{broker.state}</Text>
          </View>
        ) : null}
        {broker.city ? (
          <View style={styles.metaItem}>
            <Ionicons name="business-outline" size={13} color="#555" />
            <Text style={styles.metaText} numberOfLines={1}>{broker.city}</Text>
          </View>
        ) : null}
        <View style={styles.metaItem}>
          <Ionicons name="chatbubble-outline" size={13} color="#555" />
          <Text style={styles.metaText}>
            {broker.review_count || 0} отзыв{getReviewWord(broker.review_count || 0)}
          </Text>
        </View>
      </View>

      {rating > 0 && (
        <View style={styles.cardFooter}>
          <StarRating rating={rating} size={11} />
        </View>
      )}

      <Ionicons name="chevron-forward" size={16} color="#333" style={styles.chevron} />
    </TouchableOpacity>
  );
}

function getReviewWord(count) {
  if (count % 100 >= 11 && count % 100 <= 19) return 'ов';
  const last = count % 10;
  if (last === 1) return '';
  if (last >= 2 && last <= 4) return 'а';
  return 'ов';
}

export default function BrokerListScreen({ navigation }) {
  const [brokers, setBrokers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);
  const [total, setTotal] = useState(0);

  const [searchText, setSearchText] = useState('');
  const [selectedState, setSelectedState] = useState('Все');
  const [minRating, setMinRating] = useState(0);

  const searchTimeout = useRef(null);

  const loadBrokers = useCallback(async ({
    pageNum = 1,
    refresh = false,
    search = searchText,
    state = selectedState,
    rating = minRating,
  } = {}) => {
    if (pageNum === 1) {
      if (refresh) setRefreshing(true);
      else setLoading(true);
    } else {
      setLoadingMore(true);
    }
    setError(null);

    try {
      const params = { page: pageNum, limit: PAGE_LIMIT };
      if (search.trim()) params.search = search.trim();
      if (state && state !== 'Все') params.state = state;
      if (rating > 0) params.min_rating = rating;

      const data = await getBrokers(params);

      if (pageNum === 1) {
        setBrokers(data.brokers || []);
      } else {
        setBrokers(prev => [...prev, ...(data.brokers || [])]);
      }
      setTotal(data.total || 0);
      setHasMore(data.hasMore || false);
      setPage(pageNum);
    } catch (err) {
      const msg = err.response?.data?.error || 'Не удалось загрузить список брокеров';
      setError(msg);
      if (refresh) Alert.alert('Ошибка', msg);
    } finally {
      setLoading(false);
      setLoadingMore(false);
      setRefreshing(false);
    }
  }, [searchText, selectedState, minRating]);

  useFocusEffect(
    useCallback(() => {
      loadBrokers({ pageNum: 1 });
    }, [selectedState, minRating])
  );

  const handleSearchChange = (text) => {
    setSearchText(text);
    if (searchTimeout.current) clearTimeout(searchTimeout.current);
    searchTimeout.current = setTimeout(() => {
      loadBrokers({ pageNum: 1, search: text });
    }, 400);
  };

  const handleStateFilter = (state) => {
    setSelectedState(state);
    loadBrokers({ pageNum: 1, state });
  };

  const handleRatingFilter = (rating) => {
    setMinRating(rating);
    loadBrokers({ pageNum: 1, rating });
  };

  const handleLoadMore = () => {
    if (!loadingMore && hasMore) {
      loadBrokers({ pageNum: page + 1 });
    }
  };

  const handleBrokerPress = (broker) => {
    navigation.navigate('BrokerDetail', { brokerId: broker.id, brokerName: broker.name });
  };

  const handleAddBroker = () => {
    navigation.navigate('AddBrokerReview', { mode: 'new' });
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
        <Text style={styles.loadingText}>Загружаем брокеров...</Text>
      </View>
    );
  }

  if (error && brokers.length === 0) {
    return (
      <View style={styles.center}>
        <Ionicons name="alert-circle-outline" size={48} color="#ef9a9a" />
        <Text style={styles.errorText}>{error}</Text>
        <TouchableOpacity style={styles.retryBtn} onPress={() => loadBrokers({ pageNum: 1 })}>
          <Text style={styles.retryText}>Повторить</Text>
        </TouchableOpacity>
      </View>
    );
  }

  const ListHeader = (
    <View>
      <View style={styles.header}>
        <Text style={styles.headerTitle}>Проверка брокеров</Text>
        <Text style={styles.headerSub}>{total} брокер{getBrokerWord(total)}</Text>
      </View>

      {/* Поиск */}
      <View style={styles.searchRow}>
        <Ionicons name="search-outline" size={16} color="#555" style={styles.searchIcon} />
        <TextInput
          style={styles.searchInput}
          placeholder="Поиск по имени или MC#..."
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

      {/* Фильтр штат */}
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.stateScroll}>
        {US_STATES.map(state => (
          <TouchableOpacity
            key={state}
            style={[styles.stateChip, selectedState === state && styles.stateChipActive]}
            onPress={() => handleStateFilter(state)}
          >
            <Text style={[styles.stateChipText, selectedState === state && styles.stateChipTextActive]}>
              {state}
            </Text>
          </TouchableOpacity>
        ))}
      </ScrollView>

      {/* Фильтр рейтинг */}
      <View style={styles.filterRow}>
        {RATING_FILTERS.map(f => (
          <TouchableOpacity
            key={f.value}
            style={[styles.filterBtn, minRating === f.value && styles.filterBtnActive]}
            onPress={() => handleRatingFilter(f.value)}
          >
            <Text style={[styles.filterBtnText, minRating === f.value && styles.filterBtnTextActive]}>
              {f.label}
            </Text>
          </TouchableOpacity>
        ))}
      </View>
    </View>
  );

  const EmptyState = (
    <View style={styles.emptyState}>
      <Text style={styles.emptyIcon}>🏢</Text>
      <Text style={styles.emptyTitle}>Брокеров пока нет</Text>
      <Text style={styles.emptySubtitle}>
        {searchText || selectedState !== 'Все' || minRating > 0
          ? 'Ничего не найдено — попробуй другие фильтры'
          : 'Будьте первым — добавьте брокера с отзывом'}
      </Text>
      <TouchableOpacity style={styles.emptyBtn} onPress={handleAddBroker}>
        <Text style={styles.emptyBtnText}>Добавить брокера</Text>
      </TouchableOpacity>
    </View>
  );

  return (
    <View style={{ flex: 1, backgroundColor: '#0d0d1a' }}>
      <FlatList
        style={styles.container}
        contentContainerStyle={styles.listContent}
        data={brokers}
        keyExtractor={(item) => String(item.id)}
        renderItem={({ item }) => <BrokerCard broker={item} onPress={handleBrokerPress} />}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={() => loadBrokers({ pageNum: 1, refresh: true })}
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

      {/* FAB — добавить брокера */}
      <TouchableOpacity style={styles.fab} onPress={handleAddBroker} activeOpacity={0.85}>
        <Ionicons name="add" size={28} color="#fff" />
      </TouchableOpacity>
    </View>
  );
}

function getBrokerWord(count) {
  if (count % 100 >= 11 && count % 100 <= 19) return 'ов';
  const last = count % 10;
  if (last === 1) return '';
  if (last >= 2 && last <= 4) return 'а';
  return 'ов';
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0d0d1a' },
  listContent: { padding: 16, paddingBottom: 100 },

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

  stateScroll: { marginBottom: 10 },
  stateChip: {
    paddingHorizontal: 12,
    paddingVertical: 7,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: '#1e1e3a',
    backgroundColor: '#161629',
    marginRight: 6,
  },
  stateChipActive: { backgroundColor: '#0a1f2e', borderColor: '#4fc3f7' },
  stateChipText: { color: '#555', fontSize: 12, fontWeight: '600' },
  stateChipTextActive: { color: '#4fc3f7' },

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

  emptyState: {
    alignItems: 'center',
    paddingVertical: 48,
    paddingHorizontal: 24,
  },
  emptyIcon: { fontSize: 48, marginBottom: 12 },
  emptyTitle: { color: '#555', fontSize: 18, fontWeight: '700', marginBottom: 8 },
  emptySubtitle: { color: '#333', fontSize: 13, textAlign: 'center', lineHeight: 20, marginBottom: 20 },
  emptyBtn: {
    paddingHorizontal: 24,
    paddingVertical: 12,
    borderRadius: 10,
    backgroundColor: '#0a1f2e',
    borderWidth: 1,
    borderColor: '#4fc3f7',
  },
  emptyBtnText: { color: '#4fc3f7', fontSize: 14, fontWeight: '700' },

  footerLoader: { paddingVertical: 16, alignItems: 'center' },

  // Broker card
  card: {
    backgroundColor: '#161629',
    borderRadius: 14,
    padding: 16,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: '#1e1e3a',
  },
  cardHeader: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    marginBottom: 10,
  },
  cardTitleBlock: { flex: 1, marginRight: 8 },
  brokerName: { color: '#fff', fontSize: 16, fontWeight: '800', marginBottom: 3 },
  mcNumber: { color: '#555', fontSize: 12 },
  ratingBadge: {
    borderRadius: 8,
    borderWidth: 1,
    paddingHorizontal: 8,
    paddingVertical: 4,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 3,
  },
  ratingValue: { fontSize: 14, fontWeight: '800' },

  cardMeta: {
    flexDirection: 'row',
    gap: 14,
    flexWrap: 'wrap',
    marginBottom: 8,
  },
  metaItem: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  metaText: { color: '#555', fontSize: 12 },

  cardFooter: { marginTop: 4 },
  starsRow: { flexDirection: 'row', gap: 2 },

  chevron: { position: 'absolute', right: 12, top: '50%' },

  // FAB
  fab: {
    position: 'absolute',
    right: 20,
    bottom: 24,
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: '#1565c0',
    justifyContent: 'center',
    alignItems: 'center',
    shadowColor: '#4fc3f7',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
    elevation: 8,
  },
});
