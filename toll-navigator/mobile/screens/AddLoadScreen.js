import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TextInput,
  TouchableOpacity,
  Switch,
  Alert,
  Platform,
  KeyboardAvoidingView,
  ActivityIndicator,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import AsyncStorage from '@react-native-async-storage/async-storage';

// ── Helpers ───────────────────────────────────────────────────────────────────

function parseNum(s) {
  const n = parseFloat(s.replace(/[^0-9.]/g, ''));
  return isNaN(n) ? 0 : n;
}

function calcNetPay(grossRate, fuelSurcharge, detention, factoringEnabled, factoringPct) {
  const total = parseNum(grossRate) + parseNum(fuelSurcharge) + parseNum(detention);
  if (factoringEnabled) {
    const fee = total * (parseNum(factoringPct) / 100);
    return total - fee;
  }
  return total;
}

function fmt(n) {
  return `$${n.toFixed(2)}`;
}

function todayStr() {
  return new Date().toISOString().slice(0, 10);
}

// ── Component ─────────────────────────────────────────────────────────────────

export default function AddLoadScreen({ navigation }) {
  const [grossRate,         setGrossRate]         = useState('');
  const [fuelSurcharge,     setFuelSurcharge]     = useState('');
  const [detention,         setDetention]         = useState('');
  const [factoringEnabled,  setFactoringEnabled]  = useState(false);
  const [factoringPct,      setFactoringPct]      = useState('3');
  const [miles,             setMiles]             = useState('');
  const [origin,            setOrigin]            = useState('');
  const [destination,       setDestination]       = useState('');
  const [broker,            setBroker]            = useState('');
  const [date,              setDate]              = useState(todayStr());
  const [saving,            setSaving]            = useState(false);

  const netPay = calcNetPay(grossRate, fuelSurcharge, detention, factoringEnabled, factoringPct);
  const totalGross = parseNum(grossRate) + parseNum(fuelSurcharge) + parseNum(detention);
  const factoringFee = factoringEnabled ? totalGross * (parseNum(factoringPct) / 100) : 0;
  const totalMiles = parseNum(miles);
  const ratePerMile = totalMiles > 0 ? netPay / totalMiles : 0;

  const handleSave = async () => {
    if (!grossRate || parseNum(grossRate) <= 0) {
      Alert.alert('Validation', 'Enter a gross rate.');
      return;
    }
    if (!miles || parseNum(miles) <= 0) {
      Alert.alert('Validation', 'Enter miles driven.');
      return;
    }

    setSaving(true);
    try {
      const stored = await AsyncStorage.getItem('loads');
      const list = stored ? JSON.parse(stored) : [];
      const newLoad = {
        id:               Date.now().toString(),
        grossRate:        parseNum(grossRate),
        fuelSurcharge:    parseNum(fuelSurcharge),
        detention:        parseNum(detention),
        factoringEnabled,
        factoringPct:     parseNum(factoringPct),
        factoringFee:     parseFloat(factoringFee.toFixed(2)),
        netPay:           parseFloat(netPay.toFixed(2)),
        miles:            parseNum(miles),
        origin:           origin.trim(),
        destination:      destination.trim(),
        broker:           broker.trim(),
        date,
      };
      list.unshift(newLoad);
      await AsyncStorage.setItem('loads', JSON.stringify(list));
      Alert.alert('Saved', `Load saved. Net Pay: ${fmt(netPay)}`, [
        { text: 'OK', onPress: () => navigation.goBack() },
      ]);
    } catch (err) {
      Alert.alert('Error', err.message || 'Could not save load.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <KeyboardAvoidingView
      style={styles.wrapper}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
    >
      <ScrollView style={styles.container} contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">

        {/* Header */}
        <View style={styles.headerRow}>
          <TouchableOpacity onPress={() => navigation.goBack()} style={styles.backBtn}>
            <Ionicons name="chevron-back" size={22} color="#4fc3f7" />
          </TouchableOpacity>
          <Text style={styles.title}>Add Load</Text>
        </View>

        {/* Revenue Section */}
        <View style={styles.sectionCard}>
          <Text style={styles.sectionTitle}>Revenue</Text>

          <Text style={styles.fieldLabel}>Gross Rate ($)</Text>
          <TextInput
            style={styles.input}
            value={grossRate}
            onChangeText={setGrossRate}
            placeholder="0.00"
            placeholderTextColor="#333"
            keyboardType="decimal-pad"
            selectionColor="#4fc3f7"
          />

          <Text style={styles.fieldLabel}>Fuel Surcharge ($)</Text>
          <TextInput
            style={styles.input}
            value={fuelSurcharge}
            onChangeText={setFuelSurcharge}
            placeholder="0.00"
            placeholderTextColor="#333"
            keyboardType="decimal-pad"
            selectionColor="#4fc3f7"
          />

          <Text style={styles.fieldLabel}>Detention Pay ($)</Text>
          <TextInput
            style={styles.input}
            value={detention}
            onChangeText={setDetention}
            placeholder="0.00"
            placeholderTextColor="#333"
            keyboardType="decimal-pad"
            selectionColor="#4fc3f7"
          />
        </View>

        {/* Factoring Section */}
        <View style={styles.sectionCard}>
          <View style={styles.factoringRow}>
            <View>
              <Text style={styles.sectionTitle}>Factoring</Text>
              <Text style={styles.factoringHint}>Deduct factoring fee from pay</Text>
            </View>
            <Switch
              value={factoringEnabled}
              onValueChange={setFactoringEnabled}
              trackColor={{ false: '#1e1e3a', true: '#1565c0' }}
              thumbColor={factoringEnabled ? '#4fc3f7' : '#444'}
            />
          </View>

          {factoringEnabled && (
            <>
              <Text style={styles.fieldLabel}>Factoring Rate (%)</Text>
              <TextInput
                style={styles.input}
                value={factoringPct}
                onChangeText={setFactoringPct}
                placeholder="3"
                placeholderTextColor="#333"
                keyboardType="decimal-pad"
                selectionColor="#4fc3f7"
              />
              {totalGross > 0 && (
                <View style={styles.factoringFeeRow}>
                  <Text style={styles.factoringFeeLabel}>Fee deducted:</Text>
                  <Text style={styles.factoringFeeValue}>-{fmt(factoringFee)}</Text>
                </View>
              )}
            </>
          )}
        </View>

        {/* Trip Details */}
        <View style={styles.sectionCard}>
          <Text style={styles.sectionTitle}>Trip Details</Text>

          <Text style={styles.fieldLabel}>Miles Driven</Text>
          <TextInput
            style={styles.input}
            value={miles}
            onChangeText={setMiles}
            placeholder="0"
            placeholderTextColor="#333"
            keyboardType="number-pad"
            selectionColor="#4fc3f7"
          />

          <Text style={styles.fieldLabel}>Origin</Text>
          <TextInput
            style={styles.input}
            value={origin}
            onChangeText={setOrigin}
            placeholder="e.g. Charlotte, NC"
            placeholderTextColor="#333"
            selectionColor="#4fc3f7"
          />

          <Text style={styles.fieldLabel}>Destination</Text>
          <TextInput
            style={styles.input}
            value={destination}
            onChangeText={setDestination}
            placeholder="e.g. Atlanta, GA"
            placeholderTextColor="#333"
            selectionColor="#4fc3f7"
          />

          <Text style={styles.fieldLabel}>Broker Name</Text>
          <TextInput
            style={styles.input}
            value={broker}
            onChangeText={setBroker}
            placeholder="e.g. Coyote Logistics"
            placeholderTextColor="#333"
            selectionColor="#4fc3f7"
          />

          <Text style={styles.fieldLabel}>Date</Text>
          <TextInput
            style={styles.input}
            value={date}
            onChangeText={setDate}
            placeholder="YYYY-MM-DD"
            placeholderTextColor="#333"
            selectionColor="#4fc3f7"
          />
        </View>

        {/* Net Pay Summary */}
        <View style={styles.netCard}>
          <Text style={styles.netCardTitle}>Net Pay Summary</Text>

          <View style={styles.netRow}>
            <Text style={styles.netLabel}>Gross Rate</Text>
            <Text style={styles.netValue}>{fmt(parseNum(grossRate))}</Text>
          </View>
          {parseNum(fuelSurcharge) > 0 && (
            <View style={styles.netRow}>
              <Text style={styles.netLabel}>+ Fuel Surcharge</Text>
              <Text style={styles.netValue}>{fmt(parseNum(fuelSurcharge))}</Text>
            </View>
          )}
          {parseNum(detention) > 0 && (
            <View style={styles.netRow}>
              <Text style={styles.netLabel}>+ Detention</Text>
              <Text style={styles.netValue}>{fmt(parseNum(detention))}</Text>
            </View>
          )}
          {factoringEnabled && factoringFee > 0 && (
            <View style={styles.netRow}>
              <Text style={styles.netLabel}>- Factoring ({factoringPct}%)</Text>
              <Text style={[styles.netValue, styles.colorRed]}>-{fmt(factoringFee)}</Text>
            </View>
          )}

          <View style={styles.netDivider} />

          <View style={styles.netRow}>
            <Text style={styles.netPayLabel}>Net Pay</Text>
            <Text style={[styles.netPayValue, netPay >= 0 ? styles.colorGreen : styles.colorRed]}>
              {fmt(netPay)}
            </Text>
          </View>

          {totalMiles > 0 && (
            <View style={styles.netRow}>
              <Text style={styles.netLabel}>Rate per Mile</Text>
              <Text style={[styles.netValue, styles.colorBlue]}>${ratePerMile.toFixed(2)}/mi</Text>
            </View>
          )}
        </View>

        {/* Save Button */}
        <TouchableOpacity
          style={[styles.saveBtn, saving && styles.btnDisabled]}
          onPress={handleSave}
          disabled={saving}
        >
          {saving ? (
            <ActivityIndicator color="#fff" size="small" />
          ) : (
            <Ionicons name="checkmark-circle" size={20} color="#fff" />
          )}
          <Text style={styles.saveBtnText}>{saving ? 'Saving…' : 'Save Load'}</Text>
        </TouchableOpacity>

      </ScrollView>
    </KeyboardAvoidingView>
  );
}

// ── Styles ────────────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  wrapper:   { flex: 1, backgroundColor: '#0d0d1a' },
  container: { flex: 1 },
  scroll:    { padding: 16, paddingBottom: 60 },

  // Header
  headerRow: { flexDirection: 'row', alignItems: 'center', marginBottom: 20, gap: 8 },
  backBtn:   { padding: 4 },
  title:     { color: '#fff', fontSize: 22, fontWeight: '800' },

  // Section card
  sectionCard: {
    backgroundColor: '#161629',
    borderRadius: 14,
    padding: 16,
    marginBottom: 14,
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

  // Fields
  fieldLabel: {
    color: '#888',
    fontSize: 11,
    fontWeight: '700',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginBottom: 8,
  },
  input: {
    backgroundColor: '#0d0d1a',
    borderWidth: 1,
    borderColor: '#2a2a4a',
    borderRadius: 10,
    paddingHorizontal: 14,
    paddingVertical: 12,
    color: '#fff',
    fontSize: 16,
    marginBottom: 16,
  },

  // Factoring
  factoringRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 14,
  },
  factoringHint: { color: '#555', fontSize: 12, marginTop: 2 },
  factoringFeeRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    backgroundColor: '#1a0a0a',
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 10,
    marginBottom: 4,
    borderWidth: 1,
    borderColor: '#3a1515',
  },
  factoringFeeLabel: { color: '#888', fontSize: 13 },
  factoringFeeValue: { color: '#ef9a9a', fontSize: 14, fontWeight: '700' },

  // Net card
  netCard: {
    backgroundColor: '#0a1f2e',
    borderRadius: 14,
    padding: 18,
    marginBottom: 20,
    borderWidth: 1,
    borderColor: '#1565c0',
  },
  netCardTitle: {
    color: '#4fc3f7',
    fontSize: 11,
    fontWeight: '700',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginBottom: 14,
  },
  netRow:     { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 5 },
  netLabel:   { color: '#888', fontSize: 13 },
  netValue:   { color: '#ccc', fontSize: 13, fontWeight: '600' },
  netDivider: { height: 1, backgroundColor: '#1e3a50', marginVertical: 10 },
  netPayLabel: { color: '#fff', fontSize: 16, fontWeight: '800' },
  netPayValue: { fontSize: 24, fontWeight: '900' },

  colorGreen: { color: '#66bb6a' },
  colorRed:   { color: '#ef9a9a' },
  colorBlue:  { color: '#4fc3f7' },

  // Save button
  saveBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    backgroundColor: '#1565c0',
    paddingVertical: 16,
    borderRadius: 12,
  },
  saveBtnText: { color: '#fff', fontSize: 16, fontWeight: '700' },
  btnDisabled: { opacity: 0.5 },
});
