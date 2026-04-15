import React, { useState, useEffect } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  ActivityIndicator, Alert,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../services/api';

function formatDate(dateStr) {
  if (!dateStr) return '';
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return dateStr;
  return d.toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' });
}

export default function TripDetailScreen({ route, navigation }) {
  const { tripId } = route.params;
  const [trip, setTrip] = useState(null);
  const [loading, setLoading] = useState(true);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    loadTrip();
  }, [tripId]);

  const loadTrip = async () => {
    setLoading(true);
    setError(null);
    try {
      const { data } = await api.get(`/api/trips/${tripId}`);
      setTrip(data);
    } catch (err) {
      const msg = err.response?.data?.error || 'Failed to load trip';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = () => {
    Alert.alert(
      'Delete trip?',
      `${trip.from_city} → ${trip.to_city}\n\nThis action cannot be undone.`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Delete',
          style: 'destructive',
          onPress: confirmDelete,
        },
      ]
    );
  };

  const confirmDelete = async () => {
    setDeleting(true);
    try {
      await api.delete(`/api/trips/${tripId}`);
      navigation.goBack();
    } catch (err) {
      const msg = err.response?.data?.error || 'Failed to delete trip';
      Alert.alert('Error', msg);
    } finally {
      setDeleting(false);
    }
  };

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color="#4fc3f7" />
        <Text style={styles.loadingText}>Loading trip...</Text>
      </View>
    );
  }

  if (error || !trip) {
    return (
      <View style={styles.center}>
        <Ionicons name="alert-circle-outline" size={48} color="#ef9a9a" />
        <Text style={styles.errorText}>{error || 'Trip not found'}</Text>
        <TouchableOpacity style={styles.retryBtn} onPress={loadTrip}>
          <Text style={styles.retryText}>Retry</Text>
        </TouchableOpacity>
      </View>
    );
  }

  const stateMiles = trip.state_miles || {};
  const stateEntries = Object.entries(stateMiles).sort((a, b) => b[1] - a[1]);
  const totalCost = ((trip.toll_cost || 0) + (trip.fuel_cost || 0)).toFixed(2);
  const fuelPurchases = trip.fuel_purchases || [];

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.scroll}>
      {/* Route */}
      <View style={styles.routeCard}>
        <View style={styles.routeRow}>
          <View style={styles.cityBlock}>
            <Text style={styles.cityLabel}>ИЗ</Text>
            <Text style={styles.cityName}>{trip.from_city}</Text>
          </View>
          <Ionicons name="arrow-forward" size={20} color="#4fc3f7" style={styles.arrow} />
          <View style={[styles.cityBlock, { alignItems: 'flex-end' }]}>
            <Text style={styles.cityLabel}>В</Text>
            <Text style={styles.cityName}>{trip.to_city}</Text>
          </View>
        </View>

        <View style={styles.routeMeta}>
          <View style={styles.metaItem}>
            <Ionicons name="calendar-outline" size={14} color="#555" />
            <Text style={styles.metaText}>{formatDate(trip.created_at)}</Text>
          </View>
          <View style={styles.metaItem}>
            <Ionicons name="navigate-outline" size={14} color="#555" />
            <Text style={styles.metaText}>{(trip.total_miles || 0).toFixed(1)} mi</Text>
          </View>
          <View style={styles.metaItem}>
            <Ionicons name="speedometer-outline" size={14} color="#555" />
            <Text style={styles.metaText}>{trip.mpg || 6.5} MPG</Text>
          </View>
        </View>

        <View style={styles.quarterBadge}>
          <Text style={styles.quarterText}>Q{trip.quarter} {trip.year}</Text>
        </View>
      </View>

      {/* Costs */}
      <View style={styles.sectionCard}>
        <Text style={styles.sectionTitle}>Costs</Text>
        <View style={styles.costsRow}>
          <View style={styles.costItem}>
            <Text style={styles.costLabel}>Tolls</Text>
            <Text style={styles.costValue}>${(trip.toll_cost || 0).toFixed(2)}</Text>
          </View>
          <View style={styles.costItem}>
            <Text style={styles.costLabel}>Fuel</Text>
            <Text style={styles.costValue}>${(trip.fuel_cost || 0).toFixed(2)}</Text>
          </View>
          <View style={[styles.costItem, styles.costTotalItem]}>
            <Text style={styles.costTotalLabel}>Total</Text>
            <Text style={styles.costTotalValue}>${totalCost}</Text>
          </View>
        </View>
      </View>

      {/* IFTA — miles by state */}
      {stateEntries.length > 0 && (
        <View style={styles.sectionCard}>
          <Text style={styles.sectionTitle}>IFTA — miles by state</Text>
          {stateEntries.map(([state, miles]) => (
            <View key={state} style={styles.stateRow}>
              <Text style={styles.stateCode}>{state}</Text>
              <View style={styles.stateBarWrap}>
                <View
                  style={[
                    styles.stateBar,
                    { width: `${Math.min((miles / (trip.total_miles || 1)) * 100, 100)}%` },
                  ]}
                />
              </View>
              <Text style={styles.stateMiles}>{parseFloat(miles).toFixed(1)} mi</Text>
            </View>
          ))}
        </View>
      )}

      {/* Trip fuel purchases */}
      {fuelPurchases.length > 0 && (
        <View style={styles.sectionCard}>
          <Text style={styles.sectionTitle}>Trip fuel purchases</Text>
          {fuelPurchases.map((fp, idx) => (
            <View key={fp.id || idx} style={styles.fuelRow}>
              <View style={styles.fuelLeft}>
                <Text style={styles.fuelState}>{fp.state}</Text>
                {fp.station_name ? <Text style={styles.fuelStation}>{fp.station_name}</Text> : null}
              </View>
              <View style={styles.fuelRight}>
                <Text style={styles.fuelGallons}>{parseFloat(fp.gallons || 0).toFixed(2)} gal</Text>
                {fp.price_per_gallon > 0 && (
                  <Text style={styles.fuelPrice}>${parseFloat(fp.price_per_gallon).toFixed(3)}/gal</Text>
                )}
              </View>
            </View>
          ))}
        </View>
      )}

      {/* Delete button */}
      <TouchableOpacity
        style={[styles.deleteBtn, deleting && styles.deleteBtnDisabled]}
        onPress={handleDelete}
        disabled={deleting}
      >
        {deleting
          ? <ActivityIndicator size="small" color="#fff" />
          : <Ionicons name="trash-outline" size={18} color="#fff" />
        }
        <Text style={styles.deleteBtnText}>{deleting ? 'Deleting...' : 'Delete Trip'}</Text>
      </TouchableOpacity>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0d0d1a' },
  scroll: { padding: 16, paddingBottom: 40 },

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

  // Route card
  routeCard: {
    backgroundColor: '#161629',
    borderRadius: 14,
    padding: 16,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: '#1e1e3a',
  },
  routeRow: { flexDirection: 'row', alignItems: 'center', marginBottom: 12 },
  cityBlock: { flex: 1 },
  arrow: { marginHorizontal: 10 },
  cityLabel: { color: '#444', fontSize: 10, fontWeight: '700', letterSpacing: 1, marginBottom: 2 },
  cityName: { color: '#fff', fontSize: 16, fontWeight: '800' },
  routeMeta: { flexDirection: 'row', gap: 16, flexWrap: 'wrap' },
  metaItem: { flexDirection: 'row', alignItems: 'center', gap: 5 },
  metaText: { color: '#555', fontSize: 13 },
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

  // Section cards
  sectionCard: {
    backgroundColor: '#161629',
    borderRadius: 14,
    padding: 16,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: '#1e1e3a',
  },
  sectionTitle: {
    color: '#888',
    fontSize: 11,
    fontWeight: '700',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginBottom: 14,
  },

  // Costs
  costsRow: { flexDirection: 'row', gap: 10 },
  costItem: { flex: 1, alignItems: 'center' },
  costLabel: { color: '#555', fontSize: 10, fontWeight: '700', textTransform: 'uppercase', marginBottom: 4 },
  costValue: { color: '#aaa', fontSize: 14, fontWeight: '700' },
  costTotalItem: {
    borderLeftWidth: 1,
    borderLeftColor: '#1e1e3a',
    paddingLeft: 10,
  },
  costTotalLabel: { color: '#888', fontSize: 10, fontWeight: '700', textTransform: 'uppercase', marginBottom: 4 },
  costTotalValue: { color: '#4fc3f7', fontSize: 17, fontWeight: '800' },

  // State rows
  stateRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 10,
    gap: 10,
  },
  stateCode: { color: '#fff', fontSize: 14, fontWeight: '700', width: 32 },
  stateBarWrap: {
    flex: 1,
    height: 6,
    backgroundColor: '#1e1e3a',
    borderRadius: 3,
    overflow: 'hidden',
  },
  stateBar: { height: '100%', backgroundColor: '#4fc3f7', borderRadius: 3 },
  stateMiles: { color: '#555', fontSize: 12, width: 60, textAlign: 'right' },

  // Fuel rows
  fuelRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: '#1a1a2a',
  },
  fuelLeft: { flex: 1 },
  fuelState: { color: '#fff', fontSize: 14, fontWeight: '700' },
  fuelStation: { color: '#555', fontSize: 12, marginTop: 2 },
  fuelRight: { alignItems: 'flex-end' },
  fuelGallons: { color: '#81c784', fontSize: 13, fontWeight: '700' },
  fuelPrice: { color: '#555', fontSize: 11, marginTop: 2 },

  // Delete button
  deleteBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 10,
    backgroundColor: '#c62828',
    paddingVertical: 16,
    borderRadius: 14,
    marginTop: 8,
  },
  deleteBtnDisabled: { backgroundColor: '#5a1515', opacity: 0.7 },
  deleteBtnText: { color: '#fff', fontSize: 15, fontWeight: '800' },
});
