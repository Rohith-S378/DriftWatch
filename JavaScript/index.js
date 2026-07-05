require('dotenv').config();
const express = require('express');
const cors = require('cors');
const nodemailer = require('nodemailer');
const fetch = require('node-fetch');
const fs = require('fs');

const app = express();
const PORT = process.env.PORT || 3000;

// Middleware
app.use(cors({
  origin: [
    'http://localhost:5173',   // React Vite
    'http://localhost:5174',
    '*'
  ]
}));
app.use(express.json());

// In-memory store for received events (simple, no DB needed on Node side)
let receivedEvents = [];

// Email transporter setup
let emailTransporter = null;
if (process.env.EMAIL_USER && process.env.EMAIL_PASS) {
  emailTransporter = nodemailer.createTransport({
    host: process.env.EMAIL_HOST || 'smtp.ethereal.email',
    port: parseInt(process.env.EMAIL_PORT) || 587,
    secure: process.env.EMAIL_SECURE === 'true',
    auth: {
      user: process.env.EMAIL_USER,
      pass: process.env.EMAIL_PASS
    }
  });
}

// Dead letter queue file path
const deadLetterFile = process.env.DEAD_LETTER_FILE || './dead-letter-queue.json';

// Load existing dead letter queue or initialize empty array
let deadLetterQueue = [];
if (process.env.DEAD_LETTER_ENABLED === 'true' && fs.existsSync(deadLetterFile)) {
  try {
    const data = fs.readFileSync(deadLetterFile, 'utf8');
    deadLetterQueue = JSON.parse(data);
  } catch (error) {
    console.warn('Could not load dead letter queue, starting with empty queue:', error.message);
    deadLetterQueue = [];
  }
}

// Save dead letter queue to file
function saveDeadLetterQueue() {
  if (process.env.DEAD_LETTER_ENABLED !== 'true') return;
  try {
    fs.writeFileSync(deadLetterFile, JSON.stringify(deadLetterQueue, null, 2));
  } catch (error) {
    console.error('Failed to save dead letter queue:', error.message);
  }
}

// Add to dead letter queue
function addToDeadLetterQueue(event, errorInfo, attemptNumber) {
  if (process.env.DEAD_LETTER_ENABLED !== 'true') return;

  deadLetterQueue.push({
    event: event,
    failedAt: new Date().toISOString(),
    error: errorInfo,
    attempts: attemptNumber
  });

  // Keep only last 1000 entries to prevent unbounded growth
  if (deadLetterQueue.length > 1000) {
    deadLetterQueue = deadLetterQueue.slice(-1000);
  }

  saveDeadLetterQueue();
  console.warn();
}

// Send email notification
async function sendEmailNotification(event) {
  if (!emailTransporter) {
    throw new Error('Email transporter not configured');
  }

  const mailOptions = {
    from: process.env.EMAIL_FROM || 'notifications@sirius.ai',
    to: process.env.EMAIL_USER || 'admin@example.com',
    subject: `[Sirius Alert] ${event.severity.toUpperCase()} - ${event.change_type} change detected`,
    html: `
      <h2>Sirius Competitive Intelligence Alert</h2>
      <p><strong>Severity:</strong> ${event.severity.toUpperCase()}</p>
      <p><strong>Change Type:</strong> ${event.change_type}</p>
      <p><strong>Source ID:</strong> ${event.source_id}</p>
      <p><strong>Description:</strong> ${event.description}</p>
      ${event.old_value && event.new_value ? `
        <p><strong>Old Value:</strong> ${String(event.old_value).substring(0, 100)}${String(event.old_value).length > 100 ? '...' : ''}</p>
        <p><strong>New Value:</strong> ${String(event.new_value).substring(0, 100)}${String(event.new_value).length > 100 ? '...' : ''}</p>
      ` : ''}
      <p><strong>Detected at:</strong> ${new Date(event.created_at || Date.now()).toLocaleString()}</p>
      <hr>
      <p style="font-size: 0.9em; color: #666;">
        This is an automated message from the Sirius Competitive Intelligence Engine.
      </p>
    `
  };

  const info = await emailTransporter.sendMail(mailOptions);
  console.log(`Email notification sent: ${info.messageId}`);
  return info;
}

// Send Slack notification
async function sendSlackNotification(event) {
  const webhookUrl = process.env.SLACK_WEBHOOK_URL;
  if (!webhookUrl || webhookUrl.includes('YOUR/SLACK/WEBHOOK')) {
    throw new Error('Slack webhook URL not configured');
  }

  const slackMessage = {
    text: '*Sirius Alert*: ' + event.severity.toUpperCase() + ' - ' + event.change_type + '\n*Source ID*: ' + event.source_id + '\n*Description*: ' + event.description
      + (event.old_value !== null && event.new_value !== null ? '\n*Old Value*: ' + String(event.old_value).substring(0, 100) + (String(event.old_value).length > 100 ? '...' : '') + '\n*New Value*: ' + String(event.new_value).substring(0, 100) + (String(event.new_value).length > 100 ? '...' : '') : '')
  };

  const response = await fetch(webhookUrl, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(slackMessage)
  });

  if (!response.ok) {
    throw new Error('Slack webhook returned ' + response.status + ': ' + await response.text());
  }

  console.log('Slack notification sent successfully');
}

