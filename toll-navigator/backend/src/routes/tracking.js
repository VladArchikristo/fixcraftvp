const express = require('express');
const { verifyToken } = require('../middleware/auth');
const LoadTracking = require('../models/LoadTracking');

const router = express.Router();

const BASE_URL = process.env.BASE_URL || 'http://localhost:3000';

// ─── POST /api/tracking/start ─────────────────────────────────────────────────
// Creates a new load tracking session. Returns token + public broker URL.
// Requires auth (driver must be logged in).
router.post('/start', verifyToken, (req, res) => {
  const { destination } = req.body;

  if (!destination || typeof destination !== 'string' || !destination.trim()) {
    return res.status(400).json({ error: 'destination is required' });
  }

  const session = LoadTracking.create(req.userId, destination.trim());
  const trackingUrl = `${BASE_URL}/track/${session.token}`;

  return res.status(201).json({
    token: session.token,
    trackingUrl,
    destination: session.destination,
    createdAt: session.createdAt,
  });
});

// ─── POST /api/tracking/update ────────────────────────────────────────────────
// Called by the driver app (background GPS task) to push current position.
// No auth required — token acts as the secret.
router.post('/update', (req, res) => {
  const { token, lat, lng, speed } = req.body;

  if (!token) return res.status(400).json({ error: 'token is required' });
  if (lat === undefined || lng === undefined) {
    return res.status(400).json({ error: 'lat and lng are required' });
  }

  const latNum = parseFloat(lat);
  const lngNum = parseFloat(lng);
  if (isNaN(latNum) || isNaN(lngNum) || !isFinite(latNum) || !isFinite(lngNum)) {
    return res.status(400).json({ error: 'lat and lng must be valid numbers' });
  }
  if (latNum < -90 || latNum > 90 || lngNum < -180 || lngNum > 180) {
    return res.status(400).json({ error: 'lat must be -90..90, lng must be -180..180' });
  }

  const speedNum = speed != null ? parseFloat(speed) : null;
  if (speedNum !== null && (!isFinite(speedNum) || speedNum < 0 || speedNum > 200)) {
    return res.status(400).json({ error: 'speed must be a valid number between 0 and 200 mph' });
  }
  const session = LoadTracking.updatePosition(token, latNum, lngNum, speedNum);
  if (!session) {
    return res.status(404).json({ error: 'Tracking session not found or already stopped' });
  }

  return res.json({ ok: true, updatedAt: session.updatedAt });
});

// ─── POST /api/tracking/stop ──────────────────────────────────────────────────
// Marks delivery as done. Link will show "Load delivered" to broker.
// Requires auth so only the driver can stop their own session.
router.post('/stop', verifyToken, (req, res) => {
  const { token } = req.body;
  if (!token) return res.status(400).json({ error: 'token is required' });

  const session = LoadTracking.get(token);
  if (!session) return res.status(404).json({ error: 'Session not found' });
  if (session.driverId !== req.userId) {
    return res.status(403).json({ error: 'Not your tracking session' });
  }

  LoadTracking.stop(token);
  return res.json({ ok: true, message: 'Tracking stopped. Load delivered.' });
});

// ─── GET /api/tracking/:token ─────────────────────────────────────────────────
// Public endpoint — used by track.html to poll position.
// Returns only the fields the broker needs; no sensitive driver data.
router.get('/:token', (req, res) => {
  const { token } = req.params;
  const session = LoadTracking.get(token.toUpperCase());

  if (!session) {
    return res.status(404).json({ error: 'Tracking session not found' });
  }

  return res.json({
    lat: session.lat,
    lng: session.lng,
    speed: session.speed,
    updatedAt: session.updatedAt,
    destination: session.destination,
    eta: session.eta,
    active: session.active,
  });
});

module.exports = router;
