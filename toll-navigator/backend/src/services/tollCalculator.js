/**
 * Toll Calculator Service
 * Рассчитывает стоимость толлов по маршруту
 * 
 * FIX v14: Исправлена логика расчета — больше не суммируем ВСЕ дороги штата.
 * Используем средний rate per mile × реальные мили в штате × оси.
 */

const db = require('../db');

// Axle config: axles = физическое число осей
const AXLE_CONFIG = {
  '2-axle':  { axles: 2,  label: '2-Axle' },
  '3-axle':  { axles: 3,  label: '3-Axle' },
  '4-axle':  { axles: 4,  label: '4-Axle' },
  '5-axle':  { axles: 5,  label: '5-Axle' },  // стандартный 18-wheeler
  '6-axle':  { axles: 6,  label: '6-Axle' },
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
 * @param {string[]} states - штаты на маршруте
 * @param {number} distanceMiles - общая дистанция
 * @param {string} truckType - тип грузовика
 * @param {object} [stateMilesMap] - мили по штатам
 * @returns {{ total: number, breakdown: object[], states: string[] }}
 */
function calculateTollCost(states, distanceMiles, truckType = '2-axle', stateMilesMap = null) {
  const config = AXLE_CONFIG[truckType] || AXLE_CONFIG['2-axle'];
  const breakdown = [];
  let total = 0;

  for (const state of states) {
    const tolls = getTollsByState(state);
    if (tolls.length === 0) continue;

    const milesInState = (stateMilesMap && stateMilesMap[state]) ? stateMilesMap[state] : distanceMiles / states.length;

    // Средний rate per mile per axle по штату (только дороги с rate)
    const perMileTolls = tolls.filter(t => t.cost_per_axle > 0);
    if (perMileTolls.length === 0) continue;

    const avgRatePerAxle = perMileTolls.reduce((s, t) => s + t.cost_per_axle, 0) / perMileTolls.length;

    // Эвристика: какая доля миль в штате проходит по платным дорогам?
    // Больше toll roads → выше coverage, но кап 35%
    const coverageRatio = Math.min(0.35, perMileTolls.length * 0.0015 + 0.06);
    const tollMiles = milesInState * coverageRatio;

    // Основная стоимость: rate × мили × число осей
    let stateCost = avgRatePerAxle * tollMiles * config.axles;

    // Плюс вероятные bridge/flat tolls (среднее число фиксированных платежей на маршрут)
    const flatTolls = tolls.filter(t => t.min_cost > 0 && t.cost_per_axle === 0);
    if (flatTolls.length > 0) {
      // Предполагаем ~1-2 фиксированных платежа на штат в зависимости от числа дорог
      const likelyBridgeCount = Math.min(flatTolls.length, Math.ceil(milesInState / 200));
      const avgFlatCost = flatTolls.reduce((s, t) => s + t.min_cost, 0) / flatTolls.length;
      stateCost += avgFlatCost * likelyBridgeCount;
    }

    total += stateCost;

    breakdown.push({
      state,
      roads: tolls.length,
      miles_in_state: Math.round(milesInState),
      toll_miles: Math.round(tollMiles),
      cost: parseFloat(stateCost.toFixed(2)),
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
