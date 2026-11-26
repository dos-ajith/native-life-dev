self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (event) => event.waitUntil(self.clients.claim()));

const CHAT_QUERY_TIMEOUT_MS = 400;

function askClient(client, senderId) {
  return new Promise((resolve) => {
    const channel = new MessageChannel();
    const timer = setTimeout(() => resolve(false), CHAT_QUERY_TIMEOUT_MS);
    channel.port1.onmessage = (reply) => {
      clearTimeout(timer);
      resolve(reply.data === true);
    };
    client.postMessage({ type: 'is-chat-open', senderId }, [channel.port2]);
  });
}

async function chatIsOpen(data) {
  if (data.type !== 'direct_message') return false;
  const clients = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
  const visible = clients.filter((client) => client.visibilityState === 'visible');
  const answers = await Promise.all(visible.map((client) => askClient(client, data.sender_id)));
  return answers.some(Boolean);
}

self.addEventListener('push', (event) => {
  if (!event.data) return;
  let payload;
  try {
    payload = event.data.json();
  } catch {
    return;
  }
  const notification = payload.notification || {};
  const data = payload.data || {};
  event.waitUntil(
    chatIsOpen(data).then((open) => {
      if (open) return undefined;
      return self.registration.showNotification(notification.title || 'Native Life', {
        body: notification.body || '',
        data,
      });
    })
  );
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clients) => {
      if (clients.length) return clients[0].focus();
      return self.clients.openWindow('./push-test.html');
    })
  );
});
