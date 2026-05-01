const { sendTelegramNotification } = require('./telegram');
const { sendEmailNotification } = require('./email');
const { sendSMS } = require('./sms');

async function notifyNewLead(lead) {
  const results = await Promise.allSettled([
    sendTelegramNotification(lead),
    sendEmailNotification(lead),
    sendSMS(lead),
  ]);
  return {
    telegram: results[0].status === 'fulfilled' ? results[0].value : { error: results[0].reason?.message },
    email: results[1].status === 'fulfilled' ? results[1].value : { error: results[1].reason?.message },
    sms: results[2].status === 'fulfilled' ? results[2].value : { error: results[2].reason?.message },
  };
}

module.exports = { notifyNewLead };
