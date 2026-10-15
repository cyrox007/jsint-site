/*
 * Service Worker панели управления.
 *
 * Намеренно не кэшируем HTML, API и приватные ответы: административные данные
 * должны всегда запрашиваться у сервера после проверки сессии. Worker нужен
 * для installability PWA и корректной обработки перехода из уведомлений.
 */
self.addEventListener('install', () => {
    self.skipWaiting();
});

self.addEventListener('activate', event => {
    event.waitUntil(self.clients.claim());
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
