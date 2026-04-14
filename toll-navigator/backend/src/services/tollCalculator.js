/**
 * Toll Calculator Service
 * Рассчитывает стоимость толлов по маршруту
 */

const db = require('../db');

// Axle multipliers по типу грузовика
const AXLE_CONFIG = {
  '2-axle':  { axles: 2,  multiplier: 1.0 },
  '3-axle':  { axles: 3,  multiplier: 1.8 },
  '4-axle':  { axles: 4,  multiplier: 2.5 },
  '5-axle':  { axles: 5,  multiplier: 3.2 },  // стандартный 18-wheeler
  '6-axle':  { axles: 6,  multiplier: 3.8 },
};

/**
 * Получить все толлы по штату
 */
function getTollsByState(state) {
  return db.prepare(
    'SELECT * FROM tolls WHERE state = ? ORDER BY road_name'
  ).all(state.toUpperCase());
}

/**
 * Рассчитать стоимость толлов для маршрута
 * @param {string[]} states - штаты на маршруте (например ['TX', 'LA', 'FL'])
 * @param {number} distanceMiles - общая дистанция в милях
 * @param {string} truckType - тип грузовика
 * @param {object} [stateMilesMap] - распределение миль по штатам { TX: 400, OK: 190, ... }
 * @returns {{ total: number, breakdown: object[], states: string[] }}
 */
function calculateTollCost(states, distanceMiles, truckType = '2-axle', stateMilesMap = null) {
  const config = AXLE_CONFIG[truckType] || AXLE_CONFIG['2-axle'];
  const breakdown = [];
  let total = 0;

  for (const state of states) {
    const tolls = getTollsByState(state);
    if (tolls.length === 0) continue;

    // Используем точное распределение миль по штату если доступно
    const milesInState = (stateMilesMap && stateMilesMap[state]) ? stateMilesMap[state] : distanceMiles / states.length;

    let stateCost = 0;

    for (const toll of tolls) {
      let cost = 0;

      if (toll.cost_per_axle > 0) {
        // Per-mile rate
        cost = toll.cost_per_axle * milesInState * config.multiplier;
      } else if (toll.min_cost > 0) {
        // Flat rate (умножаем на множитель за оси)
        cost = toll.min_cost * config.multiplier;
      }

      // Берём средний toll из доступных дорог в штате
      stateCost += cost;
    }

    // Используем среднее по штату (не сумму всех дорог)
    const avgStateCost = stateCost / tolls.length;
    total += avgStateCost;

    breakdown.push({
      state,
      roads: tolls.length,
      miles_in_state: Math.round(milesInState),
      cost: parseFloat(avgStateCost.toFixed(2)),
    });
  }

  return {
    total: parseFloat(total.toFixed(2)),
    truck_type: truckType,
    axles: config.axles,
    breakdown,
    states_crossed: states,
  };
}

/**
 * Получить все штаты для которых есть данные
 */
function getAvailableStates() {
  const rows = db.prepare(
    'SELECT DISTINCT state FROM tolls ORDER BY state'
  ).all();
  return rows.map(r => r.state);
}

module.exports = { calculateTollCost, getTollsByState, getAvailableStates };
