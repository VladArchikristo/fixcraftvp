const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

function generateICS({ name, phone, address, service_type, date, time_slot, uid }) {
  const timeMap = {
    morning: { hour: 9, minute: 0, duration: 3 },
    afternoon: { hour: 13, minute: 0, duration: 3 },
    evening: { hour: 17, minute: 0, duration: 2 },
  };
  const t = timeMap[time_slot] || timeMap.morning;

  // Build ISO timestamps
  const start = new Date(`${date}T${String(t.hour).padStart(2,'0')}:${String(t.minute).padStart(2,'0')}:00-05:00`);
  const end = new Date(start.getTime() + t.duration * 60 * 60 * 1000);

  const format = (d) => d.toISOString().replace(/[-:]/g, '').split('.')[0] + 'Z';
  const startStr = format(start);
  const endStr = format(end);
  const nowStr = format(new Date());
  const eventUid = uid || crypto.randomUUID();

  const summary = `${process.env.BUSINESS_NAME || 'FixCraft VP'} — ${service_type.replace(/_/g, ' ')}`;
  const description = `Client: ${name}\\nPhone: ${phone}\\nAddress: ${address || 'TBD'}\\nService: ${service_type}`;

  const icsContent = `BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//FixCraft VP//AI Agent//EN
CALSCALE:GREGORIAN
METHOD:PUBLISH
BEGIN:VEVENT
UID:${eventUid}@fixcraftvp.com
DTSTAMP:${nowStr}
DTSTART:${startStr}
DTEND:${endStr}
SUMMARY:${summary}
DESCRIPTION:${description}
LOCATION:${address || 'Charlotte, NC'}
STATUS:CONFIRMED
SEQUENCE:0
BEGIN:VALARM
ACTION:DISPLAY
DESCRIPTION:FixCraft VP Appointment
TRIGGER:-PT15M
END:VALARM
END:VEVENT
END:VCALENDAR`;

  const fileName = `fixcraft-${eventUid}.ics`;
  const filePath = path.join('/tmp', fileName);
  fs.writeFileSync(filePath, icsContent);

  return { filePath, fileName, start, end, eventUid };
}

module.exports = { generateICS };
