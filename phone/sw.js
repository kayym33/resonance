// Service worker: keeps the app working offline and shows pushed
// notifications (event reminders, timers, the desktop's "phone" command).
const CACHE = "t1ld3-shell";
const SHELL = [
  "./", "index.html", "style.css", "manifest.webmanifest", "icons/icon-180.png", "icons/icon-192.png",
  "js/app.js", "js/cloud.js", "js/config.js", "js/data.js", "js/events.js", "js/gestures.js", "js/push.js",
  "js/recipes.js", "js/store.js", "js/timers.js", "js/ui.js",
  "js/views/calendar.js", "js/views/cookbook.js", "js/views/me.js", "js/views/today.js", "js/views/todo.js",
];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

// The app's own files: the network first, so a new version shows straight
// away, and the cache when offline. Sync requests go straight through.
self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== "GET" || url.origin !== location.origin) return;
  event.respondWith(
    fetch(event.request)
      .then((response) => {
        if (response.ok) {
          const copy = response.clone();
          caches.open(CACHE).then((cache) => cache.put(event.request, copy));
        }
        return response;
      })
      .catch(() => caches.match(event.request).then((cached) => cached ?? caches.match("index.html"))),
  );
});

self.addEventListener("push", (event) => {
  let message = {};
  try {
    message = event.data ? event.data.json() : {};
  } catch {
    message = { body: event.data?.text() ?? "" };
  }
  // iOS stops sending pushes to an app that receives one without showing
  // a notification, so always show one.
  event.waitUntil(self.registration.showNotification(message.title || "t1ld3", {
    body: message.body || "",
    icon: "icons/icon-192.png",
    tag: message.tag,
    data: { url: message.url || "./" },
  }));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const target = new URL(event.notification.data?.url || "./", self.registration.scope).href;
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((windows) => {
      const open = windows.find((client) => client.url.startsWith(self.registration.scope));
      if (open) {
        open.navigate(target).catch(() => {});
        return open.focus();
      }
      return self.clients.openWindow(target);
    }),
  );
});
