/**
 * IFTA Quarterly Calculator
 * Утилиты для расчёта IFTA отчёта на клиенте и генерации PDF.
 *
 * Основной расчёт выполняется на сервере (/api/trips/ifta),
 * этот модуль предоставляет вспомогательные функции:
 * - фильтрация поездок по кварталу (клиентская)
 * - генерация HTML для expo-print
 */

// IFTA ставки ($ per gallon, 2026) — дублируем с бэкенда для офлайн PDF
export const IFTA_TAX_RATES = {
  TX: 0.20, OK: 0.16, KS: 0.26, MO: 0.17, IL: 0.455,
  IN: 0.33, OH: 0.28, PA: 0.741, NY: 0.398, NJ: 0.175,
  VA: 0.162, NC: 0.361, TN: 0.17, GA: 0.326, FL: 0.359,
  AL: 0.19, MS: 0.18, AR: 0.225, LA: 0.20, CA: 0.824,
  AZ: 0.26, NV: 0.27, UT: 0.249, CO: 0.205, NM: 0.21,
  WY: 0.24, MT: 0.2775, ID: 0.32, WA: 0.494, OR: 0.34,
  AK: 0.0895, CT: 0.401, DE: 0.220, IA: 0.325, KY: 0.216,
  ME: 0.319, MD: 0.358, MA: 0.240, MI: 0.470, MN: 0.285,
  NE: 0.278, NH: 0.222, ND: 0.230, RI: 0.340, SC: 0.220,
  SD: 0.280, VT: 0.320, WV: 0.358, WI: 0.329,
};

/**
 * Возвращает start/end даты для квартала.
 * @param {number} quarter 1-4
 * @param {number} year
 * @returns {{ start: Date, end: Date }}
 */
export function getQuarterDates(quarter, year) {
  const startMonth = (quarter - 1) * 3; // 0, 3, 6, 9
  const start = new Date(year, startMonth, 1);
  const end = new Date(year, startMonth + 3, 0, 23, 59, 59); // последний день квартала
  return { start, end };
}

/**
 * Фильтрует массив поездок по кварталу и году.
 * Поездка должна иметь поле `created_at` или `quarter`+`year`.
 * @param {Array} trips
 * @param {number} quarter 1-4
 * @param {number} year
 * @returns {Array}
 */
export function filterTripsByQuarter(trips, quarter, year) {
  return trips.filter((trip) => {
    // Если бэкенд уже проставил quarter/year — используем их
    if (trip.quarter !== undefined && trip.year !== undefined) {
      return trip.quarter === quarter && trip.year === year;
    }
    // Иначе парсим дату
    if (trip.created_at) {
      const d = new Date(trip.created_at);
      const tripQuarter = Math.ceil((d.getMonth() + 1) / 3);
      return tripQuarter === quarter && d.getFullYear() === year;
    }
    return false;
  });
}

/**
 * Агрегирует мили по штатам из массива поездок.
 * @param {Array} trips — у каждой поездки state_miles: { TX: 200, OK: 100 }
 * @returns {{ [state: string]: number }}
 */
export function aggregateStateMiles(trips) {
  const result = {};
  trips.forEach((trip) => {
    const sm = trip.state_miles || {};
    Object.entries(sm).forEach(([state, miles]) => {
      result[state] = (result[state] || 0) + parseFloat(miles || 0);
    });
  });
  return result;
}

/**
 * Рассчитывает IFTA отчёт по клиентским данным (для офлайн-режима).
 * @param {Object} stateMiles { TX: 450, OK: 200 }
 * @param {number} mpg средний MPG
 * @param {Object} purchasedByState { TX: 30 } галлоны купленные в каждом штате
 * @returns {Array} массив строк отчёта
 */
