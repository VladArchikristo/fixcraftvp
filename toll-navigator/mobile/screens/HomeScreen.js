import React, { useState, useEffect } from 'react';
import {
  View, Text, TextInput, TouchableOpacity, StyleSheet,
  ScrollView, ActivityIndicator, Alert, KeyboardAvoidingView, Platform, Modal,
  SafeAreaView
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { calculateRoute } from '../services/api';
import { checkLimit, incrementCalcs, upgradeToPremium, FREE_CALCULATIONS_LIMIT } from '../services/subscription';
import { COLORS, SPACING, RADIUS, SHADOW } from '../theme';

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
  { label: '3-Axle', value: '3-axle', icon: '🚚' },
  { label: '5-Axle', value: '5-axle', icon: '🚛' },
];

// Nominatim autocomplete
const NOMINATIM_URL = 'https://nominatim.openstreetmap.org/search';

async function fetchAddresses(query) {
  if (!query || query.length < 2) return [];
  try {
    const url = `${NOMINATIM_URL}?q=${encodeURIComponent(query + ', USA')}&format=json&limit=5&countrycodes=us&addressdetails=1`;
    const res = await fetch(url, { headers: { 'User-Agent': 'HaulWallet/1.0' } });
    const data = await res.json();
    if (!Array.isArray(data)) return [];
    return data.map(item => {
      const addr = item.address || {};
      const city = addr.city || addr.town || addr.village || addr.hamlet || '';
      const state = addr.state || '';
      const display = city && state ? `${city}, ${state}` : item.display_name;
      return { display, lat: item.lat, lon: item.lon };
    }).filter(x => x.display);
  } catch (e) {
    console.warn('Nominatim error:', e.message);
    return [];
  }
}

