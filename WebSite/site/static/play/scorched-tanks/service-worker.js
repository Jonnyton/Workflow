const CACHE_NAME = "scorched-tanks-original-amiga-v8";
const ASSETS = [
  "./",
  "./index.html",
  "./styles.css?v=rights-runtime",
  "./original.js?v=rights-runtime",
  "./app.js?v=rights-runtime",
  "./compatibility.json",
  "./assets/scorched-tanks-v1.90-autostart-a642eb46.adf",
  "./manifest.webmanifest?v=rights-runtime",
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
