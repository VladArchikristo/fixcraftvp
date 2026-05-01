/**
 * Twilio Inbound Call Pre-filter (Anti-Spam)
 * 
 * Deploy as Twilio webhook for incoming calls.
 * Runs BEFORE Bland AI — filters spam, then forwards to Bland.
 */

const express = require('express');
const router = express.Router();
const twilio = require('twilio');

// Blacklist of known spam callers (persisted to SQLite for cross-restart safety)
const { db } = require('../services/db');

// Config
const SPAM_THRESHOLD_SECONDS = 3; // Calls shorter than this = spam
const MAX_CALLS_PER_MINUTE = 5;   // Same number >5 calls/min = spam
const ANONYMOUS_BLOCKED = true;   // Block "Unknown" / "Anonymous" callers
const VOICEMAIL_FALLBACK = true;  // Send suspected spam to voicemail

/**
 * Check if caller is in blacklist
 */
async function isBlacklisted(phoneNumber) {
  try {
    const row = await db.get(
      'SELECT 1 FROM spam_blacklist WHERE phone_number = ?',
      [phoneNumber]
    );
    return !!row;
  } catch (e) {
    console.error('Blacklist check error:', e);
    return false;
  }
}

/**
 * Check call rate for this number (last minute)
 */
async function isRateLimited(phoneNumber) {
  try {
    const row = await db.get(
      `SELECT COUNT(*) as count FROM call_log 
       FROM caller_number = ? 
       AND timestamp > datetime('now', '-1 minute')`,
      [phoneNumber]
    );
    return row.count > MAX_CALLS_PER_MINUTE;
  } catch (e) {
    console.error('Rate limit check error:', e);
    return false;
  }
}

/**
 * Log the call attempt
 */
async function logCall(phoneNumber, status, duration = null) {
  try {
    await db.run(
      `INSERT INTO call_log (caller_number, status, duration, timestamp)
       VALUES (?, ?, ?, datetime('now'))`,
      [phoneNumber, status, duration]
    );
  } catch (e) {
    console.error('Call log error:', e);
  }
}

/**
 * Main webhook handler
 * POST /voice/inbound
 */
router.post('/inbound', async (req, res) => {
  const callerNumber = req.body.From || 'Unknown';
  const callSid = req.body.CallSid;
  
  console.log(`[ANTISPAM] Incoming call from ${callerNumber}, SID: ${callSid}`);
  
  const twiml = new twilio.twiml.VoiceResponse();
  
  // 1. Block anonymous callers
  if (ANONYMOUS_BLOCKED && (callerNumber === 'Unknown' || callerNumber === 'Anonymous' || callerNumber.startsWith('Restricted'))) {
    console.log(`[ANTISPAM] BLOCKED: Anonymous call`);
    await logCall(callerNumber, 'BLOCKED_ANONYMOUS');
    twiml.reject();
    return res.type('text/xml').send(twiml.toString());
  }
  
  // 2. Check blacklist
  if (await isBlacklisted(callerNumber)) {
    console.log(`[ANTISPAM] BLOCKED: Blacklisted ${callerNumber}`);
    await logCall(callerNumber, 'BLOCKED_BLACKLIST');
    twiml.reject();
    return res.type('text/xml').send(twiml.toString());
  }
  
  // 3. Check rate limit (flooding)
  if (await isRateLimited(callerNumber)) {
    console.log(`[ANTISPAM] BLOCKED: Rate limited ${callerNumber}`);
    await logCall(callerNumber, 'BLOCKED_RATE_LIMIT');
    // Add to blacklist automatically
    await db.run(
      'INSERT OR IGNORE INTO spam_blacklist (phone_number, reason, added_at) VALUES (?, ?, datetime("now"))',
      [callerNumber, 'Auto: rate limit exceeded']
    );
    twiml.reject();
    return res.type('text/xml').send(twiml.toString());
  }
  
  // 4. All clear — forward to Bland AI
  console.log(`[ANTISPAM] ALLOWED: ${callerNumber} → Bland AI`);
  await logCall(callerNumber, 'ALLOWED');
  
  // Forward to Bland webhook (will be configured after Bland setup)
  const BLAND_WEBHOOK = process.env.BLAND_INBOUND_WEBHOOK || 
    'https://api.bland.ai/v1/inbound';
  
  twiml.dial().sip(`${BLAND_WEBHOOK}?from=${encodeURIComponent(callerNumber)}`);
  
  return res.type('text/xml').send(twiml.toString());
});

/**
 * Post-call spam analysis
 * POST /voice/status
 * Twilio sends this when call ends
 */
router.post('/status', async (req, res) => {
  const { From, CallDuration, CallStatus } = req.body;
  
  // Auto-blacklist very short calls (likely robo-dialers)
  if (CallDuration && parseInt(CallDuration) < SPAM_THRESHOLD_SECONDS && CallStatus === 'completed') {
    console.log(`[ANTISPAM] Auto-blacklisting ${From}: ${CallDuration}s call`);
    await db.run(
      `INSERT OR IGNORE INTO spam_blacklist (phone_number, reason, added_at) 
       VALUES (?, ?, datetime('now'))`,
      [From, `Auto: ${CallDuration}s robocall`]
    );
  }
  
  // Update call log with duration
  await logCall(From, CallStatus, CallDuration ? parseInt(CallDuration) : null);
  
  res.sendStatus(200);
});

/**
 * Admin: manually blacklist a number
 * POST /voice/blacklist
 */
router.post('/blacklist', async (req, res) => {
  const { phoneNumber, reason = 'Manual' } = req.body;
  
  if (!phoneNumber) {
    return res.status(400).json({ error: 'phoneNumber required' });
  }
  
  try {
    await db.run(
      `INSERT OR IGNORE INTO spam_blacklist (phone_number, reason, added_at)
       VALUES (?, ?, datetime('now'))`,
      [phoneNumber, reason]
    );
    res.json({ success: true, message: `${phoneNumber} blacklisted` });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

/**
 * Admin: get blacklist
 * GET /voice/blacklist
 */
router.get('/blacklist', async (req, res) => {
  try {
    const rows = await db.all('SELECT * FROM spam_blacklist ORDER BY added_at DESC');
    res.json({ count: rows.length, entries: rows });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

module.exports = router;
