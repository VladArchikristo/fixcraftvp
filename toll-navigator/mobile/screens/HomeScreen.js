import React, { useState, useEffect } from 'react';
import {
  View, Text, TextInput, TouchableOpacity, StyleSheet,
  ScrollView, ActivityIndicator, Alert, KeyboardAvoidingView, Platform, Modal,
  SafeAreaView
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { calculateRoute } from '../services/api';
import { checkLimit, incrementCalcs, upgradeToPremium, FREE_CALCULATIONS_LIMIT } from '../services/subscription';

// US states list for fuel purchase picker
const US_STATES = [
  'AL','AK','AZ','AR','CA','CO','CT','DE','FL','GA',
  'ID','IL','IN','IA','KS','KY','LA','ME','MD','MA',
  'MI','MN','MS','MO','MT','NE','NV','NH','NJ','NM',
  'NY','NC','ND','OH','OK','OR','PA','RI','SC','SD',
  'TN','TX','UT','VT','VA','WA','WV','WI','WY',
];

const TRUCK_TYPES = [
  { label: '2-Axle', value: '2-axle', icon: '🛻' },
  { label: '3-Axle', value: '3-axle', icon: '🚛' },
  { label: '5-Axle', value: '5-axle', icon: '🚛' },
];

const CITY_SUGGESTIONS = [
  'Dallas, TX', 'Houston, TX', 'San Antonio, TX', 'Austin, TX', 'Fort Worth, TX',
  'Los Angeles, CA', 'San Francisco, CA', 'San Diego, CA', 'Sacramento, CA',
  'Miami, FL', 'Orlando, FL', 'Tampa, FL', 'Jacksonville, FL',
  'Chicago, IL', 'New York, NY', 'Philadelphia, PA', 'Atlanta, GA',
  'Charlotte, NC', 'Nashville, TN', 'Memphis, TN',
  'Denver, CO', 'Phoenix, AZ', 'Las Vegas, NV',
  'Seattle, WA', 'Portland, OR', 'Boston, MA',
  'Detroit, MI', 'Columbus, OH', 'Cleveland, OH', 'Pittsburgh, PA',
  'Kansas City, MO', 'St. Louis, MO', 'Minneapolis, MN',
  'New Orleans, LA', 'Louisville, KY', 'Indianapolis, IN',
];

export default function HomeScreen({ navigation }) {
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');
  const [truckType, setTruckType] = useState('5-axle');
  const [loading, setLoading] = useState(false);
  const [fromFocus, setFromFocus] = useState(false);
  const [toFocus, setToFocus] = useState(false);
  // Fuel calculation
  const [showFuel, setShowFuel] = useState(false);
  const [mpg, setMpg] = useState('6.5');
  const [fuelPrice, setFuelPrice] = useState('3.80');
  // Fuel purchases by state (for precise IFTA)
  const [fuelPurchases, setFuelPurchases] = useState([]); // [{state, gallons}]
  const [showStatePicker, setShowStatePicker] = useState(null); // index of row with open picker
  // Subscription
  const [showPaywall, setShowPaywall] = useState(false);
  const [calcsRemaining, setCalcsRemaining] = useState(FREE_CALCULATIONS_LIMIT);

  const fromSuggestions = CITY_SUGGESTIONS.filter(c =>
    from.length > 1 && c.toLowerCase().includes(from.toLowerCase())
  );
  const toSuggestions = CITY_SUGGESTIONS.filter(c =>
    to.length > 1 && c.toLowerCase().includes(to.toLowerCase())
  );

  const handleClear = () => {
    setFrom('');
    setTo('');
    setTruckType('5-axle');
    setFromFocus(false);
    setToFocus(false);
    setMpg('6.5');
    setFuelPrice('3.80');
    setFuelPurchases([]);
    setShowStatePicker(null);
  };

  // Helpers for fuel purchases list
  const addFuelPurchase = () => {
    setFuelPurchases(prev => [...prev, { state: 'TX', gallons: '' }]);
  };

  const removeFuelPurchase = (index) => {
    setFuelPurchases(prev => prev.filter((_, i) => i !== index));
    if (showStatePicker === index) setShowStatePicker(null);
  };

  const updatePurchaseState = (index, state) => {
    setFuelPurchases(prev => prev.map((p, i) => i === index ? { ...p, state } : p));
    setShowStatePicker(null);
  };

  const updatePurchaseGallons = (index, gallons) => {
    setFuelPurchases(prev => prev.map((p, i) => i === index ? { ...p, gallons } : p));
  };

  useEffect(() => {
    checkLimit().then((res) => setCalcsRemaining(res.remaining));
  }, []);

  const handleCalculate = async () => {
    if (!from.trim() || !to.trim()) {
      Alert.alert('Enter Route', 'Enter origin and destination city');
      return;
    }
    if (showFuel) {
      const mpgVal = parseFloat(mpg);
      if (!mpg || isNaN(mpgVal) || mpgVal <= 0 || mpgVal > 100) {
        Alert.alert('Error', 'Enter valid fuel consumption (1-100 MPG)');
        return;
      }
    }
    // Check subscription limit
    const limitStatus = await checkLimit();
    if (!limitStatus.allowed) {
      setShowPaywall(true);
      return;
    }
    setLoading(true);
    try {
      await incrementCalcs();
      setCalcsRemaining(prev => Math.max(0, prev - 1));
      const response = await calculateRoute(from.trim(), to.trim(), truckType);
      const fuelData = showFuel ? {
        mpg: parseFloat(mpg) || 6.5,
        fuelPrice: parseFloat(fuelPrice) || 3.80,
      } : null;
      // Prepare fuel purchase data: only valid rows (state + gallons > 0)
      const validPurchases = showFuel
        ? fuelPurchases
            .map(p => ({ state: p.state, gallons: parseFloat(p.gallons) || 0 }))
            .filter(p => p.gallons > 0)
        : [];
      navigation.navigate('Result', {
        result: response.data, from, to, truckType, fuelData,
        fuelPurchases: validPurchases.length > 0 ? validPurchases : undefined,
      });
    } catch (err) {
      const msg = err.response?.data?.error || 'Server connection error';
      Alert.alert('Error', msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <SafeAreaView style={styles.container}>
    <KeyboardAvoidingView
      style={{ flex: 1 }}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
    >
      <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">
        {/* Header */}
        <View style={styles.header}>
          <Text style={styles.logo}>🛣️ HaulWallet</Text>
          <Text style={styles.subtitle}>Total route cost for trucks</Text>
        </View>

        {/* From */}
        <View style={styles.card}>
          <Text style={styles.label}>📍 From</Text>
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
          <Text style={styles.label}>🏁 To</Text>
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
          <Text style={styles.label}>🚛 Truck Type</Text>
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

        {/* Fuel Calculator Toggle */}
        <TouchableOpacity
          style={[styles.fuelToggle, showFuel && styles.fuelToggleActive]}
          onPress={() => setShowFuel(!showFuel)}
        >
          <Text style={styles.fuelToggleIcon}>⛽</Text>
          <View style={styles.fuelToggleText}>
            <Text style={[styles.fuelToggleTitle, showFuel && styles.fuelToggleTitleActive]}>
              Add fuel cost
            </Text>
            <Text style={styles.fuelToggleSub}>
              {showFuel ? 'Tap to hide' : 'MPG + price → total trip cost'}
            </Text>
          </View>
          <Ionicons
            name={showFuel ? 'chevron-up' : 'chevron-down'}
            size={18}
            color={showFuel ? '#4fc3f7' : '#555'}
          />
        </TouchableOpacity>

        {/* Fuel Inputs */}
        {showFuel && (
          <View style={styles.fuelCard}>
            <View style={styles.fuelRow}>
              <View style={styles.fuelField}>
                <Text style={styles.fuelLabel}>⛽ Fuel Economy (MPG)</Text>
                <TextInput
                  style={styles.fuelInput}
                  value={mpg}
                  onChangeText={setMpg}
                  keyboardType="decimal-pad"
                  placeholder="6.5"
                  placeholderTextColor="#555"
                />
                <Text style={styles.fuelHint}>Standard truck: 5.5–7 MPG</Text>
              </View>
              <View style={styles.fuelField}>
                <Text style={styles.fuelLabel}>💵 Price per gallon</Text>
                <TextInput
                  style={styles.fuelInput}
                  value={fuelPrice}
                  onChangeText={setFuelPrice}
                  keyboardType="decimal-pad"
                  placeholder="3.80"
                  placeholderTextColor="#555"
                />
                <Text style={styles.fuelHint}>Diesel currently ~$3.80</Text>
              </View>
            </View>
            {/* Fuel purchases by state section */}
            <View style={styles.purchasesSection}>
              <View style={styles.purchasesHeader}>
                <View>
                  <Text style={styles.purchasesTitle}>⛽ Fuel purchases by state</Text>
                  <Text style={styles.purchasesSub}>
                    {fuelPurchases.length > 0
                      ? `${fuelPurchases.length} state(s) — precise IFTA calculation`
                      : 'Optional — for precise IFTA'}
                  </Text>
                </View>
                <TouchableOpacity style={styles.addPurchaseBtn} onPress={addFuelPurchase}>
                  <Text style={styles.addPurchaseBtnText}>+ Add</Text>
                </TouchableOpacity>
              </View>

              {fuelPurchases.map((p, index) => (
                <View key={index} style={styles.purchaseRow}>
                  {/* State selection */}
                  <TouchableOpacity
                    style={styles.stateSelector}
                    onPress={() => setShowStatePicker(showStatePicker === index ? null : index)}
                  >
                    <Text style={styles.stateSelectorText}>{p.state}</Text>
                    <Text style={styles.stateSelectorArrow}>▼</Text>
                  </TouchableOpacity>

                  {/* State picker (inline dropdown) */}
                  {showStatePicker === index && (
                    <View style={styles.statePickerContainer}>
                      <ScrollView style={styles.statePickerScroll} nestedScrollEnabled>
                        {US_STATES.map(st => (
                          <TouchableOpacity
                            key={st}
                            style={[styles.stateOption, p.state === st && styles.stateOptionActive]}
                            onPress={() => updatePurchaseState(index, st)}
                          >
                            <Text style={[styles.stateOptionText, p.state === st && styles.stateOptionTextActive]}>
                              {st}
                            </Text>
                          </TouchableOpacity>
                        ))}
                      </ScrollView>
                    </View>
                  )}

                  {/* Gallons field */}
                  <TextInput
                    style={styles.gallonsInput}
                    value={p.gallons}
                    onChangeText={val => updatePurchaseGallons(index, val)}
                    keyboardType="decimal-pad"
                    placeholder="gallons"
                    placeholderTextColor="#444"
                  />

                  {/* Delete row */}
                  <TouchableOpacity
                    style={styles.removePurchaseBtn}
                    onPress={() => removeFuelPurchase(index)}
                  >
                    <Text style={styles.removePurchaseBtnText}>✕</Text>
                  </TouchableOpacity>
                </View>
              ))}
            </View>

            <Text style={styles.fuelNote}>
              📊 You'll see: tolls + fuel + IFTA breakdown + trip total
            </Text>
          </View>
        )}

        {/* Calculate button */}
        <TouchableOpacity
          style={[styles.calcBtn, loading && styles.calcBtnDisabled]}
          onPress={handleCalculate}
          disabled={loading}
        >
          {loading
            ? <ActivityIndicator color="#fff" />
            : <Text style={styles.calcBtnText}>
                {showFuel ? '⛽ Calculate full cost →' : 'Calculate route →'}
              </Text>
          }
        </TouchableOpacity>

        {/* Clear button */}
        {(from || to) && (
          <TouchableOpacity style={styles.clearBtn} onPress={handleClear}>
            <Ionicons name="close-circle-outline" size={16} color="#888" />
            <Text style={styles.clearBtnText}>Clear form</Text>
          </TouchableOpacity>
        )}

        <Text style={styles.hint}>80+ US cities • IFTA 2026 • Toll data 2026</Text>
      </ScrollView>

      {/* Premium Paywall Modal */}
      <Modal visible={showPaywall} transparent animationType="fade">
        <View style={styles.paywallOverlay}>
          <View style={styles.paywallCard}>
            <Text style={styles.paywallIcon}>🔒</Text>
            <Text style={styles.paywallTitle}>Daily Limit Reached</Text>
            <Text style={styles.paywallText}>
              You've used all {FREE_CALCULATIONS_LIMIT} free calculations today.{'\n'}
              Upgrade to Premium for unlimited route calculations.
            </Text>
            <TouchableOpacity
              style={styles.paywallBtn}
              onPress={async () => {
                await upgradeToPremium();
                setShowPaywall(false);
                setCalcsRemaining(Infinity);
                Alert.alert('Premium Activated', 'You now have unlimited calculations!');
              }}
            >
              <Text style={styles.paywallBtnText}>Upgrade to Premium</Text>
            </TouchableOpacity>
            <TouchableOpacity style={styles.paywallClose} onPress={() => setShowPaywall(false)}>
              <Text style={styles.paywallCloseText}>Maybe later</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>
    </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0d0d1a' },
  scroll: { padding: 20, paddingBottom: 40 },
  header: { alignItems: 'center', marginBottom: 28, marginTop: 10 },
  logo: { fontSize: 26, fontWeight: '800', color: '#fff', letterSpacing: 0.5, fontFamily: Platform.select({ ios: '-apple-system', android: 'Roboto' }) },
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
  truckRow: { flexDirection: 'row', gap: 8, flexWrap: 'nowrap' },
  truckBtn: {
    flex: 1, alignItems: 'center', paddingVertical: 10, paddingHorizontal: 6, borderRadius: 10,
    backgroundColor: '#0d0d1a', borderWidth: 1, borderColor: '#2a2a4a', minWidth: 0,
  },
  truckBtnActive: { borderColor: '#4fc3f7', backgroundColor: '#0d1f2d' },
  truckIcon: { fontSize: 22, marginBottom: 4 },
  truckLabel: { color: '#666', fontSize: 11, fontWeight: '600', textAlign: 'center' },
  truckLabelActive: { color: '#4fc3f7' },
  // Fuel toggle
  fuelToggle: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    backgroundColor: '#161629',
    borderRadius: 14,
    padding: 14,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: '#1e1e3a',
  },
  fuelToggleActive: {
    borderColor: '#4fc3f7',
    backgroundColor: '#0d1f2d',
  },
  fuelToggleIcon: { fontSize: 20 },
  fuelToggleText: { flex: 1 },
  fuelToggleTitle: { color: '#aaa', fontSize: 14, fontWeight: '700' },
  fuelToggleTitleActive: { color: '#4fc3f7' },
  fuelToggleSub: { color: '#555', fontSize: 11, marginTop: 2 },
  // Fuel card
  fuelCard: {
    backgroundColor: '#0a1a28',
    borderRadius: 14,
    padding: 16,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: '#4fc3f7',
  },
  fuelRow: { flexDirection: 'row', gap: 12, marginBottom: 12 },
  fuelField: { flex: 1 },
  fuelLabel: { color: '#888', fontSize: 11, fontWeight: '700', marginBottom: 6, textTransform: 'uppercase', letterSpacing: 0.5 },
  fuelInput: {
    backgroundColor: '#0d0d1a',
    color: '#fff',
    fontSize: 22,
    fontWeight: '800',
    borderRadius: 10,
    padding: 12,
    borderWidth: 1,
    borderColor: '#2a3a4a',
    textAlign: 'center',
  },
  fuelHint: { color: '#444', fontSize: 10, marginTop: 4, textAlign: 'center' },
  fuelNote: { color: '#4fc3f7', fontSize: 12, textAlign: 'center', fontWeight: '600' },
  // Fuel purchases section
  purchasesSection: {
    marginTop: 8,
    marginBottom: 12,
    borderTopWidth: 1,
    borderTopColor: '#1a2e3a',
    paddingTop: 12,
  },
  purchasesHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 10,
  },
  purchasesTitle: { color: '#aaa', fontSize: 12, fontWeight: '700', textTransform: 'uppercase', letterSpacing: 0.5 },
  purchasesSub: { color: '#555', fontSize: 10, marginTop: 2 },
  addPurchaseBtn: {
    backgroundColor: '#0d1f2d',
    borderWidth: 1,
    borderColor: '#4fc3f7',
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 5,
  },
  addPurchaseBtnText: { color: '#4fc3f7', fontSize: 12, fontWeight: '700' },
  purchaseRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 8,
  },
  stateSelector: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#0d0d1a',
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 10,
    borderWidth: 1,
    borderColor: '#2a3a4a',
    minWidth: 60,
    gap: 4,
  },
  stateSelectorText: { color: '#fff', fontSize: 14, fontWeight: '700' },
  stateSelectorArrow: { color: '#4fc3f7', fontSize: 10 },
  statePickerContainer: {
    position: 'absolute',
    top: 40,
    left: 0,
    zIndex: 100,
    backgroundColor: '#161629',
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#2a3a4a',
    width: 80,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.5,
    shadowRadius: 8,
    elevation: 10,
  },
  statePickerScroll: { maxHeight: 200 },
  stateOption: { paddingHorizontal: 12, paddingVertical: 8 },
  stateOptionActive: { backgroundColor: '#0d1f2d' },
  stateOptionText: { color: '#888', fontSize: 14 },
  stateOptionTextActive: { color: '#4fc3f7', fontWeight: '700' },
  gallonsInput: {
    flex: 1,
    backgroundColor: '#0d0d1a',
    color: '#fff',
    fontSize: 15,
    fontWeight: '700',
    borderRadius: 8,
    padding: 10,
    borderWidth: 1,
    borderColor: '#2a3a4a',
    textAlign: 'center',
  },
  removePurchaseBtn: {
    backgroundColor: '#1a0d0d',
    borderRadius: 8,
    padding: 10,
    borderWidth: 1,
    borderColor: '#3a1a1a',
  },
  removePurchaseBtnText: { color: '#ef9a9a', fontSize: 13, fontWeight: '700' },
  // Buttons
  calcBtn: {
    backgroundColor: '#4fc3f7',
    borderRadius: 14,
    padding: 16,
    alignItems: 'center',
    marginTop: 10,
  },
  calcBtnDisabled: { opacity: 0.6 },
  calcBtnText: { color: '#0d0d1a', fontSize: 16, fontWeight: '800' },
  clearBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    gap: 6, marginTop: 10, padding: 10,
  },
  clearBtnText: { color: '#888', fontSize: 13 },
  hint: { textAlign: 'center', color: '#444', fontSize: 12, marginTop: 16 },
  // Paywall
  paywallOverlay: {
    flex: 1, backgroundColor: 'rgba(0,0,0,0.8)',
    justifyContent: 'center', alignItems: 'center', padding: 24,
  },
  paywallCard: {
    backgroundColor: '#161629', borderRadius: 20, padding: 28,
    alignItems: 'center', borderWidth: 2, borderColor: '#4fc3f7', width: '100%', maxWidth: 340,
  },
  paywallIcon: { fontSize: 48, marginBottom: 12 },
  paywallTitle: { color: '#fff', fontSize: 20, fontWeight: '800', marginBottom: 12, textAlign: 'center' },
  paywallText: { color: '#888', fontSize: 14, textAlign: 'center', lineHeight: 22, marginBottom: 24 },
  paywallBtn: {
    backgroundColor: '#4fc3f7', borderRadius: 14, paddingVertical: 16,
    paddingHorizontal: 32, width: '100%', alignItems: 'center', marginBottom: 12,
  },
  paywallBtnText: { color: '#0d0d1a', fontSize: 16, fontWeight: '800' },
  paywallClose: { padding: 8 },
  paywallCloseText: { color: '#666', fontSize: 14 },
});
