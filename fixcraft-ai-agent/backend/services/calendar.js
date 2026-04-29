const { google } = require('googleapis');

const auth = new google.auth.GoogleAuth({
  credentials: {
    client_email: process.env.GOOGLE_CLIENT_EMAIL,
    private_key: process.env.GOOGLE_PRIVATE_KEY.replace(/\\n/g, '\n'),
  },
  scopes: ['https://www.googleapis.com/auth/calendar'],
});

const calendar = google.calendar({ version: 'v3', auth });
const CALENDAR_ID = process.env.GOOGLE_CALENDAR_ID;

async function createEvent({ name, phone, address, service_type, date, time_slot }) {
  const timeMap = {
    morning: { hour: 9, minute: 0, duration: 3 },
    afternoon: { hour: 13, minute: 0, duration: 3 },
    evening: { hour: 17, minute: 0, duration: 2 },
  };
  const t = timeMap[time_slot] || timeMap.morning;

  const startDate = new Date(`${date}T${String(t.hour).padStart(2,'0')}:${String(t.minute).padStart(2,'0')}:00-05:00`);
  const endDate = new Date(startDate.getTime() + t.duration * 60 * 60 * 1000);

  const event = {
    summary: `${process.env.BUSINESS_NAME || 'FixCraft'} — ${service_type.replace('_', ' ')}`,
    description: `Client: ${name}\nPhone: ${phone}\nAddress: ${address || 'TBD'}\nService: ${service_type}`,
    start: { dateTime: startDate.toISOString(), timeZone: 'America/New_York' },
    end: { dateTime: endDate.toISOString(), timeZone: 'America/New_York' },
  };

  const res = await calendar.events.insert({ calendarId: CALENDAR_ID, requestBody: event });
  return res.data;
}

module.exports = { createEvent };
