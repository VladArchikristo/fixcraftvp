import React, { useState, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  FlatList,
  Alert,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useFocusEffect } from '@react-navigation/native';

// ── Mock data (replace with API calls later) ─────────────────────────────────

const MOCK_LOADS = [
  { id: 'l1', grossRevenue: 3200, fuelSurcharge: 400, detention: 150, miles: 1200, date: '2026-04-10' },
  { id: 'l2', grossRevenue: 5200, fuelSurcharge: 600, detention: 0,   miles: 2000, date: '2026-04-07' },
];

const MOCK_EXPENSES = [
  { id: 'e1', category: 'fuel',        amount: 142.50, vendor: "Love's #450",   date: '2026-04-13', notes: '' },
  { id: 'e2', category: 'maintenance', amount: 350.00, vendor: 'Peterbilt Shop', date: '2026-04-11', notes: 'Oil change' },
  { id: 'e3', category: 'fuel',        amount: 210.00, vendor: "Pilot #882",     date: '2026-04-10', notes: '' },
  { id: 'e4', category: 'permits',     amount: 85.00,  vendor: 'PrePass',        date: '2026-04-09', notes: '' },
  { id: 'e5', category: 'food',        amount: 38.75,  vendor: 'Subway',         date: '2026-04-08', notes: '' },
  { id: 'e6', category: 'fuel',        amount: 198.00, vendor: "TA #312",        date: '2026-04-07', notes: '' },
  { id: 'e7', category: 'tolls',       amount: 24.50,  vendor: 'I-95 E-ZPass',   date: '2026-04-07', notes: '' },
  { id: 'e8', category: 'insurance',   amount: 950.00, vendor: 'Progressive',    date: '2026-04-01', notes: 'Monthly' },
  { id: 'e9', category: 'other',       amount: 45.00,  vendor: 'Dollar General', date: '2026-04-06', notes: '' },
];

const CATEGORY_META = {
  fuel:        { icon: 'flame',            color: '#ff7043', label: 'Fuel' },
  maintenance: { icon: 'build',            color: '#ffa726', label: 'Maintenance' },
  tolls:       { icon: 'car',              color: '#ab47bc', label: 'Tolls' },
  permits:     { icon: 'document-text',    color: '#42a5f5', label: 'Permits' },
  food:        { icon: 'fast-food',        color: '#66bb6a', label: 'Food' },
  insurance:   { icon: 'shield-checkmark', color: '#26c6da', label: 'Insurance' },
  other:       { icon: 'ellipsis-horizontal-circle', color: '#78909c', label: 'Other' },
};

const PERIODS = ['Week', 'Month', 'Quarter', 'Year'];

// ── Helpers ───────────────────────────────────────────────────────────────────

function buildPnL(loads, expenses) {
  const grossRevenue = loads.reduce((s, l) => s + l.grossRevenue + l.fuelSurcharge + l.detention, 0);
  const totalMiles   = loads.reduce((s, l) => s + l.miles, 0);

  const byCategory = {};
  let totalExpenses = 0;
  expenses.forEach((e) => {
    byCategory[e.category] = (byCategory[e.category] || 0) + e.amount;
    totalExpenses += e.amount;
  });

  const netProfit    = grossRevenue - totalExpenses;
  const revenuePerMi = totalMiles > 0 ? (grossRevenue / totalMiles) : 0;
  const costPerMi    = totalMiles > 0 ? (totalExpenses / totalMiles) : 0;
  const profitPerMi  = totalMiles > 0 ? (netProfit / totalMiles) : 0;

  return { grossRevenue, totalExpenses, netProfit, byCategory, totalMiles, revenuePerMi, costPerMi, profitPerMi };
}

function fmt(n) {
  return n >= 0 ? `$${n.toFixed(2)}` : `-$${Math.abs(n).toFixed(2)}`;
}

// ── Component ─────────────────────────────────────────────────────────────────

