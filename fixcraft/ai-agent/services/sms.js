const twilio = require('twilio');

const accountSid = process.env.TWILIO_ACCOUNT_SID;
const authToken = process.env.TWILIO_AUTH_TOKEN;
const fromNumber = process.env.TWILIO_PHONE_NUMBER;

const client = twilio(accountSid, authToken);

async function sendSMS(lead) {
  const { name, phone, serviceType, date, timeSlot } = lead;

  if (!phone || phone === 'N/A') {
    return { success: false, error: 'No phone number' };
  }

  const body = `Hi ${name || 'there'}! FixCraft VP received your request for ${serviceType || 'handyman services'}. We'll confirm your inspection for ${date || 'soon'} ${timeSlot || ''}. Questions? Call (980) 485-5899.`;

  try {
    const message = await client.messages.create({
      body,
      messagingServiceSid: 'MG249a5e27a8032fb82323098bd45c41a6',
      to: phone,
    });
    return { success: true, sid: message.sid };
  } catch (err) {
    console.error('SMS send error:', err.message);
    return { success: false, error: err.message };
  }
}

module.exports = { sendSMS };
