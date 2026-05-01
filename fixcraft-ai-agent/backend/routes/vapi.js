const express = require('express');
const router = express.Router();
const { run, all } = require('../services/db');
const { notifyNewLead } = require('../services/notifications');

// 🔥 CATCH-ALL: Vapi sends function calls to the root serverUrl
router.post('/', async (req, res) => {
  try {
    console.log(`[${new Date().toISOString()}] VAPI ROOT INCOMING:`, JSON.stringify(req.body, null, 2));
    
    // Vapi sends tool call info in the body
    const body = req.body;
    const message = body.message || body;
    const toolCalls = message.toolCalls || message.tool_calls || [];
    
    if (toolCalls.length === 0) {
      console.log('No tool calls in request');
      return res.json({ success: true });
    }
    
    for (const toolCall of toolCalls) {
      const func = toolCall.function || toolCall;
      const name = func.name || func.functionName;
      const args = func.arguments || func.parameters || func.args || {};
      
      console.log(`Function call: ${name}`, args);
      
      if (name === 'saveLead') {
        const { name, phone, address, service_type, urgency, notes, date, time_slot } = args;
        const source = 'phone-vapi';
        
        // 🔥 DEDUPLICATION: skip if same phone in last 60 seconds
        const existing = await all(
          `SELECT id FROM leads WHERE phone = ? AND source = 'phone-vapi' AND created_at > datetime('now', '-60 seconds') ORDER BY id DESC LIMIT 1`,
          [phone]
        );
        if (existing.length > 0) {
          console.log(`Duplicate lead skipped for phone ${phone}, existing ID: ${existing[0].id}`);
          return res.json({ success: true, leadId: existing[0].id, message: 'Duplicate skipped' });
        }
        
        const result = await run(
          `INSERT INTO leads (name, phone, address, service_type, urgency, notes, source, status, requested_date, requested_time) VALUES (?, ?, ?, ?, ?, ?, ?, 'new', ?, ?)`,
          [name || null, phone || null, address || null, service_type || null, urgency || null, notes || null, source, date || null, time_slot || null]
        );
        await notifyNewLead({ id: result.id, name, phone, address, serviceType: service_type, urgency, notes, source, date, timeSlot: time_slot });
        console.log('Lead saved:', result.id);
      }
    }
    
    return res.json({ success: true });
  } catch (err) {
    console.error('Vapi root error:', err);
    return res.status(200).json({ success: true }); // Always 200 to Vapi
  }
});

// Legacy endpoint for direct POST
router.post('/lead', async (req, res) => {
  try {
    const { name, phone, address, service_type, urgency, notes, date, time_slot } = req.body;
    console.log(`[${new Date().toISOString()}] VAPI-LEAD INCOMING:`, JSON.stringify(req.body, null, 2));
    const source = 'phone-vapi';
    const result = await run(
      `INSERT INTO leads (name, phone, address, service_type, urgency, notes, source, status, requested_date, requested_time) VALUES (?, ?, ?, ?, ?, ?, ?, 'new', ?, ?)`,
      [name || null, phone || null, address || null, service_type || null, urgency || null, notes || null, source, date || null, time_slot || null]
    );
    await notifyNewLead({ id: result.id, name, phone, address, serviceType: service_type, urgency, notes, source, date, timeSlot: time_slot });
    return res.json({ success: true, leadId: result.id, message: 'Lead saved' });
  } catch (err) {
    console.error('Vapi lead save error:', err);
    return res.status(500).json({ success: false, error: err.message });
  }
});

// Call status webhook
router.post('/status', async (req, res) => {
  try {
    const { call, status, startedAt, endedAt, duration } = req.body;
    const caller = call?.customer?.number || 'unknown';
    await run(
      `INSERT INTO call_log (caller_number, status, duration) VALUES (?, ?, ?)`,
      [caller, status || 'completed', duration || 0]
    );
    return res.json({ success: true });
  } catch (err) {
    console.error('Vapi status error:', err);
    return res.json({ success: false });
  }
});

module.exports = router;
