/* Service Worker for Panorama Comms web-push.
   Handles push events (tab closed or backgrounded) and notification clicks. */
/* eslint-disable no-restricted-globals */

self.addEventListener("install", () => {
    self.skipWaiting();
});

self.addEventListener("activate", (event) => {
    event.waitUntil(self.clients.claim());
});

self.addEventListener("push", (event) => {
    let data = {};
    try {
        data = event.data ? event.data.json() : {};
    } catch (e) {
        data = { title: "Panorama Comms", body: event.data ? event.data.text() : "" };
    }
    const title = data.title || "Panorama Comms";
    const options = {
        body: data.body || "",
        tag: data.tag || undefined,
        renotify: !!data.tag,
        data: {
            url: data.url || "/",
            channel_id: data.channel_id,
            message_id: data.message_id,
        },
    };
    event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener("notificationclick", (event) => {
    event.notification.close();
    const target = (event.notification.data && event.notification.data.url) || "/";
    event.waitUntil(
        (async () => {
            const allClients = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
            for (const client of allClients) {
                try {
                    const url = new URL(client.url);
                    // Focus any existing app tab
                    if (url.origin === self.location.origin) {
                        client.focus();
                        client.postMessage({
                            type: "push:click",
                            channel_id: event.notification.data?.channel_id,
                            message_id: event.notification.data?.message_id,
                        });
                        return;
                    }
                } catch (_e) {
                    /* ignore */
                }
            }
            if (self.clients.openWindow) {
                await self.clients.openWindow(target);
            }
        })()
    );
});