export default function HomeScreen({ navigation }) {
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');
  const [truckType, setTruckType] = useState('5-axle');
  const [loading, setLoading] = useState(false);
  const [fromFocus, setFromFocus] = useState(false);
  const [toFocus, setToFocus] = useState(false);
  // Autocomplete states
  const [fromSuggestions, setFromSuggestions] = useState([]);
  const [toSuggestions, setToSuggestions] = useState([]);
  const [addrLoading, setAddrLoading] = useState(false);
  // Fuel calculation
  const [showFuel, setShowFuel] = useState(false);
  const [mpg, setMpg] = useState('6.5');
  const [fuelPrice, setFuelPrice] = useState('3.80');
  // Fuel purchases by state
  const [fuelPurchases, setFuelPurchases] = useState([]);
  const [showStatePicker, setShowStatePicker] = useState(null);
  // Subscription
  const [showPaywall, setShowPaywall] = useState(false);
  const [calcsRemaining, setCalcsRemaining] = useState(FREE_CALCULATIONS_LIMIT);

  // Debounced Nominatim autocomplete
  useEffect(() => {
    if (!fromFocus || from.length < 2) { setFromSuggestions([]); return; }
    const timer = setTimeout(async () => {
      setAddrLoading(true);
      const results = await fetchAddresses(from);
      setFromSuggestions(results);
      setAddrLoading(false);
    }, 400);
    return () => clearTimeout(timer);
  }, [from, fromFocus]);

  useEffect(() => {
    if (!toFocus || to.length < 2) { setToSuggestions([]); return; }
    const timer = setTimeout(async () => {
      setAddrLoading(true);
      const results = await fetchAddresses(to);
      setToSuggestions(results);
      setAddrLoading(false);
    }, 400);
    return () => clearTimeout(timer);
  }, [to, toFocus]);

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
    checkLimit().then((res) => setCalcsRemaining(res.remaining)).catch(() => {});
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
          <View style={styles.logoBadge}>
            <Ionicons name="navigate" size={22} color={COLORS.textInverse} />
          </View>
          <Text style={styles.logo}>HaulWallet</Text>
          <Text style={styles.subtitle}>Total route cost for trucks</Text>
          <View style={styles.statsRow}>
            <View style={styles.statChip}>
              <Ionicons name="map-outline" size={12} color={COLORS.primary} />
              <Text style={styles.statChipText}>80+ cities</Text>
            </View>
            <View style={styles.statChip}>
              <Ionicons name="receipt-outline" size={12} color={COLORS.primary} />
              <Text style={styles.statChipText}>IFTA 2026</Text>
            </View>
            <View style={styles.statChip}>
              <Ionicons name="shield-checkmark-outline" size={12} color={COLORS.primary} />
              <Text style={styles.statChipText}>Toll data 2026</Text>
            </View>
          </View>
        </View>

        {/* From */}
        <View style={styles.card}>
          <Text style={styles.label}>📍 From</Text>
          <View style={styles.inputRow}>
            <Ionicons name="location-outline" size={20} color={COLORS.primary} style={styles.inputIcon} />
            <TextInput
              style={styles.input}
              placeholder="Dallas, TX"
              placeholderTextColor={COLORS.textMuted}
              value={from}
              onChangeText={setFrom}
              onFocus={() => setFromFocus(true)}
              onBlur={() => setTimeout(() => setFromFocus(false), 200)}
            />
          </View>
          {fromFocus && fromSuggestions.map((city, i) => (
            <TouchableOpacity key={`from-${i}`} style={styles.suggestion} onPress={() => { setFrom(city.display); setFromFocus(false); }}>
              <Text style={styles.suggestionText}>{city.display}</Text>
            </TouchableOpacity>
          ))}
          {fromFocus && addrLoading && from.length > 1 && (
            <ActivityIndicator size="small" color={COLORS.primary} style={{ marginVertical: 8 }} />
          )}
        </View>

        {/* Swap button */}
        <TouchableOpacity style={styles.swapBtn} onPress={() => { const tmp = from; setFrom(to); setTo(tmp); }}>
          <Ionicons name="swap-vertical" size={22} color={COLORS.primary} />
        </TouchableOpacity>

        {/* To */}
        <View style={styles.card}>
          <Text style={styles.label}>🏁 To</Text>
          <View style={styles.inputRow}>
            <Ionicons name="flag-outline" size={20} color={COLORS.success} style={styles.inputIcon} />
            <TextInput
              style={styles.input}
              placeholder="Houston, TX"
              placeholderTextColor={COLORS.textMuted}
              value={to}
              onChangeText={setTo}
              onFocus={() => setToFocus(true)}
              onBlur={() => setTimeout(() => setToFocus(false), 200)}
            />
          </View>
          {toFocus && toSuggestions.map((city, i) => (
            <TouchableOpacity key={`to-${i}`} style={styles.suggestion} onPress={() => { setTo(city.display); setToFocus(false); }}>
              <Text style={styles.suggestionText}>{city.display}</Text>
            </TouchableOpacity>
          ))}
          {toFocus && addrLoading && to.length > 1 && (
            <ActivityIndicator size="small" color={COLORS.primary} style={{ marginVertical: 8 }} />
          )}
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
            color={showFuel ? COLORS.primary : COLORS.textMuted}
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
                  placeholderTextColor={COLORS.textMuted}
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
                  placeholderTextColor={COLORS.textMuted}
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
                    placeholderTextColor={COLORS.textMuted}
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
            ? <ActivityIndicator color={COLORS.textInverse} />
            : <Text style={styles.calcBtnText}>
                {showFuel ? '⛽ Calculate full cost →' : 'Calculate route →'}
              </Text>
          }
        </TouchableOpacity>

        {/* Clear button */}
        {(from || to) && (
          <TouchableOpacity style={styles.clearBtn} onPress={handleClear}>
            <Ionicons name="close-circle-outline" size={16} color={COLORS.textSecondary} />
            <Text style={styles.clearBtnText}>Clear form</Text>
          </TouchableOpacity>
        )}

        {/* Quick nav */}
        <View style={styles.quickNav}>
          <TouchableOpacity style={styles.quickNavBtn} onPress={() => navigation.navigate('History')}>
            <Ionicons name="time-outline" size={18} color={COLORS.primary} />
            <Text style={styles.quickNavText}>History</Text>
          </TouchableOpacity>
          <TouchableOpacity style={styles.quickNavBtn} onPress={() => navigation.navigate('ExpenseDashboard')}>
            <Ionicons name="wallet-outline" size={18} color={COLORS.primary} />
            <Text style={styles.quickNavText}>Expenses</Text>
          </TouchableOpacity>
          <TouchableOpacity style={styles.quickNavBtn} onPress={() => navigation.navigate('IFTADashboard')}>
            <Ionicons name="document-text-outline" size={18} color={COLORS.primary} />
            <Text style={styles.quickNavText}>IFTA</Text>
          </TouchableOpacity>
        </View>
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
                setCalcsRemaining(9999);
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
  container: { flex: 1, backgroundColor: COLORS.bg },
  scroll: { padding: 20, paddingBottom: 40 },
  header: { alignItems: 'center', marginBottom: 28, marginTop: 10 },
  logoBadge: {
    width: 52, height: 52, borderRadius: 16,
    backgroundColor: COLORS.accent, alignItems: 'center', justifyContent: 'center',
    marginBottom: SPACING.sm,
    borderWidth: 2,
    borderColor: COLORS.accentGlow,
    ...SHADOW.accent,
  },
  logo: { fontSize: 28, fontWeight: '800', color: COLORS.textPrimary, letterSpacing: 1, fontFamily: Platform.select({ ios: '-apple-system', android: 'Roboto' }) },
  subtitle: { fontSize: 14, color: COLORS.textMuted, marginTop: SPACING.xs, fontWeight: '500' },
  statsRow: { flexDirection: 'row', gap: SPACING.sm, marginTop: SPACING.md },
  statChip: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    backgroundColor: COLORS.primaryLight, borderRadius: RADIUS.full,
    paddingHorizontal: 10, paddingVertical: 5,
  },
  statChipText: { fontSize: 11, fontWeight: '600', color: COLORS.primary },
  card: {
    backgroundColor: COLORS.bgCard,
    borderRadius: 14,
    padding: SPACING.md,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: COLORS.bgCardAlt,
    ...SHADOW.sm,
  },
  label: { color: COLORS.textSecondary, fontSize: 12, marginBottom: 10, fontWeight: '600', textTransform: 'uppercase', letterSpacing: 0.5 },
  inputRow: { flexDirection: 'row', alignItems: 'center' },
  inputIcon: { marginRight: 10 },
  input: { flex: 1, color: COLORS.textPrimary, fontSize: 16, paddingVertical: SPACING.xs },
  suggestion: { paddingVertical: SPACING.sm, borderTopWidth: 1, borderTopColor: COLORS.bgCardAlt },
  suggestionText: { color: COLORS.primary, fontSize: 14 },
  swapBtn: {
    alignSelf: 'center',
    marginVertical: -4,
    zIndex: 10,
    backgroundColor: COLORS.bgCardAlt,
    borderRadius: 20,
    padding: SPACING.sm,
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  truckRow: { flexDirection: 'row', gap: SPACING.sm, flexWrap: 'nowrap' },
  truckBtn: {
    flex: 1, alignItems: 'center', paddingVertical: 10, paddingHorizontal: 6, borderRadius: 10,
    backgroundColor: COLORS.bg, borderWidth: 1, borderColor: COLORS.border, minWidth: 0,
  },
  truckBtnActive: { borderColor: COLORS.primary, backgroundColor: COLORS.primaryLight },
  truckIcon: { fontSize: 22, marginBottom: SPACING.xs },
  truckLabel: { color: COLORS.textMuted, fontSize: 11, fontWeight: '600', textAlign: 'center' },
  truckLabelActive: { color: COLORS.primary },
  // Fuel toggle
  fuelToggle: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    backgroundColor: COLORS.bgCard,
    borderRadius: 14,
    padding: 14,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: COLORS.bgCardAlt,
  },
  fuelToggleActive: {
    borderColor: COLORS.primary,
    backgroundColor: COLORS.primaryLight,
  },
  fuelToggleIcon: { fontSize: 20 },
  fuelToggleText: { flex: 1 },
  fuelToggleTitle: { color: COLORS.textSecondary, fontSize: 14, fontWeight: '700' },
  fuelToggleTitleActive: { color: COLORS.primary },
  fuelToggleSub: { color: COLORS.textMuted, fontSize: 11, marginTop: 2 },
  // Fuel card
  fuelCard: {
    backgroundColor: COLORS.primaryLight,
    borderRadius: 14,
    padding: SPACING.md,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: COLORS.primary,
  },
  fuelRow: { flexDirection: 'row', gap: 12, marginBottom: 12 },
  fuelField: { flex: 1 },
  fuelLabel: { color: COLORS.textSecondary, fontSize: 11, fontWeight: '700', marginBottom: 6, textTransform: 'uppercase', letterSpacing: 0.5 },
  fuelInput: {
    backgroundColor: COLORS.bg,
    color: COLORS.textPrimary,
    fontSize: 22,
    fontWeight: '800',
    borderRadius: 10,
    padding: 12,
    borderWidth: 1,
    borderColor: COLORS.border,
    textAlign: 'center',
  },
  fuelHint: { color: COLORS.tabInactive, fontSize: 10, marginTop: SPACING.xs, textAlign: 'center' },
  fuelNote: { color: COLORS.primary, fontSize: 12, textAlign: 'center', fontWeight: '600' },
  // Fuel purchases section
  purchasesSection: {
    marginTop: SPACING.sm,
    marginBottom: 12,
    borderTopWidth: 1,
    borderTopColor: COLORS.border,
    paddingTop: 12,
  },
  purchasesHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 10,
  },
  purchasesTitle: { color: COLORS.textSecondary, fontSize: 12, fontWeight: '700', textTransform: 'uppercase', letterSpacing: 0.5 },
  purchasesSub: { color: COLORS.textMuted, fontSize: 10, marginTop: 2 },
  addPurchaseBtn: {
    backgroundColor: COLORS.primaryLight,
    borderWidth: 1,
    borderColor: COLORS.primary,
    borderRadius: RADIUS.sm,
    paddingHorizontal: 10,
    paddingVertical: 5,
  },
  addPurchaseBtnText: { color: COLORS.primary, fontSize: 12, fontWeight: '700' },
  purchaseRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: SPACING.sm,
    marginBottom: SPACING.sm,
  },
  stateSelector: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: COLORS.bg,
    borderRadius: RADIUS.sm,
    paddingHorizontal: 10,
    paddingVertical: 10,
    borderWidth: 1,
    borderColor: COLORS.border,
    minWidth: 60,
    gap: 4,
  },
  stateSelectorText: { color: COLORS.textPrimary, fontSize: 14, fontWeight: '700' },
  stateSelectorArrow: { color: COLORS.primary, fontSize: 10 },
  statePickerContainer: {
    position: 'absolute',
    top: 40,
    left: 0,
    zIndex: 100,
    backgroundColor: COLORS.bgCard,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: COLORS.border,
    width: 80,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.5,
    shadowRadius: 8,
    elevation: 10,
  },
  statePickerScroll: { maxHeight: 200 },
  stateOption: { paddingHorizontal: 12, paddingVertical: SPACING.sm },
  stateOptionActive: { backgroundColor: COLORS.primaryLight },
  stateOptionText: { color: COLORS.textSecondary, fontSize: 14 },
  stateOptionTextActive: { color: COLORS.primary, fontWeight: '700' },
  gallonsInput: {
    flex: 1,
    backgroundColor: COLORS.bg,
    color: COLORS.textPrimary,
    fontSize: 15,
    fontWeight: '700',
    borderRadius: RADIUS.sm,
    padding: 10,
    borderWidth: 1,
    borderColor: COLORS.border,
    textAlign: 'center',
  },
  removePurchaseBtn: {
    backgroundColor: COLORS.errorLight,
    borderRadius: RADIUS.sm,
    padding: 10,
    borderWidth: 1,
    borderColor: COLORS.error + '33',
  },
  removePurchaseBtnText: { color: COLORS.error, fontSize: 13, fontWeight: '700' },
  // Buttons
  calcBtn: {
    backgroundColor: COLORS.accent,
    borderRadius: 14,
    padding: SPACING.md,
    alignItems: 'center',
    marginTop: 10,
    ...SHADOW.accent,
  },
  calcBtnDisabled: { opacity: 0.6 },
  calcBtnText: { color: COLORS.textInverse, fontSize: 16, fontWeight: '800', letterSpacing: 0.3 },
  clearBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    gap: 6, marginTop: 10, padding: 10,
  },
  clearBtnText: { color: COLORS.textSecondary, fontSize: 13 },
  quickNav: {
    flexDirection: 'row', gap: SPACING.sm, marginTop: SPACING.lg,
  },
  quickNavBtn: {
    flex: 1, alignItems: 'center', paddingVertical: 14,
    backgroundColor: COLORS.bgCard, borderRadius: RADIUS.md,
    borderWidth: 1, borderColor: COLORS.bgCardAlt,
    ...SHADOW.sm,
  },
  quickNavText: { fontSize: 11, fontWeight: '600', color: COLORS.textSecondary, marginTop: SPACING.xs },
  // Paywall
  paywallOverlay: {
    flex: 1, backgroundColor: 'rgba(0,0,0,0.8)',
    justifyContent: 'center', alignItems: 'center', padding: SPACING.lg,
  },
  paywallCard: {
    backgroundColor: COLORS.bgCard, borderRadius: 20, padding: 28,
    alignItems: 'center', borderWidth: 2, borderColor: COLORS.primary, width: '100%', maxWidth: 340,
  },
  paywallIcon: { fontSize: 48, marginBottom: 12 },
  paywallTitle: { color: COLORS.textPrimary, fontSize: 20, fontWeight: '800', marginBottom: 12, textAlign: 'center' },
  paywallText: { color: COLORS.textSecondary, fontSize: 14, textAlign: 'center', lineHeight: 22, marginBottom: SPACING.lg },
  paywallBtn: {
    backgroundColor: COLORS.accent, borderRadius: 14, paddingVertical: SPACING.md,
    paddingHorizontal: SPACING.xl, width: '100%', alignItems: 'center', marginBottom: 12,
  },
  paywallBtnText: { color: COLORS.textInverse, fontSize: 16, fontWeight: '800' },
  paywallClose: { padding: SPACING.sm },
  paywallCloseText: { color: COLORS.textMuted, fontSize: 14 },
});
