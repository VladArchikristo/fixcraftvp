const { DatabaseSync } = require('node:sqlite');
const path = require('path');
const fs = require('fs');

const DB_PATH = process.env.DB_PATH || path.join(__dirname, '../../data/toll_navigator.db');

// Создаём папку если нет
const dbDir = path.dirname(DB_PATH);
if (!fs.existsSync(dbDir)) fs.mkdirSync(dbDir, { recursive: true });

const db = new DatabaseSync(DB_PATH);

// Включаем WAL и foreign keys
db.exec('PRAGMA journal_mode = WAL');
db.exec('PRAGMA foreign_keys = ON');

// Создаём таблицы при первом запуске
db.exec(`
  CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    truck_type TEXT DEFAULT '2-axle',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
  );

  CREATE TABLE IF NOT EXISTS routes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    from_city TEXT,
    to_city TEXT,
    truck_type TEXT DEFAULT '5-axle',
    total_toll REAL DEFAULT 0,
    distance_miles REAL DEFAULT 0,
    route_data TEXT,
    states_crossed TEXT DEFAULT '[]',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
  );

  CREATE TABLE IF NOT EXISTS tolls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    road_name TEXT NOT NULL,
    state TEXT NOT NULL,
    cost_per_axle REAL NOT NULL,
    min_cost REAL DEFAULT 0,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
  );

  CREATE INDEX IF NOT EXISTS idx_routes_user_id ON routes(user_id);
  CREATE INDEX IF NOT EXISTS idx_tolls_state ON tolls(state);

  CREATE TABLE IF NOT EXISTS trips (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    from_city TEXT NOT NULL,
    to_city TEXT NOT NULL,
    truck_type TEXT DEFAULT '5-axle',
    total_miles REAL DEFAULT 0,
    state_miles TEXT DEFAULT '{}',
    toll_cost REAL DEFAULT 0,
    fuel_cost REAL DEFAULT 0,
    mpg REAL DEFAULT 6.5,
    quarter INTEGER NOT NULL,
    year INTEGER NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
  );

  CREATE TABLE IF NOT EXISTS fuel_purchases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    trip_id INTEGER REFERENCES trips(id),
    state TEXT NOT NULL,
    gallons REAL NOT NULL,
    price_per_gallon REAL DEFAULT 0,
    station_name TEXT,
    receipt_photo TEXT,
    quarter INTEGER NOT NULL,
    year INTEGER NOT NULL,
    purchase_date DATETIME DEFAULT CURRENT_TIMESTAMP
  );

  CREATE TABLE IF NOT EXISTS ifta_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    quarter INTEGER NOT NULL,
    year INTEGER NOT NULL,
    report_data TEXT DEFAULT '{}',
    total_tax_due REAL DEFAULT 0,
    generated_at DATETIME DEFAULT CURRENT_TIMESTAMP
  );

  CREATE INDEX IF NOT EXISTS idx_trips_user_id ON trips(user_id);
  CREATE INDEX IF NOT EXISTS idx_trips_quarter_year ON trips(user_id, quarter, year);
  CREATE INDEX IF NOT EXISTS idx_fuel_purchases_user_id ON fuel_purchases(user_id);
  CREATE INDEX IF NOT EXISTS idx_fuel_purchases_quarter_year ON fuel_purchases(user_id, quarter, year);
`);

// Migration: add new columns to existing tables (safe — fails silently if already exist)
const migrateColumns = [
  `ALTER TABLE routes ADD COLUMN from_city TEXT`,
  `ALTER TABLE routes ADD COLUMN to_city TEXT`,
  `ALTER TABLE routes ADD COLUMN truck_type TEXT DEFAULT '5-axle'`,
  `ALTER TABLE routes ADD COLUMN total_toll REAL DEFAULT 0`,
  `ALTER TABLE routes ADD COLUMN route_data TEXT`,
];
migrateColumns.forEach(sql => { try { db.exec(sql); } catch (_) {} });

// Copy old column data to new columns if migration just happened
try {
  db.exec(`UPDATE routes SET from_city = origin WHERE from_city IS NULL AND origin IS NOT NULL`);
  db.exec(`UPDATE routes SET to_city = destination WHERE to_city IS NULL AND destination IS NOT NULL`);
  db.exec(`UPDATE routes SET total_toll = toll_cost WHERE total_toll = 0 AND toll_cost IS NOT NULL`);
} catch (_) {}

// Fix NOT NULL constraint on legacy origin/destination columns (SQLite can't ALTER constraints,
// so we recreate the table preserving all data)
try {
  const hasNotNull = db.prepare(`PRAGMA table_info(routes)`).all()
    .some(c => (c.name === 'origin' || c.name === 'destination') && c.notnull === 1);

  if (hasNotNull) {
    console.log('Migrating routes table: removing NOT NULL from origin/destination...');
    db.exec(`
      BEGIN;
      CREATE TABLE IF NOT EXISTS routes_new (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        origin TEXT DEFAULT '',
        destination TEXT DEFAULT '',
        toll_cost REAL DEFAULT 0,
        distance_miles REAL DEFAULT 0,
        states_crossed TEXT DEFAULT '[]',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        from_city TEXT,
        to_city TEXT,
        truck_type TEXT DEFAULT '5-axle',
        total_toll REAL DEFAULT 0,
        route_data TEXT,
        FOREIGN KEY (user_id) REFERENCES users(id)
      );
      INSERT INTO routes_new SELECT * FROM routes;
      DROP TABLE routes;
      ALTER TABLE routes_new RENAME TO routes;
      CREATE INDEX IF NOT EXISTS idx_routes_user_id ON routes(user_id);
      COMMIT;
    `);
    console.log('Migration complete: routes table updated.');
  }
} catch (migErr) {
  console.error('Migration error (routes NOT NULL fix):', migErr.message);
}

console.log(`SQLite DB ready: ${DB_PATH}`);

module.exports = db;
