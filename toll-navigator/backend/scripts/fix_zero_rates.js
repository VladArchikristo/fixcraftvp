/**
 * Fix zero-cost toll records
 * Updates tolls where cost_per_axle=0 AND min_cost=0 with realistic state averages.
 */

const { DatabaseSync } = require('node:sqlite');
const path = require('path');

const DB_PATH = process.env.DB_PATH || path.join(__dirname, '../data/toll_navigator.db');
const db = new DatabaseSync(DB_PATH);

// Realistic average state rates per axle per mile (USD)
const STATE_RATES = {
  TX: 0.18,
  FL: 0.06,
  NY: 0.08,
  PA: 0.10,
  IL: 0.06,
  OH: 0.03,
  IN: 0.03,
  NJ: 0.10,
  CA: 0.08,
  VA: 0.06,
  MA: 0.05,
  MD: 0.08,
  OK: 0.03,
  WA: 0.06,
  CO: 0.07,
  MN: 0.05,
  AZ: 0.04,
  NV: 0.05,
  NC: 0.05,
  GA: 0.05,
};

const DEFAULT_RATE = 0.04;

function getRate(state) {
  return STATE_RATES[state.toUpperCase()] || DEFAULT_RATE;
}

function main() {
  const stmt = db.prepare(
    "SELECT id, state, road_name, cost_per_axle, min_cost FROM tolls WHERE cost_per_axle = 0 AND min_cost = 0"
  );
  const rows = stmt.all();

  console.log(`Found ${rows.length} zero-cost toll records.`);

  const updateStmt = db.prepare(
    "UPDATE tolls SET cost_per_axle = ? WHERE id = ?"
  );

  let updated = 0;
  for (const row of rows) {
    const rate = getRate(row.state);
    updateStmt.run(rate, row.id);
    updated++;
  }

  console.log(`Updated ${updated} records with state average rates.`);
}

main();
