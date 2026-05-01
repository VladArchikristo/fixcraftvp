const express = require('express');
const router = express.Router();
const { chatCompletion } = require('../services/openai');
const { createEvent } = require('../services/calendar');
const { sendConfirmationSMS } = require('../services/sms');
const { sendTelegramNotification } = require('../services/telegram');
const { run, all } = require('../services/db');
const { notifyNewLead } = require('../services/notifications');

router.post('/message', async (req, res) => {
  try {
    const { sessionId, messages } = req.body;

    const lastUser = messages.filter(m => m.role === 'user').pop();
    if (lastUser) {
      await run('INSERT INTO chats (session_id, role, content) VALUES (?, ?, ?)', [sessionId, 'user', lastUser.content]);
    }

    const result = await chatCompletion(messages);

    if (result.type === 'function' && result.name === 'book_appointment') {
      const event = await createEvent(result.args);
      await run('INSERT INTO appointments (name, phone, service_type, date, time_slot, calendar_event_id) VALUES (?, ?, ?, ?, ?, ?)',
        [result.args.name, result.args.phone, result.args.service_type, result.args.date, result.args.time_slot || 'morning', event.id]);
      
      // Save as lead too
      await run('INSERT INTO leads (name, phone, address, service_type, source, status) VALUES (?, ?, ?, ?, ?, ?)',
        [result.args.name, result.args.phone, result.args.address || null, result.args.service_type, 'website-chat', 'new']);

      // Send confirmation SMS
      await sendConfirmationSMS({
        to: result.args.phone,
        name: result.args.name,
        date: result.args.date,
        serviceType: result.args.service_type,
        date: result.args.date,
        timeSlot: result.args.time_slot || 'morning',
        source: 'website-chat',
      });
      await notifyNewLead({
        name: result.args.name,
        phone: result.args.phone,
        address: result.args.address,
        serviceType: result.args.service_type,
        date: result.args.date,
        timeSlot: result.args.time_slot || 'morning',
        source: 'website-chat',
      });

      const confirmMsg = `✅ Appointment booked for ${result.args.date}! You'll receive a confirmation call from ${process.env.BUSINESS_NAME || 'FixCraft VP'}.`;
      await run('INSERT INTO chats (session_id, role, content) VALUES (?, ?, ?)', [sessionId, 'assistant', confirmMsg]);
      return res.json({ reply: confirmMsg, bookingSubmitted: true });
    }

    if (result.type === 'function' && result.name === 'transfer_to_human') {
      const msg = `I'm connecting you with ${process.env.OWNER_NAME || 'Vlad'}. He'll reach out shortly.`;
      await run('INSERT INTO chats (session_id, role, content) VALUES (?, ?, ?)', [sessionId, 'assistant', msg]);
      return res.json({ reply: msg, handoff: true });
    }

    await run('INSERT INTO chats (session_id, role, content) VALUES (?, ?, ?)', [sessionId, 'assistant', result.content]);
    return res.json({ reply: result.content });
  } catch (err) {
    console.error('Chat error:', err);
    return res.status(500).json({ error: 'Something went wrong' });
  }
});

router.get('/history/:sessionId', async (req, res) => {
  try {
    const rows = await all('SELECT role, content, created_at FROM chats WHERE session_id = ? ORDER BY id ASC', [req.params.sessionId]);
    res.json({ messages: rows });
  } catch (err) {
    res.status(500).json({ error: 'Failed to fetch history' });
  }
});

module.exports = router;
