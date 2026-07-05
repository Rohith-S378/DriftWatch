const fetch = require('node-fetch');
require('dotenv').config();

async function testSlack() {
  try {
    const response = await fetch('http://localhost:3000/internal/change-events', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-internal-secret': process.env.INTERNAL_SECRET || 'test-internal'
      },
      body: JSON.stringify({
        source_id: 'slack-test-001',
        change_type: 'headline_change',
        description: 'Test high severity for Slack',
        severity: 'high',
        old_value: 'Old headline',
        new_value: 'New headline',
        timestamp: new Date().toISOString()
      })
    });
    const data = await response.json();
    console.log('Slack test result:', data);
  } catch (error) {
    console.error('Error:', error);
  }
}

testSlack();