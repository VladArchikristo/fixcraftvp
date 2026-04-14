import React, { useState, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  FlatList,
  Alert,
  ActivityIndicator,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useFocusEffect } from '@react-navigation/native';
import { getProfitAndLoss, getExpensesByPeriod } from '../services/expenseService';

// ── Period label → service period key ────────────────────────────────────────
const PERIOD_KEY = {
  Week:    'week',
  Month:   'month',
  Quarter: 'quarter',
  Year:    'year',
};

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

function fmt(n) {
  return n >= 0 ? `$${n.toFixed(2)}` : `-$${Math.abs(n).toFixed(2)}`;
}

// Empty PnL shape for initial / loading state
const EMPTY_PNL = {
  grossRevenue: 0,
  totalExpenses: 0,
  netProfit: 0,
  expenses: {},
  milesDriven: 0,
  revenuePerMile: 0,
  costPerMile: 0,
  profitPerMile: 0,
};

// ── Component ─────────────────────────────────────────────────────────────────

// Helper to get date range from period key (mirrors expenseService logic)
function getPeriodDates(period) {
  const now = new Date();
  const today = now.toISOString().slice(0, 10);
  let startDate;
  switch (period) {
    case 'week': {
      const d = new Date(now); d.setDate(d.getDate() - 6);
      startDate = d.toISOString().slice(0, 10); break;
    }
    case 'month':
      startDate = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-01`; break;
    case 'quarter': {
      const q = Math.floor(now.getMonth() / 3);
      startDate = `${now.getFullYear()}-${String(q * 3 + 1).padStart(2, '0')}-01`; break;
    }
    case 'year':
      startDate = `${now.getFullYear()}-01-01`; break;
    default:
      startDate = today;
  }
  return { startDate, endDate: today };
}

export default function ExpenseDashboardScreen({ navigation }) {
  const [period, setPeriod]       = useState('Month');
  const [expenses, setExpenses]   = useState([]);
  const [pnl, setPnl]             = useState(EMPTY_PNL);
  const [loading, setLoading]     = useState(true);

  useFocusEffect(
    useCallback(() => {
      let cancelled = false;
      const load = async () => {
        setLoading(true);
        try {
          const key = PERIOD_KEY[period] || 'month';
          const pnlData = await getProfitAndLoss(key);
          const expRows = await getExpensesByPeriod(pnlData.startDate, pnlData.endDate);
          if (!cancelled) {
            setPnl(pnlData);
            setExpenses(expRows);
          }
        } catch (err) {
          if (!cancelled) {
            Alert.alert('Error', err.message || 'Could not load data.');
          }
        } finally {
          if (!cancelled) setLoading(false);
        }
      };
      load();
      return () => { cancelled = true; };
    }, [period])
  );

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
          <Text style={styles.expenseCat}>{meta.label || item.category} · {item.trip_date || item.date}</Text>
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

          {loading ? (
            <ActivityIndicator color="#4fc3f7" style={{ marginVertical: 20 }} />
          ) : (
            <>
              <View style={styles.pnlRow}>
                <Text style={styles.pnlLabel}>💰 Gross Revenue</Text>
                <Text style={[styles.pnlValue, styles.colorGreen]}>{fmt(pnl.grossRevenue)}</Text>
              </View>

              {Object.entries(pnl.expenses || {}).map(([cat, amt]) => {
                const meta = CATEGORY_META[cat] || CATEGORY_META.other;
                return (
                  <View key={cat} style={styles.pnlRow}>
                    <Text style={styles.pnlLabel}>  {meta.label || cat}</Text>
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
                  <Text style={styles.perMileText}>{(pnl.milesDriven || 0).toLocaleString()} mi</Text>
                </View>
                <View style={styles.perMileDivider} />
                <View style={styles.perMileItem}>
                  <Text style={styles.perMileLabel}>Rev</Text>
                  <Text style={[styles.perMileText, styles.colorGreen]}>${(pnl.revenuePerMile || 0).toFixed(2)}/mi</Text>
                </View>
                <View style={styles.perMileDivider} />
                <View style={styles.perMileItem}>
                  <Text style={styles.perMileLabel}>Cost</Text>
                  <Text style={[styles.perMileText, styles.colorRed]}>${(pnl.costPerMile || 0).toFixed(2)}/mi</Text>
                </View>
                <View style={styles.perMileDivider} />
                <View style={styles.perMileItem}>
                  <Text style={styles.perMileLabel}>Net</Text>
                  <Text style={[styles.perMileText, (pnl.profitPerMile || 0) >= 0 ? styles.colorGreen : styles.colorRed]}>
                    ${(pnl.profitPerMile || 0).toFixed(2)}/mi
                  </Text>
                </View>
              </View>
            </>
          )}
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
