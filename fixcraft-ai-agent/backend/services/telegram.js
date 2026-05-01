async function sendTelegramNotification(lead) {
  const token = process.env.TELEGRAM_BOT_TOKEN;
  const chatId = process.env.TELEGRAM_CHAT_ID || '-1003904636267';
  if (!token) return { success: false, error: 'No TELEGRAM_BOT_TOKEN' };

  const { name, phone, serviceType, date, timeSlot, address, urgency, notes, source = 'chat', id } = lead;

  // Smart time parsing
  let time;
  const lower = (timeSlot || '').toLowerCase().trim();
  if (!timeSlot) {
    time = 'Not specified';
  } else if (lower.includes('8') || lower.includes('9') || lower.includes('10') || lower.includes('11') || lower.includes(':') || lower.includes('am') || lower.includes('pm')) {
    time = timeSlot;
  } else if (lower.includes('morning') || lower.includes('утром')) {
    time = '8:00 AM – 11:00 AM';
  } else if (lower.includes('noon') || lower.includes('midday') || lower.includes('обед')) {
    time = '11:00 AM – 2:00 PM';
  } else if (lower.includes('afternoon') || lower.includes('после обеда')) {
    time = '12:00 PM – 4:00 PM';
  } else if (lower.includes('evening') || lower.includes('вечер')) {
    time = '4:00 PM – 6:00 PM';
  } else {
    time = timeSlot;
  }

  const publicUrl = process.env.PUBLIC_URL || process.env.NGROK_URL || '';
  const calendarLink = publicUrl ? `${publicUrl}/calendar-event/${id}` : '';

  let text = `🚨 *New FixCraft VP Lead*

*📡 Source:* ${source}
*👤 Client:* ${name || 'N/A'}
*📞 Phone:* ${phone || 'N/A'}`;

  if (address) text += `\n*📍 Address:* ${address}`;
  if (serviceType) text += `\n*🔧 Service:* ${serviceType.replace(/_/g, ' ')}`;
  if (date) text += `\n*📅 Date:* ${date}`;
  if (timeSlot) text += `\n*⏰ Time:* ${time}`;
  if (urgency) text += `\n*⚠️ Urgency:* ${urgency}`;
  if (notes) text += `\n*📝 Notes:* ${notes}`;
  if (calendarLink) text += `\n\n[📎 Add to Calendar](${calendarLink})`;

  text += '\n\n✅ Captured by Alex AI';

  try {
    // Send text message
    const resMsg = await fetch(`https://api.telegram.org/bot${token}/sendMessage`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ chat_id: chatId, text, parse_mode: 'Markdown' }),
    });
    const dataMsg = await resMsg.json();

    // Also send .ics file as document if we have lead id
    if (id) {
      const { generateICS } = require('./calendar-ics');
      const { ics } = generateICS(lead);
      const formData = new FormData();
      formData.append('chat_id', chatId);
      formData.append('document', new Blob([ics], { type: 'text/calendar' }), 'fixcraft-inspection.ics');
      formData.append('caption', `📎 Calendar event for ${name || 'client'}`);

      await fetch(`https://api.telegram.org/bot${token}/sendDocument`, {
        method: 'POST',
        body: formData,
      });
    }

    return { success: dataMsg.ok, result: dataMsg };
  } catch (err) {
    console.error('Telegram notify error:', err.message);
    return { success: false, error: err.message };
  }
}

module.exports = { sendTelegramNotification };
