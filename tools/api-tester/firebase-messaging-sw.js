self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (event) => event.waitUntil(self.clients.claim()));

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
    self.registration.showNotification(notification.title || 'Native Life', {
      body: notification.body || '',
      data,
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