export function calculateIFTAReport(stateMiles, mpg = 6.5, purchasedByState = {}) {
  return Object.entries(stateMiles)
    .map(([state, total_miles]) => {
      const consumed_gallons = total_miles / mpg;
      const purchased_gallons = purchasedByState[state] || 0;
      const net_gallons = consumed_gallons - purchased_gallons;
      const tax_rate = IFTA_TAX_RATES[state] || 0;
      const tax_due = net_gallons * tax_rate;
      return {
        state,
        total_miles: parseFloat(total_miles.toFixed(2)),
        consumed_gallons: parseFloat(consumed_gallons.toFixed(3)),
        purchased_gallons: parseFloat(purchased_gallons.toFixed(3)),
        net_gallons: parseFloat(net_gallons.toFixed(3)),
        tax_rate,
        tax_due: parseFloat(tax_due.toFixed(4)),
        refund: tax_due < 0,
      };
    })
    .sort((a, b) => a.state.localeCompare(b.state));
}

/**
 * Полное название штата по аббревиатуре
 */
const STATE_NAMES = {
  AL: 'Alabama', AK: 'Alaska', AZ: 'Arizona', AR: 'Arkansas', CA: 'California',
  CO: 'Colorado', CT: 'Connecticut', DE: 'Delaware', FL: 'Florida', GA: 'Georgia',
  ID: 'Idaho', IL: 'Illinois', IN: 'Indiana', IA: 'Iowa', KS: 'Kansas',
  KY: 'Kentucky', LA: 'Louisiana', ME: 'Maine', MD: 'Maryland', MA: 'Massachusetts',
  MI: 'Michigan', MN: 'Minnesota', MS: 'Mississippi', MO: 'Missouri', MT: 'Montana',
  NE: 'Nebraska', NV: 'Nevada', NH: 'New Hampshire', NJ: 'New Jersey', NM: 'New Mexico',
  NY: 'New York', NC: 'North Carolina', ND: 'North Dakota', OH: 'Ohio', OK: 'Oklahoma',
  OR: 'Oregon', PA: 'Pennsylvania', RI: 'Rhode Island', SC: 'South Carolina',
  SD: 'South Dakota', TN: 'Tennessee', TX: 'Texas', UT: 'Utah', VT: 'Vermont',
  VA: 'Virginia', WA: 'Washington', WV: 'West Virginia', WI: 'Wisconsin', WY: 'Wyoming',
};

/**
 * Генерирует HTML строку для expo-print (официальный формат IFTA).
 * @param {Object} reportData — данные из /api/trips/ifta или calculateIFTAReport
 * @param {Object} driverInfo { name, company, usdot }
 * @returns {string} HTML
 */
