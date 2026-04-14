/**
 * Expense Tracker Service
 *
 * Manages expenses and loads (income) for truck drivers.
 * Provides P&L calculations, per-load profitability, and vendor category learning.
 *
 * SQLite tables:
 *   expenses         — individual expense records
 *   loads            — income / load records
 *   vendor_categories — learned vendor → category mappings
 */

import * as SQLite from 'expo-sqlite';

// ─────────────────────────────────────────────────────────────────────────────
// Constants
// ─────────────────────────────────────────────────────────────────────────────

export const EXPENSE_CATEGORIES = [
  'diesel',
  'maintenance',
  'permits',
  'insurance',
  'lumper',
  'hotel',
  'food',
  'factoring',
  'custom',
];

// ─────────────────────────────────────────────────────────────────────────────
// Database init
// ─────────────────────────────────────────────────────────────────────────────

let _db = null;

/**
 * Open (or reuse) the SQLite database and ensure all expense tracker tables exist.
 * Shares the same toll_navigator.db as iftaMileageTracker.
 * @returns {Promise<SQLite.SQLiteDatabase>}
 */
async function getDb() {
  if (_db) return _db;

  _db = await SQLite.openDatabaseAsync('toll_navigator.db');

  // Expenses table
  await _db.execAsync(`
    CREATE TABLE IF NOT EXISTS expenses (
      id                TEXT PRIMARY KEY,
      category          TEXT NOT NULL,
      amount            REAL NOT NULL,
      vendor            TEXT,
      notes             TEXT,
      receipt_image_uri TEXT,
      state             TEXT,
      load_id           TEXT,
      created_at        TEXT NOT NULL,
      trip_date         TEXT NOT NULL
    );

    CREATE INDEX IF NOT EXISTS idx_expenses_trip_date
      ON expenses (trip_date);

    CREATE INDEX IF NOT EXISTS idx_expenses_category
      ON expenses (category);
  `);

  // Loads (income) table
  await _db.execAsync(`
    CREATE TABLE IF NOT EXISTS loads (
      id                   TEXT PRIMARY KEY,
      gross_rate           REAL NOT NULL,
      fuel_surcharge       REAL DEFAULT 0,
      detention_pay        REAL DEFAULT 0,
      factoring_enabled    INTEGER DEFAULT 0,
      factoring_percent    REAL DEFAULT 0,
      net_pay              REAL NOT NULL,
      miles                REAL,
      origin               TEXT,
      destination          TEXT,
      broker_name          TEXT,
      load_tracking_token  TEXT,
      started_at           TEXT,
      delivered_at         TEXT,
      created_at           TEXT NOT NULL
    );

    CREATE INDEX IF NOT EXISTS idx_loads_delivered_at
      ON loads (delivered_at);
  `);

  // Vendor category learning table
  await _db.execAsync(`
    CREATE TABLE IF NOT EXISTS vendor_categories (
      vendor_name TEXT PRIMARY KEY,
      category    TEXT NOT NULL,
      learned_at  TEXT NOT NULL
    );
  `);

  return _db;
}

// ─────────────────────────────────────────────────────────────────────────────
// ID generator
// ─────────────────────────────────────────────────────────────────────────────

