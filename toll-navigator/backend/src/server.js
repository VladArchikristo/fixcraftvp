require('dotenv').config();
const express = require('express');
const cors = require('cors');

// Инициализируем БД при старте
require('./db');

const app = express();
const PORT = process.env.PORT || 3000;

app.use(cors());
app.use(express.json());

// Health check
app.get('/health', (_req, res) => {
  const cache = require('./services/cache');
  res.json({
    status: 'ok',
    uptime: process.uptime(),
    version: '0.2.0',
    cache: cache.stats(),
  });
});

// Auth роуты
app.use('/api/auth', require('./routes/auth'));

// Toll Calculator
app.use('/api/tolls', require('./routes/tolls'));

// 404 handler
app.use((_req, res) => {
  res.status(404).json({ error: 'Not found' });
});

app.listen(PORT, () => {
  console.log(`Toll Navigator API v0.2.0 running on port ${PORT}`);
});

module.exports = app;
