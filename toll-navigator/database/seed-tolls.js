/**
 * Toll Navigator — Seeder данных о платных дорогах США
 * День 4: Наполнение БД реальными тарифами (2024-2025)
 */

const { DatabaseSync } = require('node:sqlite');
const path = require('path');

const DB_PATH = path.join(__dirname, '../data/toll_navigator.db');
const db = new DatabaseSync(DB_PATH);

// Данные о платных дорогах по 5 штатам
// flat rate: cost_per_axle=0, min_cost=flat_price
// per mile: cost_per_axle=rate, min_cost=0
const TOLL_DATA = [
  // ── TEXAS ──────────────────────────────────────────────
  { road_name: 'Dallas North Tollway',           state: 'TX', cost_per_axle: 0.22, min_cost: 0 },
  { road_name: 'President George Bush Turnpike', state: 'TX', cost_per_axle: 0.18, min_cost: 0 },
  { road_name: 'Sam Rayburn Tollway (SH 121)',   state: 'TX', cost_per_axle: 0.20, min_cost: 0 },
  { road_name: 'Loop 49 Tyler',                  state: 'TX', cost_per_axle: 0.15, min_cost: 0 },
  { road_name: 'Hardy Toll Road',                state: 'TX', cost_per_axle: 0.17, min_cost: 0 },
  { road_name: 'Westpark Tollway',               state: 'TX', cost_per_axle: 0.19, min_cost: 0 },

  // ── FLORIDA ────────────────────────────────────────────
  { road_name: 'Florida Turnpike',               state: 'FL', cost_per_axle: 0.067, min_cost: 0 },
  { road_name: 'I-75 Alligator Alley',           state: 'FL', cost_per_axle: 0,    min_cost: 6.00 },
  { road_name: 'Osceola Parkway',                state: 'FL', cost_per_axle: 0,    min_cost: 1.25 },
  { road_name: 'Beachline Expressway (SR-528)',  state: 'FL', cost_per_axle: 0,    min_cost: 0.80 },
  { road_name: 'Seminole Expressway',            state: 'FL', cost_per_axle: 0.05, min_cost: 0 },
  { road_name: 'Veterans Expressway',            state: 'FL', cost_per_axle: 0.05, min_cost: 0 },

  // ── NEW YORK ───────────────────────────────────────────
  { road_name: 'New York State Thruway (I-90)',  state: 'NY', cost_per_axle: 0.085, min_cost: 0 },
  { road_name: 'Gov. Mario Cuomo Bridge',        state: 'NY', cost_per_axle: 0,    min_cost: 5.00 },
  { road_name: 'Brooklyn-Battery Tunnel',        state: 'NY', cost_per_axle: 0,    min_cost: 8.50 },
  { road_name: 'Verrazzano-Narrows Bridge',      state: 'NY', cost_per_axle: 0,    min_cost: 19.00 },
  { road_name: 'Throgs Neck Bridge',             state: 'NY', cost_per_axle: 0,    min_cost: 8.50 },
  { road_name: 'Whitestone Bridge',              state: 'NY', cost_per_axle: 0,    min_cost: 8.50 },

  // ── ILLINOIS ───────────────────────────────────────────
  { road_name: 'Illinois Tollway I-90',          state: 'IL', cost_per_axle: 0.06, min_cost: 0 },
  { road_name: 'Illinois Tollway I-88',          state: 'IL', cost_per_axle: 0.06, min_cost: 0 },
  { road_name: 'Illinois Tollway I-294',         state: 'IL', cost_per_axle: 0.06, min_cost: 0 },
  { road_name: 'Illinois Tollway I-190',         state: 'IL', cost_per_axle: 0.06, min_cost: 0 },
  { road_name: 'Chicago Skyway',                 state: 'IL', cost_per_axle: 0,    min_cost: 7.00 },

  // ── CALIFORNIA ─────────────────────────────────────────
  { road_name: 'Bay Bridge (San Francisco)',     state: 'CA', cost_per_axle: 0,    min_cost: 7.00 },
  { road_name: 'Golden Gate Bridge',             state: 'CA', cost_per_axle: 0,    min_cost: 8.75 },
  { road_name: 'SR-91 Express Lanes',            state: 'CA', cost_per_axle: 0,    min_cost: 6.50 },
  { road_name: 'I-15 Express Lanes',             state: 'CA', cost_per_axle: 0,    min_cost: 4.00 },
  { road_name: 'San Francisco-Oakland Bay Bridge', state: 'CA', cost_per_axle: 0,  min_cost: 7.00 },
  { road_name: 'Antioch Bridge',                 state: 'CA', cost_per_axle: 0,    min_cost: 6.00 },
];

// Очищаем и наполняем
db.exec('DELETE FROM tolls');

const insert = db.prepare(
  'INSERT INTO tolls (road_name, state, cost_per_axle, min_cost) VALUES (?, ?, ?, ?)'
);

let count = 0;
for (const toll of TOLL_DATA) {
  insert.run(toll.road_name, toll.state, toll.cost_per_axle, toll.min_cost);
  count++;
}

// Проверяем результат
const stats = db.prepare(
  'SELECT state, COUNT(*) as cnt FROM tolls GROUP BY state ORDER BY state'
).all();

console.log(`\n✅ Toll data seeded: ${count} records\n`);
console.log('By state:');
stats.forEach(row => console.log(`  ${row.state}: ${row.cnt} roads`));

db.close();
