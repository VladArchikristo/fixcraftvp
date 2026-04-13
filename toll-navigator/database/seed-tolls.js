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

  // ── PENNSYLVANIA ───────────────────────────────────────
  { road_name: 'Pennsylvania Turnpike (I-76)',          state: 'PA', cost_per_axle: 0.097, min_cost: 0 },
  { road_name: 'Pennsylvania Turnpike NE Extension',    state: 'PA', cost_per_axle: 0.097, min_cost: 0 },
  { road_name: 'Mon/Fayette Expressway (SR-43)',        state: 'PA', cost_per_axle: 0.082, min_cost: 0 },
  { road_name: 'Amos K. Hutchinson Bypass (PA-66)',     state: 'PA', cost_per_axle: 0,     min_cost: 1.00 },
  { road_name: 'Delaware River Bridge Tolls (I-95)',    state: 'PA', cost_per_axle: 0,     min_cost: 5.00 },

  // ── OHIO ───────────────────────────────────────────────
  { road_name: 'Ohio Turnpike (I-80/I-90)',             state: 'OH', cost_per_axle: 0.028, min_cost: 0 },
  { road_name: 'Ohio Turnpike East Extension (I-76)',   state: 'OH', cost_per_axle: 0.028, min_cost: 0 },
  { road_name: 'Columbus Southern Ohio Corridor',       state: 'OH', cost_per_axle: 0.025, min_cost: 0 },

  // ── NORTH CAROLINA ─────────────────────────────────────
  { road_name: 'Triangle Expressway (NC-540)',          state: 'NC', cost_per_axle: 0,     min_cost: 1.00 },
  { road_name: 'Monroe Expressway (US-74)',             state: 'NC', cost_per_axle: 0,     min_cost: 1.50 },
  { road_name: 'I-77 Express Lanes Charlotte',          state: 'NC', cost_per_axle: 0,     min_cost: 2.50 },
  { road_name: 'Outer Loop Toll (NC-540 SE)',           state: 'NC', cost_per_axle: 0,     min_cost: 1.25 },

  // ── INDIANA ────────────────────────────────────────────
  { road_name: 'Indiana Toll Road (I-90)',              state: 'IN', cost_per_axle: 0.032, min_cost: 0 },
  { road_name: 'Indiana Toll Road (I-80 Segment)',      state: 'IN', cost_per_axle: 0.032, min_cost: 0 },
  { road_name: 'I-69 Express Toll Lanes',               state: 'IN', cost_per_axle: 0,     min_cost: 2.00 },

  // ── GEORGIA ────────────────────────────────────────────
  { road_name: 'I-75 Express Lanes (Atlanta)',          state: 'GA', cost_per_axle: 0,     min_cost: 3.00 },
  { road_name: 'I-285 Northwest Express Lanes',         state: 'GA', cost_per_axle: 0,     min_cost: 2.50 },
  { road_name: 'I-85 Express Lanes (NE Atlanta)',       state: 'GA', cost_per_axle: 0,     min_cost: 2.00 },
  { road_name: 'I-20 Express Lanes (West Atlanta)',     state: 'GA', cost_per_axle: 0,     min_cost: 3.50 },

  // ── NEW JERSEY ─────────────────────────────────────────
  { road_name: 'New Jersey Turnpike (I-95)',            state: 'NJ', cost_per_axle: 0.10,  min_cost: 0 },
  { road_name: 'Garden State Parkway',                  state: 'NJ', cost_per_axle: 0.10,  min_cost: 0 },
  { road_name: 'Atlantic City Expressway',              state: 'NJ', cost_per_axle: 0,     min_cost: 3.75 },
  { road_name: 'Lincoln Tunnel (NJ approach)',          state: 'NJ', cost_per_axle: 0,     min_cost: 17.00 },
  { road_name: 'Holland Tunnel (NJ approach)',          state: 'NJ', cost_per_axle: 0,     min_cost: 17.00 },

  // ── VIRGINIA ───────────────────────────────────────────
  { road_name: 'Dulles Toll Road (VA-267)',             state: 'VA', cost_per_axle: 0,     min_cost: 2.50 },
  { road_name: 'I-95 Express Lanes',                   state: 'VA', cost_per_axle: 0,     min_cost: 4.00 },
  { road_name: 'I-66 Express Lanes (Inside Beltway)',  state: 'VA', cost_per_axle: 0,     min_cost: 5.00 },
  { road_name: 'Chesapeake Bay Bridge-Tunnel (US-13)', state: 'VA', cost_per_axle: 0,     min_cost: 18.00 },
  { road_name: 'Hampton Roads Bridge-Tunnel (I-64)',   state: 'VA', cost_per_axle: 0,     min_cost: 3.00 },

  // ── MASSACHUSETTS ──────────────────────────────────────
  { road_name: 'Massachusetts Turnpike (I-90)',         state: 'MA', cost_per_axle: 0.047, min_cost: 0 },
  { road_name: 'Tobin Memorial Bridge (US-1)',          state: 'MA', cost_per_axle: 0,     min_cost: 3.50 },
  { road_name: 'Ted Williams Tunnel (I-90)',            state: 'MA', cost_per_axle: 0,     min_cost: 3.50 },
  { road_name: 'Callahan/Sumner Tunnel (US-1A)',        state: 'MA', cost_per_axle: 0,     min_cost: 3.50 },

  // ── MARYLAND ───────────────────────────────────────────
  { road_name: 'I-95 John F. Kennedy Memorial Hwy',    state: 'MD', cost_per_axle: 0,     min_cost: 8.00 },
  { road_name: 'Chesapeake Bay Bridge (US-50)',         state: 'MD', cost_per_axle: 0,     min_cost: 6.00 },
  { road_name: 'Fort McHenry Tunnel (I-95)',            state: 'MD', cost_per_axle: 0,     min_cost: 4.00 },
  { road_name: 'Baltimore Harbor Tunnel (I-895)',       state: 'MD', cost_per_axle: 0,     min_cost: 4.00 },
  { road_name: 'Thomas J. Hatem Bridge (US-40)',        state: 'MD', cost_per_axle: 0,     min_cost: 3.00 },

  // ── OKLAHOMA ───────────────────────────────────────────
  { road_name: 'Turner Turnpike (I-44)',                state: 'OK', cost_per_axle: 0.035, min_cost: 0 },
  { road_name: 'Will Rogers Turnpike (I-44 NE)',        state: 'OK', cost_per_axle: 0.035, min_cost: 0 },
  { road_name: 'Kilpatrick Turnpike (OK-74)',           state: 'OK', cost_per_axle: 0.025, min_cost: 0 },
  { road_name: 'H.E. Bailey Turnpike (I-44 SW)',        state: 'OK', cost_per_axle: 0.030, min_cost: 0 },
  { road_name: 'Muskogee Turnpike (US-69)',             state: 'OK', cost_per_axle: 0.028, min_cost: 0 },

  // ── WASHINGTON ─────────────────────────────────────────
  { road_name: 'SR-520 Floating Bridge',                state: 'WA', cost_per_axle: 0,     min_cost: 4.30 },
  { road_name: 'Tacoma Narrows Bridge (SR-16)',         state: 'WA', cost_per_axle: 0,     min_cost: 6.75 },
  { road_name: 'SR-99 Alaskan Way Tunnel',              state: 'WA', cost_per_axle: 0,     min_cost: 3.25 },
  { road_name: 'I-405 Express Toll Lanes',              state: 'WA', cost_per_axle: 0.08,  min_cost: 0 },
  { road_name: 'SR-167 HOT Lanes',                      state: 'WA', cost_per_axle: 0.06,  min_cost: 0 },

  // ── ARIZONA ────────────────────────────────────────────
  { road_name: 'Loop 101 Pima Freeway',                 state: 'AZ', cost_per_axle: 0,     min_cost: 1.50 },
  { road_name: 'Loop 202 South Mountain Frwy',          state: 'AZ', cost_per_axle: 0,     min_cost: 1.75 },
  { road_name: 'SR-30 (Gateway Freeway)',                state: 'AZ', cost_per_axle: 0,     min_cost: 2.00 },
  { road_name: 'Price Road Corridor (Loop 202)',        state: 'AZ', cost_per_axle: 0.05,  min_cost: 0 },
  { road_name: 'SR-87 Beeline Hwy Express Lanes',       state: 'AZ', cost_per_axle: 0.04,  min_cost: 0 },

  // ── NEVADA ─────────────────────────────────────────────
  { road_name: 'I-15 Express Lanes (Las Vegas)',        state: 'NV', cost_per_axle: 0,     min_cost: 3.00 },
  { road_name: 'US-95 Express Lanes (Henderson)',       state: 'NV', cost_per_axle: 0,     min_cost: 2.50 },
  { road_name: 'SR-582 MLK Blvd (Henderson Toll)',      state: 'NV', cost_per_axle: 0,     min_cost: 1.75 },
  { road_name: 'I-580 Express Lanes (Reno)',            state: 'NV', cost_per_axle: 0.04,  min_cost: 0 },
  { road_name: 'Las Vegas Beltway HOT Lanes (I-215)',   state: 'NV', cost_per_axle: 0.05,  min_cost: 0 },

  // ── COLORADO ───────────────────────────────────────────
  { road_name: 'E-470 Toll Highway',                    state: 'CO', cost_per_axle: 0.085, min_cost: 0 },
  { road_name: 'Northwest Parkway (US-36 Toll)',        state: 'CO', cost_per_axle: 0,     min_cost: 4.25 },
  { road_name: 'C-470 Express Toll Lanes',              state: 'CO', cost_per_axle: 0.07,  min_cost: 0 },
  { road_name: 'I-25 Express Lanes (Denver)',           state: 'CO', cost_per_axle: 0.06,  min_cost: 0 },
  { road_name: 'US-36 Managed Lanes (Boulder Tpke)',    state: 'CO', cost_per_axle: 0,     min_cost: 3.00 },

  // ── MINNESOTA ──────────────────────────────────────────
  { road_name: 'MnPASS I-35W Express Lanes',           state: 'MN', cost_per_axle: 0.06,  min_cost: 0 },
  { road_name: 'MnPASS I-394 Managed Lanes',           state: 'MN', cost_per_axle: 0,     min_cost: 2.50 },
  { road_name: 'MnPASS I-35E Express Lanes',           state: 'MN', cost_per_axle: 0.05,  min_cost: 0 },
  { road_name: 'Minnesota Trunk Hwy 62 (Crosstown)',   state: 'MN', cost_per_axle: 0,     min_cost: 1.50 },
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