export function generateIFTAPDF(reportData, driverInfo = {}) {
  const { quarter, year, total_miles = 0, avg_mpg = 0, total_trips = 0,
    states = [], total_tax_due = 0 } = reportData;

  const driverName = driverInfo.name || 'Owner-Operator';
  const companyName = driverInfo.company || '';
  const usdot = driverInfo.usdot || '';
  const isRefund = total_tax_due < 0;

  const stateRows = states.map((s) => {
    const stateName = STATE_NAMES[s.state] || s.state;
    const netColor = s.tax_due >= 0 ? '#c62828' : '#2e7d32';
    const netSign = s.tax_due >= 0 ? '' : '-';
    return `
      <tr>
        <td>${s.state}</td>
        <td>${stateName}</td>
        <td class="num">${s.total_miles.toFixed(1)}</td>
        <td class="num">${s.consumed_gallons.toFixed(3)}</td>
        <td class="num">${s.purchased_gallons > 0 ? s.purchased_gallons.toFixed(3) : '0.000'}</td>
        <td class="num">${s.net_gallons.toFixed(3)}</td>
        <td class="num">$${s.tax_rate.toFixed(4)}</td>
        <td class="num" style="color:${netColor};font-weight:700">
          ${netSign}$${Math.abs(s.tax_due).toFixed(2)}
        </td>
      </tr>`;
  }).join('');

  const totalColor = isRefund ? '#2e7d32' : '#c62828';
  const totalLabel = isRefund ? 'CREDIT (REFUND)' : 'TAX DUE';
  const totalSign = isRefund ? '-' : '';
  const generatedDate = new Date().toLocaleDateString('en-US', {
    month: 'long', day: 'numeric', year: 'numeric',
  });

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>IFTA Quarterly Report Q${quarter} ${year}</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
      font-family: Arial, Helvetica, sans-serif;
      font-size: 11px;
      color: #1a1a1a;
      padding: 24px 32px;
      background: #fff;
    }
    /* Header */
    .header {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      border-bottom: 3px solid #1565c0;
      padding-bottom: 12px;
      margin-bottom: 16px;
    }
    .header-title { }
    .header-title h1 {
      font-size: 18px;
      font-weight: 900;
      color: #1565c0;
      letter-spacing: 0.5px;
      text-transform: uppercase;
    }
    .header-title p {
      font-size: 12px;
      color: #555;
      margin-top: 2px;
    }
    .header-quarter {
      text-align: right;
    }
    .header-quarter .quarter-badge {
      background: #1565c0;
      color: #fff;
      font-size: 22px;
      font-weight: 900;
      padding: 6px 18px;
      border-radius: 6px;
    }
    .header-quarter .year-text {
      color: #555;
      font-size: 13px;
      margin-top: 4px;
      text-align: center;
    }

    /* Driver info */
    .driver-section {
      display: flex;
      gap: 24px;
      background: #f5f5f5;
      border: 1px solid #ddd;
      border-radius: 6px;
      padding: 12px 16px;
      margin-bottom: 16px;
    }
    .driver-field { flex: 1; }
    .driver-field label {
      font-size: 9px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      color: #888;
      display: block;
      margin-bottom: 2px;
    }
    .driver-field span {
      font-size: 12px;
      font-weight: 700;
      color: #1a1a1a;
    }

    /* Summary */
    .summary {
      display: flex;
      gap: 12px;
      margin-bottom: 16px;
    }
    .summary-card {
      flex: 1;
      border: 1px solid #ddd;
      border-radius: 6px;
      padding: 10px 14px;
      text-align: center;
    }
    .summary-card .val {
      font-size: 20px;
      font-weight: 900;
      color: #1565c0;
    }
    .summary-card .lbl {
      font-size: 9px;
      text-transform: uppercase;
      color: #888;
      margin-top: 2px;
    }

    /* Table */
    .section-title {
      font-size: 10px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      color: #888;
      font-weight: 700;
      margin-bottom: 8px;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      margin-bottom: 16px;
    }
    thead tr {
      background: #1565c0;
      color: #fff;
    }
    thead th {
      padding: 8px 10px;
      text-align: left;
      font-size: 10px;
      text-transform: uppercase;
      letter-spacing: 0.3px;
      font-weight: 700;
    }
    thead th.num { text-align: right; }
    tbody tr:nth-child(even) { background: #f9f9f9; }
    tbody tr:hover { background: #e3f2fd; }
    tbody td {
      padding: 7px 10px;
      border-bottom: 1px solid #eee;
      font-size: 11px;
    }
    tbody td.num { text-align: right; }
    tfoot tr {
      background: #e8eaf6;
      font-weight: 900;
    }
    tfoot td {
      padding: 9px 10px;
      font-size: 12px;
      border-top: 2px solid #1565c0;
    }
    tfoot td.num { text-align: right; }

    /* Total due */
    .total-box {
      border: 2px solid ${totalColor};
      border-radius: 8px;
      padding: 16px 24px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      background: ${isRefund ? '#f1f8e9' : '#ffebee'};
      margin-bottom: 20px;
    }
    .total-box .total-label {
      font-size: 14px;
      font-weight: 900;
      text-transform: uppercase;
      color: ${totalColor};
      letter-spacing: 1px;
    }
    .total-box .total-amount {
      font-size: 32px;
      font-weight: 900;
      color: ${totalColor};
    }

    /* Footer */
    .footer {
      border-top: 1px solid #ddd;
      padding-top: 10px;
      display: flex;
      justify-content: space-between;
      color: #aaa;
      font-size: 9px;
    }

    /* Empty state */
    .empty-notice {
      text-align: center;
      padding: 40px;
      color: #888;
      font-size: 14px;
      border: 1px dashed #ccc;
      border-radius: 8px;
    }
  </style>
</head>
<body>

  <!-- Header -->
  <div class="header">
    <div class="header-title">
      <h1>IFTA Quarterly Fuel Tax Report</h1>
      <p>International Fuel Tax Agreement</p>
    </div>
    <div class="header-quarter">
      <div class="quarter-badge">Q${quarter}</div>
      <div class="year-text">${year}</div>
    </div>
  </div>

  <!-- Driver Info -->
  <div class="driver-section">
    <div class="driver-field">
      <label>Driver / Carrier</label>
      <span>${driverName}</span>
    </div>
    ${companyName ? `
    <div class="driver-field">
      <label>Company</label>
      <span>${companyName}</span>
    </div>` : ''}
    ${usdot ? `
    <div class="driver-field">
      <label>USDOT #</label>
      <span>${usdot}</span>
    </div>` : ''}
    <div class="driver-field">
      <label>Reporting Period</label>
      <span>Q${quarter} ${year} (${getQuarterPeriodLabel(quarter, year)})</span>
    </div>
  </div>

  <!-- Summary -->
  <div class="summary">
    <div class="summary-card">
      <div class="val">${total_trips}</div>
      <div class="lbl">Trips</div>
    </div>
    <div class="summary-card">
      <div class="val">${parseFloat(total_miles).toFixed(0)}</div>
      <div class="lbl">Total Miles</div>
    </div>
    <div class="summary-card">
      <div class="val">${states.length}</div>
      <div class="lbl">Jurisdictions</div>
    </div>
    <div class="summary-card">
      <div class="val">${parseFloat(avg_mpg || 0).toFixed(2)}</div>
      <div class="lbl">Avg MPG</div>
    </div>
    <div class="summary-card">
      <div class="val" style="color:${totalColor}">
        ${totalSign}$${Math.abs(total_tax_due).toFixed(2)}
      </div>
      <div class="lbl">${totalLabel}</div>
    </div>
  </div>

  <!-- Jurisdiction Table -->
  <div class="section-title">Jurisdiction Breakdown</div>

  ${states.length > 0 ? `
  <table>
    <thead>
      <tr>
        <th>St.</th>
        <th>Jurisdiction</th>
        <th class="num">Total Miles</th>
        <th class="num">Consumed Gal</th>
        <th class="num">Purchased Gal</th>
        <th class="num">Net Gallons</th>
        <th class="num">Tax Rate</th>
        <th class="num">Tax Due / Credit</th>
      </tr>
    </thead>
    <tbody>
      ${stateRows}
    </tbody>
    <tfoot>
      <tr>
        <td colspan="2"><strong>TOTAL</strong></td>
        <td class="num"><strong>${parseFloat(total_miles).toFixed(1)}</strong></td>
        <td class="num"></td>
        <td class="num"></td>
        <td class="num"></td>
        <td class="num"></td>
        <td class="num" style="color:${totalColor}">
          <strong>${totalSign}$${Math.abs(total_tax_due).toFixed(2)}</strong>
        </td>
      </tr>
    </tfoot>
  </table>

  <!-- Total Due Box -->
  <div class="total-box">
    <div class="total-label">${totalLabel}</div>
    <div class="total-amount">${totalSign}$${Math.abs(total_tax_due).toFixed(2)}</div>
  </div>
  ` : `
  <div class="empty-notice">
    No trip data found for Q${quarter} ${year}.<br/>
    Complete trips will appear here once recorded.
  </div>
  `}

  <!-- Footer -->
  <div class="footer">
    <span>Generated by Toll Navigator • ${generatedDate}</span>
    <span>This report is for informational purposes. Verify with your IFTA jurisdiction.</span>
  </div>

</body>
</html>`;
}

/**
 * Вспомогательная: человекочитаемый диапазон дат квартала
 */
function getQuarterPeriodLabel(quarter, year) {
  const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
    'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const startMonth = (quarter - 1) * 3;
  const endMonth = startMonth + 2;
  return `${MONTHS[startMonth]} 1 – ${MONTHS[endMonth]} ${getLastDay(endMonth, year)}, ${year}`;
}

function getLastDay(monthIndex, year) {
  return new Date(year, monthIndex + 1, 0).getDate();
}
