const nodemailer = require('nodemailer');
const { generateICS } = require('./calendar-ics');

const transporter = nodemailer.createTransport({
  service: 'gmail',
  auth: {
    user: 'fixcraftvp@gmail.com',
    pass: 'iulc yaue phss fnam', // App Password
  },
});

async function sendEmailNotification(lead) {
  const { name, phone, serviceType, date, timeSlot, address, urgency, notes } = lead;

  const { ics } = generateICS(lead);

  const subject = `🚨 New FixCraft VP Lead — ${name || 'Unknown'}`;
  const body = `
New lead captured by Alex AI:

Name: ${name || 'N/A'}
Phone: ${phone || 'N/A'}
Service: ${serviceType || 'N/A'}
Date: ${date || 'Not specified'}
Time: ${timeSlot || 'Not specified'}
Address: ${address || 'Not specified'}
Urgency: ${urgency || 'Not specified'}
Notes: ${notes || 'None'}

📎 Add to calendar: see attached .ics file
— FixCraft VP AI Agent
`;

  try {
    await transporter.sendMail({
      from: '"FixCraft VP" <fixcraftvp@gmail.com>',
      to: 'fixcraftvp@gmail.com',
      subject,
      text: body,
      attachments: [
        {
          filename: 'fixcraft-inspection.ics',
          content: ics,
          contentType: 'text/calendar; charset=utf-8',
        },
      ],
    });
    return { success: true };
  } catch (err) {
    console.error('Email send error:', err.message);
    return { success: false, error: err.message };
  }
}

module.exports = { sendEmailNotification };