// Determine if event should trigger Slack notification based on severity
function shouldNotifySlack(event) {
  const slackLevels = (process.env.SLACK_SEVERITY_LEVELS || 'critical,high').split(',').map(s => s.trim().toLowerCase());
  return slackLevels.includes(event.severity.toLowerCase());
}

// Determine if event should trigger email notification based on severity
function shouldNotifyEmail(event) {
  const emailLevels = (process.env.EMAIL_SEVERITY_LEVELS || 'medium,low').split(',').map(s => s.trim().toLowerCase());
  return emailLevels.includes(event.severity.toLowerCase());
}

// Send notifications with retry logic
async function sendNotificationsWithRetry(event, attempt = 1) {
  const maxAttempts = parseInt(process.env.MAX_RETRY_ATTEMPTS) || 3;

  try {
    const notificationsSent = [];

    // Send Slack notification if configured and severity matches
    if (shouldNotifySlack(event)) {
      try {
        await sendSlackNotification(event);
        notificationsSent.push('slack');
      } catch (slackError) {
        console.warn('Slack notification failed (attempt ' + attempt + '):', slackError.message);
        throw slackError; // Re-throw to trigger retry
      }
    }

    // Send email notification if configured and severity matches
    if (shouldNotifyEmail(event)) {
      try {
        await sendEmailNotification(event);
        notificationsSent.push('email');
      } catch (emailError) {
        console.warn('Email notification failed (attempt ' + attempt + '):', emailError.message);
        throw emailError; // Re-throw to trigger retry
      }
    }

    if (notificationsSent.length > 0) {
      console.log('✅ Notifications sent via ' + notificationsSent.join(', ') + ' for event ' + event.source_id + ' (' + event.change_type + ')');
      return true;
    }

    // If no notifications were sent (severity didn't match any rules), still consider it successful
    console.log('ℹ️  No notifications sent for event ' + event.source_id + ' (severity: ' + event.severity + ') - not routed to any channel');
    return true;
  } catch (error) {
    if (attempt < maxAttempts) {
      const delay = parseInt(process.env.RETRY_DELAY_MS) || 1000;
      console.log('⏳ Notification attempt ' + attempt + ' failed, retrying in ' + delay + 'ms...');
      await new Promise(resolve => setTimeout(resolve, delay));
      return sendNotificationsWithRetry(event, attempt + 1);
    } else {
      // All attempts failed, add to dead letter queue
      console.error('❌ All notification attempts failed for event ' + event.source_id);
      addToDeadLetterQueue(event, error.message, attempt);
      throw error;
    }
  }
}

// Health check endpoint
app.get('/health', (req, res) => {
  res.json({
    status: 'ok',
    service: 'Sirius Notification Service',
    events_stored: receivedEvents.length,
    dead_letter_queue_length: deadLetterQueue.length,
    timestamp: new Date().toISOString()
  });
});