function generateId() {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

// ─────────────────────────────────────────────────────────────────────────────
// Period helpers
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Get ISO start/end dates for a named period.
 * @param {'week'|'month'|'quarter'|'year'} period
 * @returns {{ startDate: string, endDate: string }}
 */
function getPeriodDates(period) {
  const now = new Date();
  const today = now.toISOString().slice(0, 10);

  let startDate;
  switch (period) {
    case 'week': {
      const d = new Date(now);
      d.setDate(d.getDate() - 6);
      startDate = d.toISOString().slice(0, 10);
      break;
    }
    case 'month': {
      startDate = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-01`;
      break;
    }
    case 'quarter': {
      const q = Math.floor(now.getMonth() / 3);
      const qStartMonth = q * 3 + 1;
      startDate = `${now.getFullYear()}-${String(qStartMonth).padStart(2, '0')}-01`;
      break;
    }
    case 'year': {
      startDate = `${now.getFullYear()}-01-01`;
      break;
    }
    default: {
      // Custom period passed as "YYYY-MM-DD:YYYY-MM-DD"
      const parts = period.split(':');
      return { startDate: parts[0], endDate: parts[1] || today };
    }
  }

  return { startDate, endDate: today };
}

// ─────────────────────────────────────────────────────────────────────────────
// Public API
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Add a new expense record.
 *
 * @param {Omit<import('./expenseTypes').Expense, 'id'|'created_at'>} expense
 * @returns {Promise<import('./expenseTypes').Expense>}
 */
export async function addExpense(expense) {
  const db = await getDb();

  const id = generateId();
  const created_at = new Date().toISOString();

  const {
    category,
    amount,
    vendor = null,
    notes = null,
    receipt_image_uri = null,
    state = null,
    load_id = null,
    trip_date,
  } = expense;

  await db.runAsync(
    `INSERT INTO expenses
       (id, category, amount, vendor, notes, receipt_image_uri, state, load_id, created_at, trip_date)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
    [id, category, amount, vendor, notes, receipt_image_uri, state, load_id, created_at, trip_date]
  );

  // Auto-learn vendor category if vendor is provided
  if (vendor && category) {
    await learnVendorCategory(vendor, category);
  }

  return { id, category, amount, vendor, notes, receipt_image_uri, state, load_id, created_at, trip_date };
}

/**
 * Add a new load (income) record.
 *
 * @param {Omit<import('./expenseTypes').Load, 'id'|'created_at'>} load
 * @returns {Promise<import('./expenseTypes').Load>}
 */
export async function addLoad(load) {
  const db = await getDb();

  const id = generateId();
  const created_at = new Date().toISOString();

  const {
    gross_rate,
    fuel_surcharge = 0,
    detention_pay = 0,
    factoring_enabled = 0,
    factoring_percent = 0,
    net_pay,
    miles = null,
    origin = null,
    destination = null,
    broker_name = null,
    load_tracking_token = null,
    started_at = null,
    delivered_at = null,
  } = load;

  await db.runAsync(
    `INSERT INTO loads
       (id, gross_rate, fuel_surcharge, detention_pay, factoring_enabled, factoring_percent,
        net_pay, miles, origin, destination, broker_name, load_tracking_token,
        started_at, delivered_at, created_at)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
    [
      id, gross_rate, fuel_surcharge, detention_pay,
      factoring_enabled ? 1 : 0, factoring_percent,
      net_pay, miles, origin, destination, broker_name, load_tracking_token,
      started_at, delivered_at, created_at,
    ]
  );

  return {
    id, gross_rate, fuel_surcharge, detention_pay,
    factoring_enabled, factoring_percent, net_pay,
    miles, origin, destination, broker_name, load_tracking_token,
    started_at, delivered_at, created_at,
  };
}

/**
 * Get expense summary grouped by category for a period.
 *
 * @param {'week'|'month'|'quarter'|'year'} period
 * @returns {Promise<import('./expenseTypes').ExpenseSummary>}
 */
export async function getExpensesSummary(period) {
  const db = await getDb();
  const { startDate, endDate } = getPeriodDates(period);

  const rows = await db.getAllAsync(
    `SELECT category, SUM(amount) as total
     FROM expenses
     WHERE trip_date >= ? AND trip_date <= ?
     GROUP BY category
     ORDER BY total DESC`,
    [startDate, endDate]
  );

  const byCategory = {};
  let totalExpenses = 0;

  (rows || []).forEach(({ category, total }) => {
    byCategory[category] = total;
    totalExpenses += total;
  });

  return {
    byCategory,
    totalExpenses,
    period,
    startDate,
    endDate,
  };
}

/**
 * Get full Profit & Loss statement for a period.
 *
 * @param {string} period  — 'week'|'month'|'quarter'|'year' or 'YYYY-MM-DD:YYYY-MM-DD'
 * @returns {Promise<import('./expenseTypes').PnL>}
 */
export async function getProfitAndLoss(period) {
  const db = await getDb();
  const { startDate, endDate } = getPeriodDates(period);

  // Revenue: sum of net_pay from loads delivered in the period
  const revenueRow = await db.getFirstAsync(
    `SELECT
       COALESCE(SUM(net_pay), 0)    AS gross_revenue,
       COALESCE(SUM(miles), 0)      AS miles_driven
     FROM loads
     WHERE (delivered_at >= ? AND delivered_at <= ?)
        OR (delivered_at IS NULL AND created_at >= ? AND created_at <= ?)`,
    [startDate, endDate, startDate, endDate]
  );

  const grossRevenue = revenueRow?.gross_revenue ?? 0;
  const milesDriven = revenueRow?.miles_driven ?? 0;

  // Expenses by category
  const expenseRows = await db.getAllAsync(
    `SELECT category, SUM(amount) as total
     FROM expenses
     WHERE trip_date >= ? AND trip_date <= ?
     GROUP BY category`,
    [startDate, endDate]
  );

  const expenses = {};
  let totalExpenses = 0;

  (expenseRows || []).forEach(({ category, total }) => {
    expenses[category] = total;
    totalExpenses += total;
  });

  const netProfit = grossRevenue - totalExpenses;
  const revenuePerMile = milesDriven > 0 ? grossRevenue / milesDriven : 0;
  const costPerMile = milesDriven > 0 ? totalExpenses / milesDriven : 0;
  const profitPerMile = milesDriven > 0 ? netProfit / milesDriven : 0;

  return {
    grossRevenue,
    expenses,
    totalExpenses,
    netProfit,
    milesDriven,
    revenuePerMile: parseFloat(revenuePerMile.toFixed(4)),
    costPerMile: parseFloat(costPerMile.toFixed(4)),
    profitPerMile: parseFloat(profitPerMile.toFixed(4)),
    period,
    startDate,
    endDate,
  };
}

/**
 * Get profitability breakdown for a specific load.
 *
 * @param {string} loadId
 * @returns {Promise<import('./expenseTypes').LoadProfit>}
 */
export async function getLoadProfitability(loadId) {
  const db = await getDb();

  const load = await db.getFirstAsync(
    `SELECT * FROM loads WHERE id = ?`,
    [loadId]
  );

  if (!load) {
    throw new Error(`Load not found: ${loadId}`);
  }

  const expenseRows = await db.getAllAsync(
    `SELECT category, SUM(amount) as total
     FROM expenses
     WHERE load_id = ?
     GROUP BY category`,
    [loadId]
  );

  const expenses = {};
  let totalExpenses = 0;

  (expenseRows || []).forEach(({ category, total }) => {
    expenses[category] = total;
    totalExpenses += total;
  });

  const netProfit = load.net_pay - totalExpenses;
  const revenuePerMile = load.miles > 0 ? load.net_pay / load.miles : 0;
  const costPerMile = load.miles > 0 ? totalExpenses / load.miles : 0;
  const profitPerMile = load.miles > 0 ? netProfit / load.miles : 0;

  return {
    loadId,
    grossRate: load.gross_rate,
    fuelSurcharge: load.fuel_surcharge,
    detentionPay: load.detention_pay,
    factoringFee: load.factoring_enabled
      ? load.net_pay * (load.factoring_percent / 100)
      : 0,
    netPay: load.net_pay,
    miles: load.miles,
    expenses,
    totalExpenses,
    netProfit,
    revenuePerMile: parseFloat(revenuePerMile.toFixed(4)),
    costPerMile: parseFloat(costPerMile.toFixed(4)),
    profitPerMile: parseFloat(profitPerMile.toFixed(4)),
    origin: load.origin,
    destination: load.destination,
    brokerName: load.broker_name,
  };
}

/**
 * Learn and persist a vendor → category mapping.
 *
 * @param {string} vendor
 * @param {string} category
 * @returns {Promise<void>}
 */
export async function learnVendorCategory(vendor, category) {
  if (!vendor || !category) return;

  const db = await getDb();
  const learned_at = new Date().toISOString();

  await db.runAsync(
    `INSERT OR REPLACE INTO vendor_categories (vendor_name, category, learned_at)
     VALUES (?, ?, ?)`,
    [vendor.trim().toLowerCase(), category, learned_at]
  );
}

/**
 * Look up the learned category for a vendor.
 *
 * @param {string} vendor
 * @returns {Promise<string|null>}
 */
export async function getVendorCategory(vendor) {
  if (!vendor) return null;

  const db = await getDb();
  const row = await db.getFirstAsync(
    `SELECT category FROM vendor_categories WHERE vendor_name = ?`,
    [vendor.trim().toLowerCase()]
  );

  return row?.category ?? null;
}

/**
 * Get all expense records in a date range (for export/display).
 *
 * @param {string} startDate  ISO date
 * @param {string} endDate    ISO date
 * @returns {Promise<Array>}
 */
export async function getExpensesByPeriod(startDate, endDate) {
  const db = await getDb();
  const rows = await db.getAllAsync(
    `SELECT * FROM expenses
     WHERE trip_date >= ? AND trip_date <= ?
     ORDER BY trip_date DESC, created_at DESC`,
    [startDate, endDate]
  );
  return rows || [];
}

/**
 * Get all loads in a date range.
 *
 * @param {string} startDate
 * @param {string} endDate
 * @returns {Promise<Array>}
 */
export async function getLoadsByPeriod(startDate, endDate) {
  const db = await getDb();
  const rows = await db.getAllAsync(
    `SELECT * FROM loads
     WHERE created_at >= ? AND created_at <= ?
     ORDER BY created_at DESC`,
    [startDate, endDate]
  );
  return rows || [];
}

/**
 * Delete all expense and load data (testing/reset only).
 */
export async function clearAllExpenseData() {
  const db = await getDb();
  await db.execAsync(`
    DELETE FROM expenses;
    DELETE FROM loads;
    DELETE FROM vendor_categories;
  `);
}
