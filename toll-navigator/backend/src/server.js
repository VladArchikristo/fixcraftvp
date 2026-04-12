require('dotenv').config();
const express = require('express');
const cors = require('cors');

const app = express();
const PORT = process.env.PORT || 3000;

app.use(cors());
app.use(express.json());

// Health check
app.get('/health', (_req, res) => {
  res.json({ status: 'ok', uptime: process.uptime() });
});

// TODO: подключить роуты
// app.use('/api/auth', require('./routes/auth'));
// app.use('/api/routes', require('./routes/routes'));
// app.use('/api/tolls', require('./routes/tolls'));

app.listen(PORT, () => {
  console.log(`Toll Navigator API running on port ${PORT}`);
});

module.exports = app;
