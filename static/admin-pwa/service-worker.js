/*
 * Service Worker панели управления.
 *
 * Намеренно не кэшируем HTML, API и приватные ответы: административные данные
 * всегда запрашиваются у сервера после проверки сессии. Worker отвечает за
 * installability PWA и системные Web Push-уведомления.
 */
self.addEventListener('install', () => {
    self.skipWaiting();
});

self.addEventListener('activate', event => {
    event.waitUntil(self.clients.claim());
});

self.addEventListener('push', event => {
    let payload = {};
    try {
        payload = event.data ? event.data.json() : {};
    } catch (_error) {
        payload = {title: 'JSInteractive', body: event.data ? event.data.text() : ''};
    }

    const title = payload.title || 'JSInteractive';
    const options = {
        body: payload.body || 'Новое событие требует внимания.',
        icon: '/static/favicon/icons8-pastel-glyph-192.png',
        badge: '/static/favicon/icons8-pastel-glyph-70.png',
        tag: payload.tag || 'jsinteractive-admin',
        renotify: payload.severity === 'urgent',
        requireInteraction: payload.severity === 'urgent',
        data: {
            url: payload.url || './'
        }
    };

    event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener('notificationclick', event => {
    event.notification.close();
    const target = event.notification.data && event.notification.data.url
        ? event.notification.data.url
        : './';

    event.waitUntil((async () => {
        const windows = await self.clients.matchAll({type: 'window', includeUncontrolled: true});
        for (const client of windows) {
            if ('focus' in client) {
                await client.focus();
                if ('navigate' in client) {
                    await client.navigate(target);
                }
                return;
            }
        }
        if (self.clients.openWindow) {
            await self.clients.openWindow(target);
        }
    })());
});
