const express = require('express');
const router = express.Router();
const { chatCompletion } = require('../services/openai');
const { createEvent } = require('../services/calendar');
const { run, all } = require('../services/db');

router.post('/incoming', async (req, res) => {
  try {
    const { From, Body } = req.body;
    const phone = From;

    await run('INSERT INTO chats (session_id, role, content) VALUES (?, ?, ?)', [phone, 'user', Body]);

    const history = await all('SELECT role, content FROM chats WHERE session_id = ? ORDER BY id DESC LIMIT 10', [phone]);
    const messages = history.reverse().map(h => ({ role: h.role, content: h.content }));

    const result = await chatCompletion(messages, phone);

    let reply = '';
    if (result.type === 'function' && result.name === 'book_appointment') {
      const event = await createEvent(result.args);
      await run('INSERT INTO appointments (name, phone, service_type, date, time_slot, calendar_event_id) VALUES (?, ?, ?, ?, ?, ?)',
        [result.args.name, result.args.phone, result.args.service_type, result.args.date, result.args.time_slot || 'morning', event.id]);
      reply = `✅ Booked! ${result.args.name}, your ${result.args.service_type.replace('_', ' ')} appointment is set for ${result.args.date}.`;
    } else if (result.type === 'function' && result.name === 'transfer_to_human') {
      reply = `I'm connecting you with ${process.env.OWNER_NAME || 'Vlad'}. He'll call you shortly at ${phone}.`;
    } else {
      reply = result.content;
    }

    await run('INSERT INTO chats (session_id, role, content) VALUES (?, ?, ?)', [phone, 'assistant', reply]);

    res.set('Content-Type', 'text/xml');
    res.send(`<Response><Message>${reply}</Message></Response>`);
  } catch (err) {
    console.error('SMS webhook error:', err);
    res.set('Content-Type', 'text/xml');
    res.send(`<Response><Message>Sorry, I'm having trouble. Please call ${process.env.BUSINESS_PHONE || '(980) 201-6705'}.</Message></Response>`);
  }
});

module.exports = router;
