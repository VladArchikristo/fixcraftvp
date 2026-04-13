import React, { useState } from 'react';
import {
  View, Text, TextInput, TouchableOpacity, StyleSheet,
  ScrollView, ActivityIndicator, Alert, KeyboardAvoidingView, Platform
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { calculateRoute } from '../services/api';

const TRUCK_TYPES = [
  { label: '2-Axle', value: '2-axle', icon: '🚛' },
  { label: '3-Axle', value: '3-axle', icon: '🚚' },
  { label: '5-Axle', value: '5-axle', icon: '🚜' },
];

const CITY_SUGGESTIONS = [
  'Dallas, TX', 'Houston, TX', 'San Antonio, TX', 'Austin, TX',
  'Los Angeles, CA', 'San Francisco, CA', 'Miami, FL', 'Orlando, FL',
  'Chicago, IL', 'New York, NY', 'Philadelphia, PA', 'Atlanta, GA',
];

export default function HomeScreen({ navigation }) {
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');
  const [truckType, setTruckType] = useState('5-axle');
  const [loading, setLoading] = useState(false);
  const [fromFocus, setFromFocus] = useState(false);
  const [toFocus, setToFocus] = useState(false);

  const fromSuggestions = CITY_SUGGESTIONS.filter(c =>
    from.length > 1 && c.toLowerCase().includes(from.toLowerCase())
  );
  const toSuggestions = CITY_SUGGESTIONS.filter(c =>
    to.length > 1 && c.toLowerCase().includes(to.toLowerCase())
  );

  const handleCalculate = async () => {
    if (!from.trim() || !to.trim()) {
      Alert.alert('Заполни маршрут', 'Введи город отправления и назначения');
      return;
    }
    setLoading(true);
    try {
      const response = await calculateRoute(from.trim(), to.trim(), truckType);
      navigation.navigate('Result', { result: response.data, from, to, truckType });
    } catch (err) {
      const msg = err.response?.data?.error || 'Ошибка соединения с сервером';
      Alert.alert('Ошибка', msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
    >
      <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">
        {/* Header */}
        <View style={styles.header}>
          <Text style={styles.logo}>🛣️ Toll Navigator</Text>
          <Text style={styles.subtitle}>Расчёт платных дорог для грузовиков</Text>
        </View>

        {/* From */}
        <View style={styles.card}>
          <Text style={styles.label}>📍 Откуда</Text>
          <View style={styles.inputRow}>
            <Ionicons name="location-outline" size={20} color="#4fc3f7" style={styles.inputIcon} />
            <TextInput
              style={styles.input}
              placeholder="Dallas, TX"
              placeholderTextColor="#555"
              value={from}
              onChangeText={setFrom}
              onFocus={() => setFromFocus(true)}
              onBlur={() => setTimeout(() => setFromFocus(false), 200)}
            />
          </View>
          {fromFocus && fromSuggestions.map(city => (
            <TouchableOpacity key={city} style={styles.suggestion} onPress={() => { setFrom(city); setFromFocus(false); }}>
              <Text style={styles.suggestionText}>{city}</Text>
            </TouchableOpacity>
          ))}
        </View>

        {/* Swap button */}
        <TouchableOpacity style={styles.swapBtn} onPress={() => { const tmp = from; setFrom(to); setTo(tmp); }}>
          <Ionicons name="swap-vertical" size={22} color="#4fc3f7" />
        </TouchableOpacity>

        {/* To */}
        <View style={styles.card}>
          <Text style={styles.label}>🏁 Куда</Text>
          <View style={styles.inputRow}>
            <Ionicons name="flag-outline" size={20} color="#81c784" style={styles.inputIcon} />
            <TextInput
              style={styles.input}
              placeholder="Houston, TX"
              placeholderTextColor="#555"
              value={to}
              onChangeText={setTo}
              onFocus={() => setToFocus(true)}
              onBlur={() => setTimeout(() => setToFocus(false), 200)}
            />
          </View>
          {toFocus && toSuggestions.map(city => (
            <TouchableOpacity key={city} style={styles.suggestion} onPress={() => { setTo(city); setToFocus(false); }}>
              <Text style={styles.suggestionText}>{city}</Text>
            </TouchableOpacity>
          ))}
        </View>

        {/* Truck type */}
        <View style={styles.card}>
          <Text style={styles.label}>🚛 Тип грузовика</Text>
          <View style={styles.truckRow}>
            {TRUCK_TYPES.map(t => (
              <TouchableOpacity
                key={t.value}
                style={[styles.truckBtn, truckType === t.value && styles.truckBtnActive]}
                onPress={() => setTruckType(t.value)}
              >
                <Text style={styles.truckIcon}>{t.icon}</Text>
                <Text style={[styles.truckLabel, truckType === t.value && styles.truckLabelActive]}>
                  {t.label}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>

        {/* Calculate button */}
        <TouchableOpacity
          style={[styles.calcBtn, loading && styles.calcBtnDisabled]}
          onPress={handleCalculate}
          disabled={loading}
        >
          {loading
            ? <ActivityIndicator color="#fff" />
            : <Text style={styles.calcBtnText}>Рассчитать маршрут →</Text>
          }
        </TouchableOpacity>

        <Text style={styles.hint}>80+ городов США • Данные 2026</Text>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0d0d1a' },
  scroll: { padding: 20, paddingBottom: 40 },
  header: { alignItems: 'center', marginBottom: 28, marginTop: 10 },
  logo: { fontSize: 26, fontWeight: '800', color: '#fff', letterSpacing: 0.5 },
  subtitle: { fontSize: 13, color: '#666', marginTop: 4 },
  card: {
    backgroundColor: '#161629',
    borderRadius: 14,
    padding: 16,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: '#1e1e3a',
  },
  label: { color: '#888', fontSize: 12, marginBottom: 10, fontWeight: '600', textTransform: 'uppercase', letterSpacing: 0.5 },
  inputRow: { flexDirection: 'row', alignItems: 'center' },
  inputIcon: { marginRight: 10 },
  input: { flex: 1, color: '#fff', fontSize: 16, paddingVertical: 4 },
  suggestion: { paddingVertical: 8, borderTopWidth: 1, borderTopColor: '#1e1e3a' },
  suggestionText: { color: '#4fc3f7', fontSize: 14 },
  swapBtn: {
    alignSelf: 'center',
    marginVertical: -4,
    zIndex: 10,
    backgroundColor: '#1a1a2e',
    borderRadius: 20,
    padding: 8,
    borderWidth: 1,
    borderColor: '#2a2a4a',
  },
  truckRow: { flexDirection: 'row', gap: 10 },
  truckBtn: {
    flex: 1, alignItems: 'center', padding: 12, borderRadius: 10,
    backgroundColor: '#0d0d1a', borderWidth: 1, borderColor: '#2a2a4a',
  },
  truckBtnActive: { borderColor: '#4fc3f7', backgroundColor: '#0d1f2d' },
  truckIcon: { fontSize: 22, marginBottom: 4 },
  truckLabel: { color: '#666', fontSize: 12, fontWeight: '600' },
  truckLabelActive: { color: '#4fc3f7' },
  calcBtn: {
    backgroundColor: '#4fc3f7',
    borderRadius: 14,
    padding: 16,
    alignItems: 'center',
    marginTop: 10,
  },
  calcBtnDisabled: { opacity: 0.6 },
  calcBtnText: { color: '#0d0d1a', fontSize: 16, fontWeight: '800' },
  hint: { textAlign: 'center', color: '#444', fontSize: 12, marginTop: 16 },
});
