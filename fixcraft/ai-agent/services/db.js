const sqlite3 = require('sqlite3').verbose();
const path = require('path');

const dbPath = process.env.DB_PATH || path.join(process.cwd(), '..', 'data', 'fixcraft.db');
let db;

function getDB() {
  if (!db) {
    db = new sqlite3.Database(dbPath);
  }
  return db;
}

function run(sql, params = []) {
  return new Promise((resolve, reject) => {
    getDB().run(sql, params, function(err) {
      if (err) reject(err);
      else resolve({ id: this.lastID, changes: this.changes });
    });
  });
}

function all(sql, params = []) {
  return new Promise((resolve, reject) => {
    getDB().all(sql, params, (err, rows) => {
      if (err) reject(err);
      else resolve(rows);
    });
  });
}

function get(sql, params = []) {
  return new Promise((resolve, reject) => {
    getDB().get(sql, params, (err, row) => {
      if (err) reject(err);
      else resolve(row);
    });
  });
}

function initDB() {
  const d = getDB();
  d.serialize(() => {
    d.run(`CREATE TABLE IF NOT EXISTS leads (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT, phone TEXT, email TEXT, address TEXT,
      service_type TEXT, urgency TEXT, notes TEXT,
      source TEXT DEFAULT 'chat', status TEXT DEFAULT 'new',
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )`);
    d.run(`CREATE TABLE IF NOT EXISTS appointments (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      lead_id INTEGER, name TEXT, phone TEXT, address TEXT,
      service_type TEXT, date TEXT, time_slot TEXT,
      calendar_event_id TEXT, status TEXT DEFAULT 'pending',
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )`);
    d.run(`CREATE TABLE IF NOT EXISTS chats (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      session_id TEXT, role TEXT, content TEXT,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )`);
    
    // Anti-spam tables for voice calls
    d.run(`CREATE TABLE IF NOT EXISTS spam_blacklist (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      phone_number TEXT UNIQUE NOT NULL,
      reason TEXT DEFAULT 'Manual',
      added_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )`);
    d.run(`CREATE TABLE IF NOT EXISTS call_log (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      caller_number TEXT,
      status TEXT,
      duration INTEGER,
      timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )`);
    d.run(`CREATE INDEX IF NOT EXISTS idx_call_log_number ON call_log(caller_number)`);
    d.run(`CREATE INDEX IF NOT EXISTS idx_call_log_time ON call_log(timestamp)`);
    d.run(`CREATE INDEX IF NOT EXISTS idx_leads_source ON leads(source)`);
    d.run(`CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(status)`);
    d.run(`CREATE INDEX IF NOT EXISTS idx_leads_created ON leads(created_at)`);
  });
  console.log('SQLite initialized at', dbPath);
}

module.exports = { getDB, initDB, run, all, get };