export default function ExpenseDashboardScreen({ navigation }) {
  const [period, setPeriod]       = useState('Month');
  const [expenses, setExpenses]   = useState(MOCK_EXPENSES);
  const [loads, setLoads]         = useState(MOCK_LOADS);

  useFocusEffect(
    useCallback(() => {
      // TODO: load from AsyncStorage / API
      setExpenses(MOCK_EXPENSES);
      setLoads(MOCK_LOADS);
    }, [period])
  );

  const pnl = buildPnL(loads, expenses);
  const recentExpenses = expenses.slice(0, 8);

  const renderExpenseItem = ({ item }) => {
    const meta = CATEGORY_META[item.category] || CATEGORY_META.other;
    return (
      <View style={styles.expenseRow}>
        <View style={[styles.expenseIconWrap, { backgroundColor: meta.color + '22' }]}>
          <Ionicons name={meta.icon} size={18} color={meta.color} />
        </View>
        <View style={styles.expenseInfo}>
          <Text style={styles.expenseVendor}>{item.vendor}</Text>
          <Text style={styles.expenseCat}>{meta.label} · {item.date}</Text>
        </View>
        <Text style={styles.expenseAmount}>-${item.amount.toFixed(2)}</Text>
      </View>
    );
  };

  return (
    <View style={styles.wrapper}>
      <ScrollView style={styles.container} contentContainerStyle={styles.scroll}>

        {/* Header */}
        <Text style={styles.title}>Expense Tracker</Text>

        {/* Period Selector */}
        <View style={styles.periodRow}>
          {PERIODS.map((p) => (
            <TouchableOpacity
              key={p}
              style={[styles.periodBtn, period === p && styles.periodBtnActive]}
              onPress={() => setPeriod(p)}
            >
              <Text style={[styles.periodBtnText, period === p && styles.periodBtnTextActive]}>
                {p}
              </Text>
            </TouchableOpacity>
          ))}
        </View>

        {/* P&L Card */}
        <View style={styles.pnlCard}>
          <Text style={styles.pnlTitle}>Profit & Loss · {period}</Text>

          <View style={styles.pnlRow}>
            <Text style={styles.pnlLabel}>💰 Gross Revenue</Text>
            <Text style={[styles.pnlValue, styles.colorGreen]}>{fmt(pnl.grossRevenue)}</Text>
          </View>

          {Object.entries(pnl.byCategory).map(([cat, amt]) => {
            const meta = CATEGORY_META[cat] || CATEGORY_META.other;
            return (
              <View key={cat} style={styles.pnlRow}>
                <Text style={styles.pnlLabel}>  {meta.label}</Text>
                <Text style={[styles.pnlValue, styles.colorRed]}>-${amt.toFixed(2)}</Text>
              </View>
            );
          })}

          <View style={styles.pnlDivider} />

          <View style={styles.pnlRow}>
            <Text style={styles.pnlNetLabel}>
              {pnl.netProfit >= 0 ? '✅ Net Profit' : '❌ Net Loss'}
            </Text>
            <Text style={[styles.pnlNetValue, pnl.netProfit >= 0 ? styles.colorGreen : styles.colorRed]}>
              {fmt(pnl.netProfit)}
            </Text>
          </View>

          {/* Per-mile row */}
          <View style={styles.perMileRow}>
            <View style={styles.perMileItem}>
              <Ionicons name="navigate" size={13} color="#4fc3f7" />
              <Text style={styles.perMileText}>{pnl.totalMiles.toLocaleString()} mi</Text>
            </View>
            <View style={styles.perMileDivider} />
            <View style={styles.perMileItem}>
              <Text style={styles.perMileLabel}>Rev</Text>
              <Text style={[styles.perMileText, styles.colorGreen]}>${pnl.revenuePerMi.toFixed(2)}/mi</Text>
            </View>
            <View style={styles.perMileDivider} />
            <View style={styles.perMileItem}>
              <Text style={styles.perMileLabel}>Cost</Text>
              <Text style={[styles.perMileText, styles.colorRed]}>${pnl.costPerMi.toFixed(2)}/mi</Text>
            </View>
            <View style={styles.perMileDivider} />
            <View style={styles.perMileItem}>
              <Text style={styles.perMileLabel}>Net</Text>
              <Text style={[styles.perMileText, pnl.profitPerMi >= 0 ? styles.colorGreen : styles.colorRed]}>
                ${pnl.profitPerMi.toFixed(2)}/mi
              </Text>
            </View>
          </View>
        </View>

        {/* Quick Actions */}
        <View style={styles.quickRow}>
          <TouchableOpacity
            style={[styles.quickBtn, styles.quickBtnPrimary]}
            onPress={() => navigation.navigate('AddLoad')}
          >
            <Ionicons name="add-circle-outline" size={18} color="#fff" />
            <Text style={styles.quickBtnTextPrimary}>Add Load</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.quickBtn, styles.quickBtnSecondary]}
            onPress={() => navigation.navigate('AddExpense')}
          >
            <Ionicons name="receipt-outline" size={18} color="#4fc3f7" />
            <Text style={styles.quickBtnTextSecondary}>Add Expense</Text>
          </TouchableOpacity>
        </View>

        {/* Recent Expenses */}
        <View style={styles.sectionHeader}>
          <Text style={styles.sectionTitle}>Recent Expenses</Text>
          <Text style={styles.sectionCount}>{expenses.length} total</Text>
        </View>

        <View style={styles.listCard}>
          {recentExpenses.length === 0 ? (
            <View style={styles.emptyInner}>
              <Ionicons name="receipt-outline" size={36} color="#333" />
              <Text style={styles.emptyText}>No expenses yet</Text>
            </View>
          ) : (
            recentExpenses.map((item, idx) => (
              <View key={item.id}>
                {renderExpenseItem({ item })}
                {idx < recentExpenses.length - 1 && <View style={styles.rowDivider} />}
              </View>
            ))
          )}
        </View>

      </ScrollView>

      {/* FAB */}
      <TouchableOpacity
        style={styles.fab}
        onPress={() => navigation.navigate('AddExpense')}
        activeOpacity={0.85}
      >
        <Ionicons name="add" size={28} color="#fff" />
      </TouchableOpacity>
    </View>
  );
}

