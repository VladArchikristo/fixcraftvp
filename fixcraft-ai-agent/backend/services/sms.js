const twilio = require('twilio');

const client = twilio(process.env.TWILIO_ACCOUNT_SID, process.env.TWILIO_AUTH_TOKEN);
const FROM_NUMBER = process.env.TWILIO_PHONE_NUMBER;

async function sendConfirmationSMS({ to, name, date, timeSlot, serviceType }) {
  const timeMap = {
    morning: '8:00 AM – 12:00 PM',
    afternoon: '12:00 PM – 4:00 PM',
    evening: '4:00 PM – 7:00 PM',
  };
  const time = timeMap[timeSlot] || timeMap.morning;

  const body = `Hi ${name}! Your FixCraft VP appointment is confirmed for ${date} (${time}). Service: ${serviceType.replace('_', ' ')}. We'll call you 30 min before arrival. Questions? Reply here or call ${process.env.BUSINESS_PHONE || '(980) 201-6705'}. — Alex`;

  try {
    const message = await client.messages.create({
      body,
      from: FROM_NUMBER,
      to,
    });
    console.log('SMS sent:', message.sid);
    return { success: true, sid: message.sid };
  } catch (err) {
    console.error('SMS send error:', err.message);
    return { success: false, error: err.message };
  }
}

async function sendReminderSMS({ to, name, date, timeSlot }) {
  const timeMap = {
    morning: '8:00 AM – 12:00 PM',
    afternoon: '12:00 PM – 4:00 PM',
    evening: '4:00 PM – 7:00 PM',
  };
  const time = timeMap[timeSlot] || timeMap.morning;

  const body = `Reminder: Hi ${name}, your FixCraft VP appointment is tomorrow ${date} (${time}). We'll call 30 min before arrival. Need to reschedule? Reply CALL ME. — Alex`;

  try {
    const message = await client.messages.create({
      body,
      from: FROM_NUMBER,
      to,
    });
    return { success: true, sid: message.sid };
  } catch (err) {
    console.error('Reminder SMS error:', err.message);
    return { success: false, error: err.message };
  }
}

module.exports = { sendConfirmationSMS, sendReminderSMS };
