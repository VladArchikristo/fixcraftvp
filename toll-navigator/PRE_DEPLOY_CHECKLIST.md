# Toll Navigator — Pre-Deploy Checklist

> Backend: `~/Папка тест/fixcraftvp/toll-navigator/backend/`
> Target: Hetzner server (`api.haulwallet.com`)

## ✅ Code & Logic
- [x] `Dockerfile` — patched to `COPY data/toll_navigator.db /app/data/`
- [x] `tollCalculator.js` — removed erroneous `avgStateCost = stateCost / tolls.length` division
- [x] `server.js` — health check (`/health`, `/api/health`), CORS, rate limiter, global error handler, 404 handler — all present
- [x] `db.js` — WAL mode enabled, foreign keys ON, schema includes users/routes/tolls/trips/fuel/ifta/brokers/waitlist
- [x] `src/routes/tolls.js` — extensive CITY_STATE_MAP, ROUTE_DISTANCES, STATE_MILES — loaded
- [x] Auth middleware (`verifyToken`) present on protected routes

## ✅ Database
- [x] Local DB file exists: `backend/data/toll_navigator.db` (860 KB)
- [x] Zero-rate fix applied: 3,668 records updated with state-average `$/mile`
- [x] Total records: ~3,764 tolls across 47+ states
- [x] Unique road names: 2,483

## ⚠️ Warnings
- [ ] `db.js` has safe-fail migrations (`ALTER TABLE ... ADD COLUMN`), but SQLite can't remove NOT NULL easily — routes table recreation logic is present, test on fresh container
- [ ] `tolls.js` is 1,150 lines — consider splitting into services (cityMap, distances, stateMiles) if it grows
- [ ] `CITY_STATE_MAP` has duplicate keys (e.g., `oklahoma city: 'OK'` appears twice at lines 42 and 60) — non-breaking but messy
- [ ] `ROUTE_DISTANCES` has duplicate key `dallas,tx|houston,tx` (lines 117 and 123) — last value wins in JS, non-breaking
- [ ] `tollCalculator.js` — verify that `getTollsByState` returns correct data after zero-rate fix

## ❌ Blockers (Must Fix Before Deploy)
- [ ] **None critical** — backend code is deploy-ready

## 🔧 Deploy Steps (from DEPLOY_INSTRUCTIONS.md)
1. SSH to Hetzner server
2. `cd ~/toll-navigator/backend`
3. `git pull origin main`
4. `docker build -t toll-navigator:fixed .`
5. `docker stop toll-navigator-backend`
6. `docker rm toll-navigator-backend`
7. `docker run -d --name toll-navigator-backend -p 3000:3000 --env-file .env toll-navigator:fixed`
8. Verify: `curl https://api.haulwallet.com/api/health` → should return DB stats and `version: 0.2.0`
9. Run smoke test: calculate toll Dallas→Houston → should return >$0

## 📊 Post-Deploy Verification
- [ ] `/api/health` returns 200 with cache stats
- [ ] `/api/tolls/calculate` with known route returns non-zero toll cost
- [ ] DB query on prod container returns >3,000 toll records: `docker exec toll-navigator-backend sqlite3 /app/data/toll_navigator.db "SELECT COUNT(*) FROM tolls;"`
- [ ] Zero-rate check: `SELECT COUNT(*) FROM tolls WHERE cost_per_axle = 0;` should be 0 or very low

## ✅ Status: READY TO DEPLOY
