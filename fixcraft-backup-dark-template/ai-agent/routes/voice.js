const express = require('express');
const router = express.Router();
const { chatCompletion } = require('../services/openai');
const { createEvent } = require('../services/calendar');
const { sendConfirmationSMS } = require('../services/sms');
const { sendTelegramNotification } = require('../services/telegram');
const { run, all } = require('../services/db');

function twimlResponse(message, gather = true, transferTo = null) {
  let xml = '<?xml version="1.0" encoding="UTF-8"?>';
  xml += '<Response>';

  if (message) {
    xml += `<Say voice="Polly.Matthew">${escapeXml(message)}</Say>`;
  }

  if (transferTo) {
    xml += `<Dial>${transferTo}</Dial>`;
  } else if (gather) {
    xml += '<Gather input="speech" action="/api/voice/incoming" method="POST" speechTimeout="3" timeout="15" language="en-US">';
    xml += '</Gather>';
    // Fallback 1: prompt again if no speech
    xml += '<Say voice="Polly.Matthew">I\'m still here. Just say TV mounting, furniture assembly, plumbing, or electrical, and I\'ll get you booked.</Say>';
    xml += '<Gather input="speech" action="/api/voice/incoming" method="POST" speechTimeout="3" timeout="15" language="en-US">';
    xml += '</Gather>';
    // Fallback 2: transfer only after second silence
    xml += '<Say voice="Polly.Matthew">I didn\'t catch that. Let me connect you with Vlad.</Say>';
    xml += `<Dial>${process.env.OWNER_PHONE || '+198****6705'}</Dial>`;
  }

  xml += '</Response>';
  return xml;
}

function hangupResponse(message) {
  let xml = '<?xml version="1.0" encoding="UTF-8"?>';
  xml += '<Response>';
  xml += `<Say voice="Polly.Matthew">${escapeXml(message)}</Say>`;
  xml += '<Hangup/>';
  xml += '</Response>';
  return xml;
}

function escapeXml(str) {
  if (!str) return '';
  return str.replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&apos;');
}

// Log call summary + notify after call ends
async function logCallSummary(phone, callSid) {
  try {
    const history = await all(
      'SELECT role, content FROM chats WHERE session_id = ? ORDER BY id',
      [phone]
    );

    // Build transcript
    const transcript = history.map(h => `${h.role}: ${h.content}`).join('\n');

    // Send to Telegram
    await sendTelegramNotification(`📞 Voice Call Ended\nFrom: ${phone}\nTranscript:\n${transcript.substring(0, 800)}`);

  } catch (err) {
    console.error('Call summary error:', err);
  }
}

// Save or update lead from conversation
async function saveLead(phone, serviceType, transcript) {
  try {
    const existing = await all('SELECT id FROM leads WHERE phone = ?', [phone]);
    if (existing.length === 0) {
      await run(
        'INSERT INTO leads (name, phone, service_type, source) VALUES (?, ?, ?, ?)',
        ['Voice Caller', phone, serviceType || 'unknown', 'voice']
      );
    }
  } catch (err) {
    console.error('Lead save error:', err);
  }
}

// --- STATUS CALLBACK: Twilio calls this when call ends ---
router.post('/status', async (req, res) => {
  const { CallSid, CallStatus, From } = req.body;
  if (CallStatus === 'completed' || CallStatus === 'busy' || CallStatus === 'no-answer') {
    await logCallSummary(From, CallSid);
  }
  res.sendStatus(200);
});

