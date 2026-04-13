const express = require('express');
const { verifyToken } = require('../middleware/auth');
const { calculateTollCost, getTollsByState, getAvailableStates } = require('../services/tollCalculator');
const db = require('../db');

const router = express.Router();

/**
 * POST /api/tolls/calculate
 * Рассчитать стоимость толлов
 * Body: { states: ['TX', 'LA'], distance_miles: 500, truck_type: '5-axle' }
 */
router.post('/calculate', verifyToken, (req, res) => {
  try {
    const { states, distance_miles, truck_type = '2-axle', origin = '', destination = '' } = req.body;

    if (!states || !Array.isArray(states) || states.length === 0) {
      return res.status(400).json({ error: 'states array is required (e.g. ["TX", "LA"])' });
    }
    if (!distance_miles || distance_miles <= 0) {
      return res.status(400).json({ error: 'distance_miles must be a positive number' });
    }

    const validStates = getAvailableStates();
    const unknown = states.filter(s => !validStates.includes(s.toUpperCase()));
    if (unknown.length > 0) {
      return res.status(400).json({
        error: `No toll data for states: ${unknown.join(', ')}`,
        available_states: validStates,
      });
    }

    const result = calculateTollCost(
      states.map(s => s.toUpperCase()),
      parseFloat(distance_miles),
      truck_type
    );

    // Сохраняем маршрут в историю
    db.prepare(
      'INSERT INTO routes (user_id, origin, destination, toll_cost, distance_miles, states_crossed) VALUES (?, ?, ?, ?, ?, ?)'
    ).run(
      req.userId,
      origin || states[0],
      destination || states[states.length - 1],
      result.total,
      distance_miles,
      JSON.stringify(result.states_crossed)
    );

    res.json(result);
  } catch (err) {
    console.error('Calculate error:', err);
    res.status(500).json({ error: 'Server error' });
  }
});

/**
 * GET /api/tolls/states
 * Список штатов с данными
 */
router.get('/states', (req, res) => {
  res.json({ states: getAvailableStates() });
});

/**
 * GET /api/tolls/state/:code
 * Toll дороги конкретного штата
 */
router.get('/state/:code', (req, res) => {
  const roads = getTollsByState(req.params.code);
  if (roads.length === 0) {
    return res.status(404).json({ error: 'No data for this state' });
  }
  res.json({ state: req.params.code.toUpperCase(), roads });
});

/**
 * GET /api/tolls/history
 * История маршрутов текущего пользователя
 */
router.get('/history', verifyToken, (req, res) => {
  const routes = db.prepare(
    'SELECT * FROM routes WHERE user_id = ? ORDER BY created_at DESC LIMIT 20'
  ).all(req.userId);
  res.json(routes);
});

module.exports = router;
