async function sendTelegramNotification({ name, phone, serviceType, date, timeSlot, source = 'chat' }) {
  const token = process.env.TELEGRAM_BOT_TOKEN;
  const chatId = process.env.TELEGRAM_CHAT_ID || '-1003904636267';
  if (!token) return { success: false, error: 'No TELEGRAM_BOT_TOKEN' };

  const timeMap = {
    morning: '8:00 AM – 12:00 PM',
    afternoon: '12:00 PM – 4:00 PM',
    evening: '4:00 PM – 7:00 PM',
  };
  const time = timeMap[timeSlot] || timeMap.morning;

  const text = `🚨 *New FixCraft VP Booking*

*👤 Client:* ${name}
*📞 Phone:* ${phone}
*🔧 Service:* ${serviceType.replace('_', ' ')}
*📅 Date:* ${date}
*⏰ Time:* ${time}
*📡 Source:* ${source}

✅ Auto-confirmed via Alex AI
`;

  try {
    const res = await fetch(`https://api.telegram.org/bot${token}/sendMessage`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ chat_id: chatId, text, parse_mode: 'Markdown' }),
    });
    const data = await res.json();
    return { success: data.ok, result: data };
  } catch (err) {
    console.error('Telegram notify error:', err.message);
    return { success: false, error: err.message };
  }
}

module.exports = { sendTelegramNotification };
