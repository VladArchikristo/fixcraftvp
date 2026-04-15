require('dotenv').config();
const express = require('express');
const cors = require('cors');
const rateLimit = require('express-rate-limit');
const path = require('path');

// Инициализируем БД при старте
require('./db');

const app = express();
const PORT = process.env.PORT || 3000;

app.use(cors({
  origin: process.env.ALLOWED_ORIGINS
    ? process.env.ALLOWED_ORIGINS.split(',')
    : ['http://localhost:3000', 'http://localhost:19006', 'exp://', 'https://haulwallet.com', 'https://www.haulwallet.com', 'https://api.haulwallet.com'],
  methods: ['GET', 'POST', 'PUT', 'DELETE'],
  allowedHeaders: ['Content-Type', 'Authorization']
}));
app.use(express.json());

const limiter = rateLimit({
  windowMs: 15 * 60 * 1000, // 15 минут
  max: 100, // максимум 100 запросов
  message: { error: 'Too many requests, please try again later.' }
});
app.use('/api/', limiter);

// Health check — доступен и как /health и как /api/health
const healthHandler = (_req, res) => {
  const cache = require('./services/cache');
  res.json({
    status: 'ok',
    uptime: process.uptime(),
    version: '0.2.0',
    cache: cache.stats(),
  });
};
app.get('/health', healthHandler);
app.get('/api/health', healthHandler);

// Auth роуты
app.use('/api/auth', require('./routes/auth'));

// Toll Calculator
app.use('/api/tolls', require('./routes/tolls'));

// Trips history + IFTA
app.use('/api/trips', require('./routes/trips'));

// User profile
app.use('/api/users', require('./routes/users'));

// Broker check
app.use('/api/brokers', require('./routes/brokers'));

// Document scanner — OCR + edge detection
app.use('/api/documents', require('./routes/documents'));

// Live Load Tracking
app.use('/api/tracking', require('./routes/tracking'));

// Waitlist (landing page signups)
app.use('/api/waitlist', require('./routes/waitlist'));

// Landing page
app.get('/', (_req, res) => {
  res.sendFile(path.join(__dirname, '../public', 'index.html'));
});

// Static assets (CSS, images, etc.)
app.use('/assets', express.static(path.join(__dirname, '../public/assets')));

// Serve broker tracking page at /track/:token
// track.html reads the token from window.location.pathname and polls the API
app.use('/track', express.static(path.join(__dirname, '../public')));
app.get('/track/:token', (_req, res) => {
  res.sendFile(path.join(__dirname, '../public', 'track.html'));
});

// Global error handler
app.use((err, req, res, next) => {
  console.error('Unhandled error:', err.message);
  res.status(err.status || 500).json({
    error: err.message || 'Internal server error'
  });
});

// 404 handler
app.use((req, res) => {
  res.status(404).json({ error: 'Route not found' });
});

app.listen(PORT, () => {
  console.log(`Toll Navigator API v0.2.0 running on port ${PORT}`);
});

module.exports = app;
