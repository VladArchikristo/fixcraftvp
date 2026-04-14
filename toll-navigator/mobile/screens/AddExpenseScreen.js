import React, { useState, useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TextInput,
  TouchableOpacity,
  Alert,
  Modal,
  Platform,
  KeyboardAvoidingView,
  ActivityIndicator,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import AsyncStorage from '@react-native-async-storage/async-storage';

// ── Constants ─────────────────────────────────────────────────────────────────

const CATEGORIES = [
  { key: 'fuel',        label: 'Fuel',        icon: 'flame',                    color: '#ff7043' },
  { key: 'maintenance', label: 'Maintenance',  icon: 'build',                    color: '#ffa726' },
  { key: 'tolls',       label: 'Tolls',        icon: 'car',                      color: '#ab47bc' },
  { key: 'permits',     label: 'Permits',      icon: 'document-text',            color: '#42a5f5' },
  { key: 'food',        label: 'Food',         icon: 'fast-food',                color: '#66bb6a' },
  { key: 'insurance',   label: 'Insurance',    icon: 'shield-checkmark',         color: '#26c6da' },
  { key: 'scales',      label: 'Scales',       icon: 'scale',                    color: '#ec407a' },
  { key: 'parking',     label: 'Parking',      icon: 'car-sport',                color: '#5c6bc0' },
  { key: 'other',       label: 'Other',        icon: 'ellipsis-horizontal-circle', color: '#78909c' },
];

const SCAN_MOCK = [
  { category: 'fuel',        amount: '142.50', vendor: "Love's #450" },
  { category: 'fuel',        amount: '189.00', vendor: 'Pilot #882' },
  { category: 'maintenance', amount: '85.00',  vendor: 'TA Truck Service' },
  { category: 'tolls',       amount: '24.50',  vendor: 'E-ZPass' },
  { category: 'food',        amount: '18.75',  vendor: 'Subway' },
];

function todayStr() {
  return new Date().toISOString().slice(0, 10);
}

// ── Component ─────────────────────────────────────────────────────────────────

export default function AddExpenseScreen({ navigation }) {
  const [mode, setMode]             = useState('manual'); // 'manual' | 'scan'
  const [category, setCategory]     = useState('fuel');
  const [amount, setAmount]         = useState('');
  const [vendor, setVendor]         = useState('');
  const [date, setDate]             = useState(todayStr());
  const [notes, setNotes]           = useState('');
  const [scanning, setScanning]     = useState(false);
  const [scanned, setScanned]       = useState(null);  // { category, amount, vendor }
  const [showCatModal, setShowCatModal] = useState(false);
  const [saving, setSaving]         = useState(false);

  // ── Mock receipt scan ─────────────────────────────────────────────────────

  const handleScan = () => {
    setScanning(true);
    // Simulate camera + OCR (1.5s)
    setTimeout(() => {
      const result = SCAN_MOCK[Math.floor(Math.random() * SCAN_MOCK.length)];
      setScanned(result);
      setCategory(result.category);
      setAmount(result.amount);
      setVendor(result.vendor);
      setScanning(false);
    }, 1500);
  };

  const handleConfirmScan = () => {
    setScanned(null);
    setMode('manual');
  };

  // ── Save ─────────────────────────────────────────────────────────────────

  const handleSave = async () => {
    if (!amount || parseFloat(amount) <= 0) {
      Alert.alert('Validation', 'Enter a valid amount.');
      return;
    }
    if (!vendor.trim()) {
      Alert.alert('Validation', 'Enter a vendor name.');
      return;
    }

    setSaving(true);
    try {
      const stored = await AsyncStorage.getItem('expenses');
      const list = stored ? JSON.parse(stored) : [];
      const newItem = {
        id:       Date.now().toString(),
        category,
        amount:   parseFloat(amount),
        vendor:   vendor.trim(),
        date,
        notes:    notes.trim(),
      };
      list.unshift(newItem);
      await AsyncStorage.setItem('expenses', JSON.stringify(list));
      Alert.alert('Saved', 'Expense added.', [
        { text: 'OK', onPress: () => navigation.goBack() },
      ]);
    } catch (err) {
      Alert.alert('Error', err.message || 'Could not save expense.');
    } finally {
      setSaving(false);
    }
  };

  // ── Render ────────────────────────────────────────────────────────────────

  const selectedCat = CATEGORIES.find((c) => c.key === category) || CATEGORIES[0];

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
          <Text style={styles.title}>Add Expense</Text>
        </View>

        {/* Mode Toggle */}
        <View style={styles.modeRow}>
          <TouchableOpacity
            style={[styles.modeBtn, mode === 'manual' && styles.modeBtnActive]}
            onPress={() => { setMode('manual'); setScanned(null); }}
          >
            <Ionicons name="create-outline" size={16} color={mode === 'manual' ? '#4fc3f7' : '#444'} />
            <Text style={[styles.modeBtnText, mode === 'manual' && styles.modeBtnTextActive]}>Manual</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.modeBtn, mode === 'scan' && styles.modeBtnActive]}
            onPress={() => setMode('scan')}
          >
            <Ionicons name="camera-outline" size={16} color={mode === 'scan' ? '#4fc3f7' : '#444'} />
            <Text style={[styles.modeBtnText, mode === 'scan' && styles.modeBtnTextActive]}>Scan Receipt</Text>
          </TouchableOpacity>
        </View>

        {/* ── SCAN MODE ────────────────────────────────────────────────────── */}
        {mode === 'scan' && !scanned && (
          <View style={styles.scanCard}>
            <Ionicons name="receipt-outline" size={56} color="#333" style={{ marginBottom: 16 }} />
            <Text style={styles.scanHint}>Point camera at your receipt</Text>
            <Text style={styles.scanSub}>We'll auto-detect amount, vendor & category</Text>

            <TouchableOpacity
              style={[styles.scanBtn, scanning && styles.btnDisabled]}
              onPress={handleScan}
              disabled={scanning}
            >
              {scanning ? (
                <ActivityIndicator color="#fff" size="small" />
              ) : (
                <Ionicons name="camera" size={20} color="#fff" />
              )}
              <Text style={styles.scanBtnText}>{scanning ? 'Scanning…' : '📷 Scan Receipt'}</Text>
            </TouchableOpacity>
          </View>
        )}

        {/* Scan result preview */}
        {mode === 'scan' && scanned && (
          <View style={styles.scanResultCard}>
            <Text style={styles.scanResultTitle}>Receipt Detected</Text>
            <View style={styles.scanResultRow}>
              <Text style={styles.scanResultLabel}>Category</Text>
              <View style={styles.scanResultBadge}>
                <Ionicons
                  name={CATEGORIES.find(c => c.key === scanned.category)?.icon || 'help'}
                  size={14}
                  color={CATEGORIES.find(c => c.key === scanned.category)?.color || '#888'}
                />
                <Text style={[styles.scanResultBadgeText, { color: CATEGORIES.find(c => c.key === scanned.category)?.color || '#888' }]}>
                  {CATEGORIES.find(c => c.key === scanned.category)?.label || scanned.category}
                </Text>
              </View>
            </View>
            <View style={styles.scanResultRow}>
              <Text style={styles.scanResultLabel}>Amount</Text>
              <Text style={styles.scanResultValue}>${scanned.amount}</Text>
            </View>
            <View style={styles.scanResultRow}>
              <Text style={styles.scanResultLabel}>Vendor</Text>
              <Text style={styles.scanResultValue}>{scanned.vendor}</Text>
            </View>
            <Text style={styles.scanResultHint}>Review and correct the fields below, then confirm.</Text>
            <TouchableOpacity style={styles.scanConfirmBtn} onPress={handleConfirmScan}>
              <Ionicons name="checkmark-circle-outline" size={18} color="#fff" />
              <Text style={styles.scanConfirmText}>Confirm & Edit</Text>
            </TouchableOpacity>
          </View>
        )}

        {/* ── MANUAL FORM (shown in manual mode or after scan confirm) ─────── */}
        {(mode === 'manual' || scanned !== null) && (
          <>
            {/* Category Grid */}
            <Text style={styles.fieldLabel}>Category</Text>
            <View style={styles.catGrid}>
              {CATEGORIES.map((cat) => (
                <TouchableOpacity
                  key={cat.key}
                  style={[styles.catItem, category === cat.key && { borderColor: cat.color, borderWidth: 2 }]}
                  onPress={() => setCategory(cat.key)}
                >
                  <Ionicons name={cat.icon} size={22} color={category === cat.key ? cat.color : '#555'} />
                  <Text style={[styles.catLabel, category === cat.key && { color: cat.color }]}>
                    {cat.label}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>

            {/* Amount */}
            <Text style={styles.fieldLabel}>Amount ($)</Text>
            <TextInput
              style={styles.input}
              value={amount}
              onChangeText={setAmount}
              placeholder="0.00"
              placeholderTextColor="#333"
              keyboardType="decimal-pad"
              selectionColor="#4fc3f7"
            />

            {/* Vendor */}
            <Text style={styles.fieldLabel}>Vendor</Text>
            <TextInput
              style={styles.input}
              value={vendor}
              onChangeText={setVendor}
              placeholder="e.g. Love's #450"
              placeholderTextColor="#333"
              selectionColor="#4fc3f7"
            />

            {/* Date */}
            <Text style={styles.fieldLabel}>Date</Text>
            <TextInput
              style={styles.input}
              value={date}
              onChangeText={setDate}
              placeholder="YYYY-MM-DD"
              placeholderTextColor="#333"
              selectionColor="#4fc3f7"
            />

            {/* Notes */}
            <Text style={styles.fieldLabel}>Notes (optional)</Text>
            <TextInput
              style={[styles.input, styles.inputMulti]}
              value={notes}
              onChangeText={setNotes}
              placeholder="Any details…"
              placeholderTextColor="#333"
              multiline
              numberOfLines={3}
              selectionColor="#4fc3f7"
            />

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
              <Text style={styles.saveBtnText}>{saving ? 'Saving…' : 'Add Expense'}</Text>
            </TouchableOpacity>
          </>
        )}

      </ScrollView>
    </KeyboardAvoidingView>
  );
}

// ── Styles ────────────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  wrapper:    { flex: 1, backgroundColor: '#0d0d1a' },
  container:  { flex: 1 },
  scroll:     { padding: 16, paddingBottom: 60 },

  // Header
  headerRow: { flexDirection: 'row', alignItems: 'center', marginBottom: 20, gap: 8 },
  backBtn:   { padding: 4 },
  title:     { color: '#fff', fontSize: 22, fontWeight: '800' },

  // Mode toggle
  modeRow: {
    flexDirection: 'row',
    backgroundColor: '#161629',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#1e1e3a',
    padding: 4,
    marginBottom: 20,
    gap: 4,
  },
  modeBtn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    paddingVertical: 10,
    borderRadius: 9,
  },
  modeBtnActive:     { backgroundColor: '#0a1f2e' },
  modeBtnText:       { color: '#444', fontSize: 13, fontWeight: '700' },
  modeBtnTextActive: { color: '#4fc3f7' },

  // Scan card
  scanCard: {
    backgroundColor: '#161629',
    borderRadius: 14,
    padding: 40,
    alignItems: 'center',
    marginBottom: 20,
    borderWidth: 1,
    borderColor: '#1e1e3a',
    borderStyle: 'dashed',
  },
  scanHint: { color: '#ccc', fontSize: 16, fontWeight: '700', marginBottom: 6 },
  scanSub:  { color: '#555', fontSize: 13, textAlign: 'center', marginBottom: 24 },
  scanBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    backgroundColor: '#1565c0',
    paddingVertical: 14,
    paddingHorizontal: 28,
    borderRadius: 12,
  },
  scanBtnText: { color: '#fff', fontSize: 15, fontWeight: '700' },

  // Scan result
  scanResultCard: {
    backgroundColor: '#0a1a0f',
    borderRadius: 14,
    padding: 18,
    marginBottom: 20,
    borderWidth: 1,
    borderColor: '#2e7d32',
  },
  scanResultTitle: { color: '#66bb6a', fontSize: 13, fontWeight: '700', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 12 },
  scanResultRow:   { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingVertical: 6 },
  scanResultLabel: { color: '#888', fontSize: 13 },
  scanResultValue: { color: '#fff', fontSize: 15, fontWeight: '700' },
  scanResultBadge: { flexDirection: 'row', alignItems: 'center', gap: 5 },
  scanResultBadgeText: { fontSize: 14, fontWeight: '700' },
  scanResultHint:  { color: '#555', fontSize: 12, marginTop: 10, marginBottom: 14, textAlign: 'center' },
  scanConfirmBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    backgroundColor: '#2e7d32',
    paddingVertical: 12,
    borderRadius: 10,
  },
  scanConfirmText: { color: '#fff', fontSize: 14, fontWeight: '700' },

  // Form
  fieldLabel: { color: '#888', fontSize: 11, fontWeight: '700', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 8 },

  catGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    marginBottom: 20,
  },
  catItem: {
    width: '30%',
    alignItems: 'center',
    paddingVertical: 12,
    borderRadius: 12,
    backgroundColor: '#161629',
    borderWidth: 1,
    borderColor: '#1e1e3a',
    gap: 6,
  },
  catLabel: { color: '#555', fontSize: 11, fontWeight: '600' },

  input: {
    backgroundColor: '#161629',
    borderWidth: 1,
    borderColor: '#1e1e3a',
    borderRadius: 10,
    paddingHorizontal: 14,
    paddingVertical: 12,
    color: '#fff',
    fontSize: 16,
    marginBottom: 16,
  },
  inputMulti: { minHeight: 72, textAlignVertical: 'top' },

  // Buttons
  saveBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    backgroundColor: '#1565c0',
    paddingVertical: 16,
    borderRadius: 12,
    marginTop: 4,
  },
  saveBtnText: { color: '#fff', fontSize: 16, fontWeight: '700' },
  btnDisabled: { opacity: 0.5 },
});
