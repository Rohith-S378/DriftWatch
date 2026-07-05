const fetch = require('node-fetch');
require('dotenv').config();

async function testNotification() {
  try {
    const response = await fetch('http://localhost:3000/internal/change-events', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-internal-secret': process.env.INTERNAL_SECRET || 'test-internal'
      },
      body: JSON.stringify({
        source_id: 'test-source-001',
        change_type: 'price_update',
        description: 'Test medium severity event for email notification',
        severity: 'medium',
        old_value: '$100',
        new_value: '$120',
        timestamp: new Date().toISOString()
      })
    });
    const data = await response.json();
    console.log('Notification sent:', data);
  } catch (error) {
    console.error('Error sending notification:', error);
  }
}

testNotification();