// ── Styles ────────────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  wrapper:    { flex: 1, backgroundColor: '#0d0d1a' },
  container:  { flex: 1 },
  scroll:     { padding: 16, paddingBottom: 100 },

  title: { color: '#fff', fontSize: 22, fontWeight: '800', marginBottom: 16 },

  // Period
  periodRow: { flexDirection: 'row', gap: 8, marginBottom: 16 },
  periodBtn: {
    flex: 1,
    paddingVertical: 10,
    borderRadius: 10,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: '#1e1e3a',
    backgroundColor: '#161629',
  },
  periodBtnActive: { backgroundColor: '#0a1f2e', borderColor: '#4fc3f7' },
  periodBtnText: { color: '#555', fontSize: 13, fontWeight: '700' },
  periodBtnTextActive: { color: '#4fc3f7' },

  // P&L Card
  pnlCard: {
    backgroundColor: '#161629',
    borderRadius: 14,
    padding: 18,
    marginBottom: 14,
    borderWidth: 1,
    borderColor: '#1e1e3a',
  },
  pnlTitle: {
    color: '#888',
    fontSize: 11,
    fontWeight: '700',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginBottom: 14,
  },
  pnlRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 5,
  },
  pnlLabel:    { color: '#aaa', fontSize: 14 },
  pnlValue:    { fontSize: 14, fontWeight: '700' },
  pnlDivider:  { height: 1, backgroundColor: '#2a2a4a', marginVertical: 10 },
  pnlNetLabel: { color: '#fff', fontSize: 16, fontWeight: '800' },
  pnlNetValue: { fontSize: 22, fontWeight: '900' },

  colorGreen: { color: '#66bb6a' },
  colorRed:   { color: '#ef9a9a' },

  // Per-mile
  perMileRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 14,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: '#1e1e3a',
  },
  perMileItem:    { flex: 1, alignItems: 'center' },
  perMileDivider: { width: 1, height: 28, backgroundColor: '#1e1e3a' },
  perMileLabel:   { color: '#555', fontSize: 9, fontWeight: '700', textTransform: 'uppercase', marginBottom: 2 },
  perMileText:    { color: '#ccc', fontSize: 12, fontWeight: '700' },

  // Quick actions
  quickRow: { flexDirection: 'row', gap: 10, marginBottom: 20 },
  quickBtn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 7,
    paddingVertical: 13,
    borderRadius: 12,
  },
  quickBtnPrimary:       { backgroundColor: '#1565c0' },
  quickBtnSecondary:     { backgroundColor: '#0a1520', borderWidth: 1, borderColor: '#4fc3f7' },
  quickBtnTextPrimary:   { color: '#fff',    fontSize: 14, fontWeight: '700' },
  quickBtnTextSecondary: { color: '#4fc3f7', fontSize: 14, fontWeight: '700' },

  // Section header
  sectionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 10,
  },
  sectionTitle: { color: '#888', fontSize: 11, fontWeight: '700', textTransform: 'uppercase', letterSpacing: 0.5 },
  sectionCount: { color: '#444', fontSize: 11 },

  // List card
  listCard: {
    backgroundColor: '#161629',
    borderRadius: 14,
    borderWidth: 1,
    borderColor: '#1e1e3a',
    overflow: 'hidden',
    marginBottom: 16,
  },
  expenseRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 12,
    paddingHorizontal: 14,
    gap: 12,
  },
  expenseIconWrap: {
    width: 36,
    height: 36,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
  },
  expenseInfo:   { flex: 1 },
  expenseVendor: { color: '#fff', fontSize: 14, fontWeight: '600' },
  expenseCat:    { color: '#555', fontSize: 12, marginTop: 2 },
  expenseAmount: { color: '#ef9a9a', fontSize: 14, fontWeight: '700' },
  rowDivider:    { height: 1, backgroundColor: '#1a1a2a', marginLeft: 62 },

  emptyInner: { alignItems: 'center', paddingVertical: 32 },
  emptyText:  { color: '#555', fontSize: 14, fontWeight: '600', marginTop: 10 },

  // FAB
  fab: {
    position: 'absolute',
    bottom: 24,
    right: 20,
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: '#1565c0',
    alignItems: 'center',
    justifyContent: 'center',
    elevation: 8,
    shadowColor: '#4fc3f7',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.35,
    shadowRadius: 8,
  },
});
