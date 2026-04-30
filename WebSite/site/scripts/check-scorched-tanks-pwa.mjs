import { readFileSync } from "node:fs";
import { dirname } from "node:path";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const page = readFileSync(
  resolve(root, "static", "play", "scorched-tanks", "index.html"),
  "utf8",
);
const script = readFileSync(
  resolve(root, "static", "play", "scorched-tanks", "original.js"),
  "utf8",
);
const manifest = JSON.parse(
  readFileSync(
    resolve(root, "static", "play", "scorched-tanks", "manifest.webmanifest"),
    "utf8",
  ),
);

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

assert(
  page.includes('<link rel="manifest" href="./manifest.webmanifest'),
  "Scorched Tanks page must expose a web app manifest.",
);
assert(
  !/<button[^>]+id="install-button"[^>]+disabled/.test(page),
  "Install button must stay clickable when beforeinstallprompt is unavailable.",
);
assert(
  script.includes("beforeinstallprompt"),
  "Install flow must still use the native browser prompt when available.",
);
assert(
  script.includes("Install from this browser"),
  "Install flow must report the manual browser-install path as a fallback.",
);
assert(
  script.includes("serviceWorker") &&
    script.includes('register("./service-worker.js", { scope: "./" })'),
  "Scorched Tanks page must register its local service worker.",
);
assert(
  manifest.display === "standalone" &&
    manifest.start_url === "/play/scorched-tanks/" &&
    manifest.scope === "/play/scorched-tanks/",
  "Manifest must remain browser-installable for the Scorched Tanks route.",
);

console.log("Scorched Tanks PWA contract ok");
