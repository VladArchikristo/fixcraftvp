require('dotenv').config();
const express = require('express');
const cors = require('cors');
const path = require('path');

const app = express();
app.use(cors());
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// Init DB
const { initDB } = require('./services/db');
initDB();

// Routes
app.use('/api/chat', require('./routes/chat'));
app.use('/api/sms', require('./routes/sms'));
app.use('/api/voice', require('./routes/voice'));

// Health
app.get('/api/health', (req, res) => {
  res.json({ status: 'ok', service: 'fixcraft-ai-agent', uptime: process.uptime() });
});

const PORT = process.env.PORT || 3002;
app.listen(PORT, () => {
  console.log(`FixCraft AI Agent running on port ${PORT}`);
});
