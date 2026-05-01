const { getDB } = require('./db');

function escapeICS(str) {
  if (!str) return '';
  return String(str)
    .replace(/\\/g, '\\\\')
    .replace(/;/g, '\\;')
    .replace(/,/g, '\\,')
    .replace(/\n/g, '\\n')
    .replace(/\r/g, '');
}

function parseDateTime(dateStr, timeSlot) {
  let startHour = 9, startMin = 0;
  let endHour = 10, endMin = 0;

  if (timeSlot) {
    const m = timeSlot.match(/(\d{1,2}):(\d{2})\s*(AM|PM)?/i);
    if (m) {
      let h = parseInt(m[1], 10);
      const min = parseInt(m[2], 10);
      const ampm = m[3]?.toUpperCase();
      if (ampm === 'PM' && h !== 12) h += 12;
      if (ampm === 'AM' && h === 12) h = 0;
      startHour = h; startMin = min;
      endHour = (h + 1) % 24; endMin = min;
    }
  }

  const pad = (n) => String(n).padStart(2, '0');
  const start = `${dateStr.replace(/-/g, '')}T${pad(startHour)}${pad(startMin)}00`;
  const end = `${dateStr.replace(/-/g, '')}T${pad(endHour)}${pad(endMin)}00`;
  return { start, end };
}

function generateICS(lead) {
  const { id, name, phone, serviceType, date, timeSlot, address, notes } = lead;
  const leadId = id || 0;
  const { start, end } = parseDateTime(date || new Date().toISOString().split('T')[0], timeSlot);
  const now = new Date().toISOString().replace(/[-:]/g, '').split('.')[0] + 'Z';
  const uid = `fixcraft-lead-${leadId}-${Date.now()}@fixcraftvp.com`;

  const ics = `BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//FixCraft VP//EN
CALSCALE:GREGORIAN
METHOD:REQUEST
BEGIN:VTIMEZONE
TZID:America/New_York
BEGIN:DAYLIGHT
DTSTART:19700308T020000
RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=2SU
TZOFFSETFROM:-0500
TZOFFSETTO:-0400
END:DAYLIGHT
BEGIN:STANDARD
DTSTART:19701101T020000
RRULE:FREQ=YEARLY;BYMONTH=11;BYDAY=1SU
TZOFFSETFROM:-0400
TZOFFSETTO:-0500
END:STANDARD
END:VTIMEZONE
BEGIN:VEVENT
UID:${uid}
DTSTAMP:${now}
CREATED:${now}
LAST-MODIFIED:${now}
DTSTART;TZID=America/New_York:${start}
DTEND;TZID=America/New_York:${end}
SUMMARY:FixCraft Inspection - ${escapeICS(name || 'Client')}
DESCRIPTION:Service: ${escapeICS(serviceType || 'TBD')}\\nPhone: ${escapeICS(phone || 'N/A')}\\nNotes: ${escapeICS(notes || 'None')}
LOCATION:${escapeICS(address || 'Charlotte, NC')}
STATUS:CONFIRMED
SEQUENCE:0
ORGANIZER:CN=FixCraft VP:mailto:fixcraftvp@gmail.com
ATTENDEE;ROLE=REQ-PARTICIPANT;RSVP=TRUE:mailto:fixcraftvp@gmail.com
END:VEVENT
END:VCALENDAR`;

  return { ics, uid };
}

async function getLeadICS(req, res) {
  const db = getDB();
  db.get('SELECT * FROM leads WHERE id = ?', [req.params.id], (err, row) => {
    if (err || !row) return res.status(404).send('Event not found');

    const lead = {
      id: row.id,
      name: row.name,
      phone: row.phone,
      serviceType: row.service_type,
      date: row.requested_date || row.preferred_date,
      timeSlot: row.requested_time || row.preferred_time,
      address: row.address,
      notes: row.notes,
    };

    const { ics } = generateICS(lead);
    res.set('Content-Type', 'text/calendar; charset=utf-8');
    res.set('Content-Disposition', 'inline; filename="fixcraft-inspection.ics"');
    res.send(ics);
  });
}

// HTML page with "Add to Calendar" button for mobile browsers
async function getCalendarPage(req, res) {
  const db = getDB();
  db.get('SELECT * FROM leads WHERE id = ?', [req.params.id], (err, row) => {
    if (err || !row) return res.status(404).send('Event not found');

    const lead = {
      id: row.id,
      name: row.name || 'Client',
      phone: row.phone || 'N/A',
      serviceType: row.service_type || 'TBD',
      date: row.requested_date || row.preferred_date || 'TBD',
      timeSlot: row.requested_time || row.preferred_time || '',
      address: row.address || 'Charlotte, NC',
      notes: row.notes || '',
    };

    const icsUrl = `${req.protocol}://${req.get('host')}/calendar-event/${lead.id}.ics`;
    const webcalUrl = icsUrl.replace(/^https?:/, 'webcal:');

    const html = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>FixCraft VP - Calendar Event</title>
<style>
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;background:#f5f5f5;margin:0;padding:20px;display:flex;justify-content:center;align-items:center;min-height:100vh}
.card{background:#fff;border-radius:16px;padding:24px;max-width:380px;width:100%;box-shadow:0 4px 20px rgba(0,0,0,.1)}
.header{text-align:center;margin-bottom:20px}
.logo{font-size:32px;margin-bottom:8px}
h1{margin:0;font-size:22px;color:#1a1a1a}
.subtitle{color:#666;font-size:14px;margin-top:4px}
.details{margin:20px 0}
.detail{display:flex;justify-content:space-between;padding:10px 0;border-bottom:1px solid #eee}
.detail:last-child{border-bottom:none}
.label{color:#666;font-size:13px}
.value{color:#1a1a1a;font-size:14px;font-weight:500}
.btn{display:block;width:100%;padding:16px;border:none;border-radius:12px;font-size:16px;font-weight:600;text-align:center;text-decoration:none;margin:8px 0;cursor:pointer}
.btn-primary{background:#007AFF;color:#fff}
.btn-secondary{background:#34C759;color:#fff}
.btn-outline{background:#fff;color:#007AFF;border:2px solid #007AFF}
.footer{text-align:center;margin-top:16px;font-size:12px;color:#999}
</style>
</head>
<body>
<div class="card">
  <div class="header">
    <div class="logo">🔧</div>
    <h1>FixCraft VP</h1>
    <div class="subtitle">Inspection Appointment</div>
  </div>
  <div class="details">
    <div class="detail"><span class="label">Client</span><span class="value">${lead.name}</span></div>
    <div class="detail"><span class="label">Service</span><span class="value">${lead.serviceType}</span></div>
    <div class="detail"><span class="label">Date</span><span class="value">${lead.date}</span></div>
    <div class="detail"><span class="label">Time</span><span class="value">${lead.timeSlot}</span></div>
    <div class="detail"><span class="label">Address</span><span class="value">${lead.address}</span></div>
    ${lead.notes ? `<div class="detail"><span class="label">Notes</span><span class="value">${lead.notes}</span></div>` : ''}
  </div>
  <a href="${webcalUrl}" class="btn btn-primary">📅 Add to Calendar (iOS)</a>
  <a href="${icsUrl}" class="btn btn-secondary">📅 Add to Calendar (Android)</a>
  <a href="${icsUrl}" download="fixcraft-inspection.ics" class="btn btn-outline">📥 Download .ics File</a>
  <div class="footer">FixCraft VP | (980) 485-5899</div>
</div>
</body>
</html>`;

    res.send(html);
  });
}

module.exports = { generateICS, getLeadICS, getCalendarPage };