// --- MAIN WEBHOOK ---
router.post('/incoming', async (req, res) => {
  try {
    const { SpeechResult, From, CallSid } = req.body;
    const phone = From || 'unknown';

    // --- INITIAL GREETING ---
    if (!SpeechResult) {
      const greeting = `Hi! This is Alex from FixCraft VP. I can help with furniture assembly, TV mounting, plumbing, or electrical work. What do you need today?`;
      res.set('Content-Type', 'text/xml');
      return res.send(twimlResponse(greeting, true));
    }

    // Normalize speech
    const userText = SpeechResult.toLowerCase().trim();

    // --- HANDLE GOODBYE / HANGUP ---
    const goodbyeWords = ['bye', 'goodbye', 'see you', 'hang up', 'that\'s all', 'nothing else', 'no thanks', 'no thank you', 'later', 'have a good one'];
    if (goodbyeWords.some(w => userText.includes(w))) {
      res.set('Content-Type', 'text/xml');
      return res.send(hangupResponse('Got it! Thanks for calling FixCraft VP. Feel free to call back anytime. Take care!'));
    }

    // Save user speech
    await run('INSERT INTO chats (session_id, role, content) VALUES (?, ?, ?)', [phone, 'user', SpeechResult]);

    // Fetch history
    const history = await all('SELECT role, content FROM chats WHERE session_id = ? ORDER BY id DESC LIMIT 15', [phone]);
    const messages = history.reverse().map(h => ({ role: h.role, content: h.content }));

    // Get AI response
    const result = await chatCompletion(messages, phone, 'voice');

    let reply = '';
    let transfer = false;
    let hangup = false;

    if (result.type === 'function' && result.name === 'book_appointment') {
      const args = result.args;
      
      // ALWAYS save lead first
      await saveLead(phone, args.service_type, SpeechResult);

      let calendarSuccess = false;
      let calendarError = null;

      // Try calendar booking
      try {
        const event = await createEvent(args);
        await run(
          'INSERT INTO appointments (name, phone, service_type, date, time_slot, calendar_event_id, status) VALUES (?, ?, ?, ?, ?, ?, ?)',
          [args.name, args.phone, args.service_type, args.date, args.time_slot || 'morning', event.id, 'confirmed']
        );
        calendarSuccess = true;
      } catch (calErr) {
        console.error('Calendar error:', calErr.message);
        calendarError = calErr.message;
        // Still save appointment locally without calendar
        await run(
          'INSERT INTO appointments (name, phone, service_type, date, time_slot, status) VALUES (?, ?, ?, ?, ?, ?)',
          [args.name, args.phone, args.service_type, args.date, args.time_slot || 'morning', 'pending']
        );
      }

      // Try SMS separately (may fail due to A2P)
      try {
        await sendConfirmationSMS({
          to: args.phone,
          name: args.name,
          date: args.date,
          timeSlot: args.time_slot || 'morning',
          serviceType: args.service_type
        });
      } catch (smsErr) {
        console.error('SMS error (expected if A2P pending):', smsErr.message);
      }

      // Try Telegram separately
      try {
        await sendTelegramNotification(
          `📞 NEW BOOKING (Voice)\nName: ${args.name}\nPhone: ${args.phone}\nService: ${args.service_type}\nDate: ${args.date}\nTime: ${args.time_slot || 'morning'}${calendarError ? '\n⚠️ Calendar error: ' + calendarError : ''}`
        );
      } catch (tgErr) {
        console.error('Telegram error:', tgErr.message);
      }

      if (calendarSuccess) {
        reply = `Perfect! I've booked your ${args.service_type.replace(/_/g, ' ')} for ${args.date}. Need anything else?`;
      } else {
        reply = `I've got your request for ${args.service_type.replace(/_/g, ' ')} on ${args.date}. Vlad will confirm the details shortly. Anything else?`;
      }

    } else if (result.type === 'function' && result.name === 'transfer_to_human') {
      reply = `Sure thing! Connecting you with Vlad now.`;
      transfer = true;
    } else {
      reply = result.content;
      if (reply.toLowerCase().includes('goodbye') || reply.toLowerCase().includes('take care') || reply.toLowerCase().includes('have a great day')) {
        hangup = true;
      }
    }

    // Save assistant reply
    await run('INSERT INTO chats (session_id, role, content) VALUES (?, ?, ?)', [phone, 'assistant', reply]);

    res.set('Content-Type', 'text/xml');

    if (hangup) {
      return res.send(hangupResponse(reply));
    }
    if (transfer) {
      return res.send(twimlResponse(reply, false, process.env.OWNER_PHONE || '+19802016705'));
    }

    return res.send(twimlResponse(reply, true));

  } catch (err) {
    console.error('Voice webhook error:', err);
    res.set('Content-Type', 'text/xml');
    res.send(twimlResponse('Sorry, having trouble. Connecting you with Vlad.', false, process.env.OWNER_PHONE || '+19802016705'));
  }
});

module.exports = router;
