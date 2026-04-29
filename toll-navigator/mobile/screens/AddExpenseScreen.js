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
import * as ImagePicker from 'expo-image-picker';
import { addExpense } from '../services/expenseService';
import receiptParserService from '../services/receiptParserService';
import { COLORS, SPACING, RADIUS } from '../theme';

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

// Map receiptParserService suggestedCategory → screen category keys
const CATEGORY_MAP = {
  diesel:      'fuel',
  maintenance: 'maintenance',
  food:        'food',
  hotel:       'other',
  permits:     'permits',
  other:       'other',
};

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

  // ── Real receipt scan via camera + OCR ───────────────────────────────────

  const handleScan = async () => {
    try {
      const permission = await ImagePicker.requestCameraPermissionsAsync();
      if (!permission.granted) {
        Alert.alert('Permission needed', 'Camera access is required to scan receipts.');
        return;
      }

      const pickerResult = await ImagePicker.launchCameraAsync({
        mediaTypes: ImagePicker.MediaTypeOptions.Images,
        quality: 0.85,
        allowsEditing: false,
      });

      if (pickerResult.canceled || !pickerResult.assets?.[0]?.uri) return;

      setScanning(true);
      const imageUri = pickerResult.assets[0].uri;

      const parsed = await receiptParserService.scanAndParse(imageUri);

      const mappedCategory = CATEGORY_MAP[parsed.suggestedCategory] || 'other';
      const result = {
        category: mappedCategory,
        amount:   parsed.amount != null ? String(parsed.amount) : '',
        vendor:   parsed.vendor || '',
        date:     parsed.date || todayStr(),
        imageUri,
      };

      setScanned(result);
      setCategory(result.category);
      setAmount(result.amount);
      setVendor(result.vendor);
      if (result.date) setDate(result.date);
    } catch (err) {
      Alert.alert('Scan failed', err.message || 'Could not scan receipt.');
    } finally {
      setScanning(false);
    }
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
      await addExpense({
        category,
        amount:            parseFloat(amount),
        vendor:            vendor.trim(),
        notes:             notes.trim() || null,
        trip_date:         date,
        receipt_image_uri: scanned?.imageUri || null,
      });
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
            <Ionicons name="chevron-back" size={22} color={COLORS.primary} />
          </TouchableOpacity>
          <Text style={styles.title}>Add Expense</Text>
        </View>

        {/* Mode Toggle */}
        <View style={styles.modeRow}>
          <TouchableOpacity
            style={[styles.modeBtn, mode === 'manual' && styles.modeBtnActive]}
            onPress={() => { setMode('manual'); setScanned(null); }}
          >
            <Ionicons name="create-outline" size={16} color={mode === 'manual' ? COLORS.primary : COLORS.textMuted} />
            <Text style={[styles.modeBtnText, mode === 'manual' && styles.modeBtnTextActive]}>Manual</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.modeBtn, mode === 'scan' && styles.modeBtnActive]}
            onPress={() => setMode('scan')}
          >
            <Ionicons name="camera-outline" size={16} color={mode === 'scan' ? COLORS.primary : COLORS.textMuted} />
            <Text style={[styles.modeBtnText, mode === 'scan' && styles.modeBtnTextActive]}>Scan Receipt</Text>
          </TouchableOpacity>
        </View>

        {/* ── SCAN MODE ────────────────────────────────────────────────────── */}
        {mode === 'scan' && !scanned && (
          <View style={styles.scanCard}>
            <Ionicons name="receipt-outline" size={56} color={COLORS.border} style={{ marginBottom: SPACING.md }} />
            <Text style={styles.scanHint}>Point camera at your receipt</Text>
            <Text style={styles.scanSub}>We'll auto-detect amount, vendor & category</Text>

            <TouchableOpacity
              style={[styles.scanBtn, scanning && styles.btnDisabled]}
              onPress={handleScan}
              disabled={scanning}
            >
              {scanning ? (
                <ActivityIndicator color={COLORS.textInverse} size="small" />
              ) : (
                <Ionicons name="camera" size={20} color={COLORS.textInverse} />
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
                  color={CATEGORIES.find(c => c.key === scanned.category)?.color || COLORS.textSecondary}
                />
                <Text style={[styles.scanResultBadgeText, { color: CATEGORIES.find(c => c.key === scanned.category)?.color || COLORS.textSecondary }]}>
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
              <Ionicons name="checkmark-circle-outline" size={18} color={COLORS.textInverse} />
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
                  <Ionicons name={cat.icon} size={22} color={category === cat.key ? cat.color : COLORS.textMuted} />
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
              placeholderTextColor={COLORS.textMuted}
              keyboardType="decimal-pad"
              selectionColor={COLORS.primary}
            />

            {/* Vendor */}
            <Text style={styles.fieldLabel}>Vendor</Text>
            <TextInput
              style={styles.input}
              value={vendor}
              onChangeText={setVendor}
              placeholder="e.g. Love's #450"
              placeholderTextColor={COLORS.textMuted}
              selectionColor={COLORS.primary}
            />

            {/* Date */}
            <Text style={styles.fieldLabel}>Date</Text>
            <TextInput
              style={styles.input}
              value={date}
              onChangeText={setDate}
              placeholder="YYYY-MM-DD"
              placeholderTextColor={COLORS.textMuted}
              selectionColor={COLORS.primary}
            />

            {/* Notes */}
            <Text style={styles.fieldLabel}>Notes (optional)</Text>
            <TextInput
              style={[styles.input, styles.inputMulti]}
              value={notes}
              onChangeText={setNotes}
              placeholder="Any details…"
              placeholderTextColor={COLORS.textMuted}
              multiline
              numberOfLines={3}
              selectionColor={COLORS.primary}
            />

            {/* Save Button */}
            <TouchableOpacity
              style={[styles.saveBtn, saving && styles.btnDisabled]}
              onPress={handleSave}
              disabled={saving}
            >
              {saving ? (
                <ActivityIndicator color={COLORS.textInverse} size="small" />
              ) : (
                <Ionicons name="checkmark-circle" size={20} color={COLORS.textInverse} />
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
  wrapper:    { flex: 1, backgroundColor: COLORS.bg },
  container:  { flex: 1 },
  scroll:     { padding: SPACING.md, paddingBottom: 60 },

  // Header
  headerRow: { flexDirection: 'row', alignItems: 'center', marginBottom: 20, gap: SPACING.sm },
  backBtn:   { padding: 4 },
  title:     { color: COLORS.textPrimary, fontSize: 22, fontWeight: '800' },

  // Mode toggle
  modeRow: {
    flexDirection: 'row',
    backgroundColor: COLORS.bgCard,
    borderRadius: RADIUS.md,
    borderWidth: 1,
    borderColor: COLORS.bgCardAlt,
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
  modeBtnActive:     { backgroundColor: COLORS.primaryLight },
  modeBtnText:       { color: COLORS.textMuted, fontSize: 13, fontWeight: '700' },
  modeBtnTextActive: { color: COLORS.primary },

  // Scan card
  scanCard: {
    backgroundColor: COLORS.bgCard,
    borderRadius: 14,
    padding: 40,
    alignItems: 'center',
    marginBottom: 20,
    borderWidth: 1,
    borderColor: COLORS.bgCardAlt,
    borderStyle: 'dashed',
  },
  scanHint: { color: COLORS.textSecondary, fontSize: 16, fontWeight: '700', marginBottom: 6 },
  scanSub:  { color: COLORS.textMuted, fontSize: 13, textAlign: 'center', marginBottom: SPACING.lg },
  scanBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: SPACING.sm,
    backgroundColor: COLORS.accent,
    paddingVertical: 14,
    paddingHorizontal: 28,
    borderRadius: RADIUS.md,
  },
  scanBtnText: { color: COLORS.textInverse, fontSize: 15, fontWeight: '700' },

  // Scan result
  scanResultCard: {
    backgroundColor: COLORS.successLight,
    borderRadius: 14,
    padding: 18,
    marginBottom: 20,
    borderWidth: 1,
    borderColor: COLORS.success,
  },
  scanResultTitle: { color: COLORS.success, fontSize: 13, fontWeight: '700', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 12 },
  scanResultRow:   { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingVertical: 6 },
  scanResultLabel: { color: COLORS.textSecondary, fontSize: 13 },
  scanResultValue: { color: COLORS.textPrimary, fontSize: 15, fontWeight: '700' },
  scanResultBadge: { flexDirection: 'row', alignItems: 'center', gap: 5 },
  scanResultBadgeText: { fontSize: 14, fontWeight: '700' },
  scanResultHint:  { color: COLORS.textMuted, fontSize: 12, marginTop: 10, marginBottom: 14, textAlign: 'center' },
  scanConfirmBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: SPACING.sm,
    backgroundColor: COLORS.success,
    paddingVertical: 12,
    borderRadius: 10,
  },
  scanConfirmText: { color: COLORS.textInverse, fontSize: 14, fontWeight: '700' },

  // Form
  fieldLabel: { color: COLORS.textSecondary, fontSize: 11, fontWeight: '700', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: SPACING.sm },

  catGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: SPACING.sm,
    marginBottom: 20,
  },
  catItem: {
    width: '30%',
    alignItems: 'center',
    paddingVertical: 12,
    borderRadius: RADIUS.md,
    backgroundColor: COLORS.bgCard,
    borderWidth: 1,
    borderColor: COLORS.bgCardAlt,
    gap: 6,
  },
  catLabel: { color: COLORS.textMuted, fontSize: 11, fontWeight: '600' },

  input: {
    backgroundColor: COLORS.bgCard,
    borderWidth: 1,
    borderColor: COLORS.bgCardAlt,
    borderRadius: 10,
    paddingHorizontal: 14,
    paddingVertical: 12,
    color: COLORS.textPrimary,
    fontSize: 16,
    marginBottom: SPACING.md,
  },
  inputMulti: { minHeight: 72, textAlignVertical: 'top' },

  // Buttons
  saveBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: SPACING.sm,
    backgroundColor: COLORS.accent,
    paddingVertical: SPACING.md,
    borderRadius: RADIUS.md,
    marginTop: 4,
  },
  saveBtnText: { color: COLORS.textInverse, fontSize: 16, fontWeight: '700' },
  btnDisabled: { opacity: 0.5 },
});
