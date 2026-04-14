const express = require('express');
const db = require('../db');
const { verifyToken } = require('../middleware/auth');

const router = express.Router();

// GET /api/users/profile — получить профиль пользователя
router.get('/profile', verifyToken, (req, res) => {
  try {
    const user = db.prepare(`
      SELECT id, email, truck_type, company_name, usdot_number, full_name, created_at
      FROM users WHERE id = ?
    `).get(req.userId);

    if (!user) {
      return res.status(404).json({ error: 'User not found' });
    }

    res.json(user);
  } catch (err) {
    console.error('GET /api/users/profile error:', err);
    res.status(500).json({ error: 'Server error' });
  }
});

// PUT /api/users/profile — обновить профиль пользователя
router.put('/profile', verifyToken, (req, res) => {
  try {
    const { full_name, company_name, truck_type, usdot_number } = req.body;

    // Валидация truck_type если передан
    const validTruckTypes = ['2-axle', '3-axle', '5-axle', '2axle', '3axle', '5axle'];
    if (truck_type && !validTruckTypes.includes(truck_type)) {
      return res.status(400).json({
        error: `Invalid truck_type. Must be one of: ${validTruckTypes.join(', ')}`
      });
    }

    // Строим динамический UPDATE — обновляем только переданные поля
    const fields = [];
    const values = [];

    if (full_name !== undefined) { fields.push('full_name = ?'); values.push(full_name); }
    if (company_name !== undefined) { fields.push('company_name = ?'); values.push(company_name); }
    if (truck_type !== undefined) { fields.push('truck_type = ?'); values.push(truck_type); }
    if (usdot_number !== undefined) { fields.push('usdot_number = ?'); values.push(usdot_number); }

    if (fields.length === 0) {
      return res.status(400).json({
        error: 'No fields to update. Provide at least one: full_name, company_name, truck_type, usdot_number'
      });
    }

    values.push(req.userId);
    db.prepare(`UPDATE users SET ${fields.join(', ')} WHERE id = ?`).run(...values);

    // Возвращаем обновлённый профиль
    const user = db.prepare(`
      SELECT id, email, truck_type, company_name, usdot_number, full_name, created_at
      FROM users WHERE id = ?
    `).get(req.userId);

    res.json(user);
  } catch (err) {
    console.error('PUT /api/users/profile error:', err);
    res.status(500).json({ error: 'Server error' });
  }
});

module.exports = router;
