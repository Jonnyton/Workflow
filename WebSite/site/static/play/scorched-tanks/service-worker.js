const CACHE_NAME = "scorched-tanks-original-amiga-v18";
const ASSETS = [
  "./",
  "./index.html",
  "./styles.css?v=exact-mount-guard",
  "./original.js?v=hosted-kickstart-auto",
  "./app.js?v=exact-mount-guard",
  "./compatibility.json",
  "./assets/scorched-tanks-v1.75-ap41-stack-d035687c.adf",
  "./assets/scorched-tanks-v1.90-autostart-30582ca3.adf",
  "./manifest.webmanifest?v=exact-mount-guard",
  "./icons/icon-192.png",
  "./icons/icon-512.png",
];

self.addEventListener("install", (event) => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(ASSETS)),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys
            .filter((key) => key !== CACHE_NAME)
            .map((key) => caches.delete(key)),
        ),
      )
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  if (new URL(event.request.url).origin !== location.origin) {
    return;
  }

  const destination = event.request.destination;

  if (
    event.request.mode === "navigate" ||
    ["document", "script", "style", "worker", "manifest"].includes(destination)
  ) {
    event.respondWith(
      fetch(event.request)
        .then((response) => {
          const copy = response.clone();
          caches
            .open(CACHE_NAME)
            .then((cache) => cache.put(event.request, copy));
          return response;
        })
        .catch(() =>
          caches
            .match(event.request)
            .then((cached) => cached || caches.match("./")),
        ),
    );
    return;
  }

  event.respondWith(
    caches
      .match(event.request)
      .then((cached) => cached || fetch(event.request)),
  );
});
