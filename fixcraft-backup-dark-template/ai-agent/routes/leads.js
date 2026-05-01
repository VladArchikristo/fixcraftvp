const express = require('express');
const router = express.Router();
const { all, run } = require('../services/db');

// GET /api/leads — CRM list with optional filters
router.get('/', async (req, res) => {
  try {
    const { source, status, limit = 50, offset = 0 } = req.query;
    let sql = 'SELECT * FROM leads WHERE 1=1';
    const params = [];

    if (source) {
      sql += ' AND source = ?';
      params.push(source);
    }
    if (status) {
      sql += ' AND status = ?';
      params.push(status);
    }
    sql += ' ORDER BY created_at DESC LIMIT ? OFFSET ?';
    params.push(Number(limit), Number(offset));

    const rows = await all(sql, params);
    res.json({ leads: rows, count: rows.length });
  } catch (err) {
    console.error('Get leads error:', err);
    res.status(500).json({ error: 'Failed to fetch leads' });
  }
});

// PATCH /api/leads/:id/status — update lead status
router.patch('/:id/status', async (req, res) => {
  try {
    const { status } = req.body;
    const valid = ['new', 'contacted', 'scheduled', 'completed', 'cancelled'];
    if (!valid.includes(status)) {
      return res.status(400).json({ error: `Invalid status. Use: ${valid.join(', ')}` });
    }
    await run('UPDATE leads SET status = ? WHERE id = ?', [status, req.params.id]);
    res.json({ success: true, id: req.params.id, status });
  } catch (err) {
    console.error('Update lead status error:', err);
    res.status(500).json({ error: 'Failed to update status' });
  }
});

module.exports = router;
