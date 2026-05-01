const { google } = require('googleapis');

const SCOPES = ['https://www.googleapis.com/auth/calendar'];

function getAuth() {
  const privateKey = process.env.GOOGLE_PRIVATE_KEY?.replace(/\\n/g, '\n');
  const clientEmail = process.env.GOOGLE_CLIENT_EMAIL;
  
  if (!privateKey || privateKey === 'placeholder') {
    throw new Error('Google Calendar private key not configured');
  }
  
  return new google.auth.JWT(clientEmail, null, privateKey, SCOPES);
}

async function createInspectionEvent({ name, phone, serviceType, date, timeSlot, notes }) {
  try {
    const auth = getAuth();
    const calendar = google.calendar({ version: 'v3', auth });
    
    const calendarId = process.env.GOOGLE_CALENDAR_ID || 'primary';
    
    // Parse date (expects YYYY-MM-DD)
    // Parse time — if specific time like "9:00 AM", use it. Otherwise default to 9 AM.
    let startTime = '09:00:00';
    let endTime = '10:00:00';
    
    if (timeSlot && timeSlot.includes(':')) {
      // Try to parse "9:00 AM" or "14:30"
      const match = timeSlot.match(/(\d{1,2}):(\d{2})\s*(AM|PM)?/i);
      if (match) {
        let hour = parseInt(match[1], 10);
        const min = match[2];
        const ampm = match[3]?.toUpperCase();
        if (ampm === 'PM' && hour !== 12) hour += 12;
        if (ampm === 'AM' && hour === 12) hour = 0;
        startTime = `${String(hour).padStart(2, '0')}:${min}:00`;
        // 1-hour inspection slot
        const endHour = (hour + 1) % 24;
        endTime = `${String(endHour).padStart(2, '0')}:${min}:00`;
      }
    }
    
    const startDateTime = `${date}T${startTime}-04:00`; // Charlotte EDT
    const endDateTime = `${date}T${endTime}-04:00`;
    
    const event = {
      summary: `🔧 FixCraft Inspection — ${name || 'Client'}`,
      description: `Service: ${serviceType || 'TBD'}\nPhone: ${phone || 'N/A'}\nNotes: ${notes || 'None'}`,
      start: { dateTime: startDateTime, timeZone: 'America/New_York' },
      end: { dateTime: endDateTime, timeZone: 'America/New_York' },
      reminders: {
        useDefault: false,
        overrides: [
          { method: 'email', minutes: 60 },
          { method: 'popup', minutes: 30 },
        ],
      },
    };
    
    const res = await calendar.events.insert({ calendarId, requestBody: event });
    return { success: true, eventId: res.data.id, link: res.data.htmlLink };
  } catch (err) {
    console.error('Calendar create error:', err.message);
    return { success: false, error: err.message };
  }
}

module.exports = { createInspectionEvent };