// Internal endpoint for receiving change events from Python backend
app.post('/internal/change-events', async (req, res) => {
  try {
    const event = req.body;

    // Validate required fields
    if (!event.source_id || !event.change_type || !event.severity || !event.description) {
      return res.status(400).json({
        error: 'Missing required fields: source_id, change_type, severity, description'
      });
    }

    // Validate secret
    const providedSecret = req.headers['x-internal-secret'];
    if (providedSecret !== process.env.INTERNAL_SECRET) {
      return res.status(401).json({ error: 'Invalid internal secret' });
    }

    // Store event (keep only last 100)
    receivedEvents.unshift({ ...event, received_at: new Date().toISOString() });
    if (receivedEvents.length > 100) {
      receivedEvents = receivedEvents.slice(0, 100);
    }

    console.log('📥 Change event received: ' + event.source_id + ' - ' + event.change_type + ' [' + event.severity + ']');

    // Send notifications (email/Slack based on severity routing)
    try {
      await sendNotificationsWithRetry(event);
      res.json({
        ok: true,
        message: 'Event processed and notifications sent',
        event_id: event.source_id + '-' + Date.now()
      });
    } catch (notificationError) {
      // Even if notifications failed, we still acknowledge receipt of the event
      // The event is stored and will be in the dead letter queue for manual retry
      res.json({
        ok: true,
        message: 'Event received but notification failed - see dead letter queue',
        error: notificationError.message
      });
    }
  } catch (error) {
    console.error('Error processing change event:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

// Endpoint for frontend to retrieve events
app.get('/api/events', (req, res) => {
  const includeTechnical = req.query.includeTechnical === 'true';

  let filteredEvents = receivedEvents;
  if (!includeTechnical) {
    // Filter out events that are purely technical/metadata updates
    filteredEvents = receivedEvents.filter(event => !isPurelyTechnicalUpdate(event));
  }

  res.json(filteredEvents);
});

// Helper function to determine if an event is purely a technical/update metadata change
function isPurelyTechnicalUpdate(event) {
  // If there's no diff, we can't determine - conservatively treat as non-technical
  if (!event.diff || typeof event.diff !== 'object' || Array.isArray(event.diff)) {
    return false;
  }

  // Flatten the diff object to check all changed paths
  const changedPaths = getChangedPathsFromDiff(event.diff);

  // Define patterns that indicate technical/metadata fields
  const technicalPatterns = [
    /_at$/,           // ends with _at (e.g., scraped_at, updated_at, created_at)
    /_time$/,         // ends with _time
    /timestamp/i,     // contains timestamp
    /version/i,       // contains version
    /version/i,       // contains version
    /^id$/,           // exactly "id"
    /^_id$/,          // exactly "_id"
    /^metadata$/i,    // exactly "metadata" (case insensitive)
    /^meta$/i,        // exactly "meta" (case insensitive)
  ];

  // Check if ALL changed paths are technical
  return changedPaths.length > 0 && changedPaths.every(path =>
    technicalPatterns.some(pattern => pattern.test(path))
  );
}

// Helper function to extract all changed paths from a diff object
function getChangedPathsFromDiff(diff, prefix = '') {
  const paths = [];

  for (const key in diff) {
    const value = diff[key];
    const fullPath = prefix ? `${prefix}.${key}` : key;

    // If the value is an object (but not an array), recurse into it
    if (value !== null && typeof value === 'object' && !Array.isArray(value)) {
      paths.push(...getChangedPathsFromDiff(value, fullPath));
    }
    // If it's an array, we might want to check its elements too
    else if (Array.isArray(value)) {
      // For arrays, we'll consider the array itself as changed
      paths.push(fullPath);
      // Optionally, we could check individual array elements, but for simplicity
      // we'll treat the array as a single changed field
    }
    // Primitive values (string, number, boolean, null, undefined) indicate a change
    else {
      paths.push(fullPath);
    }
  }

  return paths;
}

app.get('/api/events/:sourceId', (req, res) => {
  const filtered = receivedEvents.filter(
    e => e.source_id === req.params.sourceId
  );
  res.json(filtered);
});

// Dead letter queue management endpoints
app.get('/api/dead-letter', (req, res) => {
  res.json(deadLetterQueue);
});

app.post('/api/dead-letter/retry/:index', async (req, res) => {
  const index = parseInt(req.params.index);
  if (isNaN(index) || index < 0 || index >= deadLetterQueue.length) {
    return res.status(400).json({ error: 'Invalid dead letter queue index' });
  }

  const queueItem = deadLetterQueue[index];
  try {
    await sendNotificationsWithRetry(queueItem.event, 1);
    // Remove from queue on successful retry
    deadLetterQueue.splice(index, 1);
    saveDeadLetterQueue();
    res.json({ ok: true, message: 'Event successfully retried and removed from dead letter queue' });
  } catch (error) {
    res.status(500).json({ error: 'Retry failed: ' + error.message });
  }
});

app.delete('/api/dead-letter/:index', (req, res) => {
  const index = parseInt(req.params.index);
  if (isNaN(index) || index < 0 || index >= deadLetterQueue.length) {
    return res.status(400).json({ error: 'Invalid dead letter queue index' });
  }

  deadLetterQueue.splice(index, 1);
  saveDeadLetterQueue();
  res.json({ ok: true, message: 'Event removed from dead letter queue' });
});

// Start server
const server = app.listen(PORT, () => {
  console.log('🚀 Sirius Notification Service running on http://localhost:' + PORT);
  console.log('📧 Email notifications: ' + (emailTransporter ? 'enabled' : 'disabled (missing credentials)'));
  console.log('💬 Slack notifications: ' + (process.env.SLACK_WEBHOOK_URL && !process.env.SLACK_WEBHOOK_URL.includes('YOUR/SLACK/WEBHOOK') ? 'enabled' : 'disabled (webhook not configured)'));
});

// Graceful shutdown
process.on('SIGINT', () => {
  console.log('🛑 Shutting down Sirius Notification Service...');
  saveDeadLetterQueue();
  server.close(() => {
    console.log('✅ Service stopped');
    process.exit(0);
  });
});

process.on('SIGTERM', () => {
  console.log('🛑 Received SIGTERM, shutting down...');
  saveDeadLetterQueue();
  server.close(() => {
    console.log('✅ Service stopped');
    process.exit(0);
  });
});