import fs from "node:fs";
import http from "node:http";
import path from "node:path";
import { fileURLToPath } from "node:url";
import playwright from "../../WebSite/site/node_modules/@playwright/test/index.js";

const { chromium } = playwright;
const here = path.dirname(fileURLToPath(import.meta.url));
const repo = path.resolve(here, "..", "..");
const staticRoot = path.join(repo, "WebSite", "site", "static");

const mimeTypes = new Map([
  [".adf", "application/octet-stream"],
  [".bin", "application/octet-stream"],
  [".css", "text/css"],
  [".html", "text/html; charset=utf-8"],
  [".js", "text/javascript"],
  [".json", "application/json"],
  [".png", "image/png"],
  [".webmanifest", "application/manifest+json"],
]);

function stubVamigaPage() {
  return `<!doctype html>
<meta charset="utf-8" />
<script>
  window.__receivedLoads = [];
  window.__hardwareConfig = [];
  let mounted = false;
  let running = false;
  window.file_slot_file = undefined;
  window.file_slot_file_name = undefined;
  window.reset_before_load = false;
  window.wasm_configure = (key, value) => window.__hardwareConfig.push([key, value]);
  window.wasm_has_disk = () => mounted;
  window.show_drive_select = () => {};
  window.wasm_run = () => { running = true; };
  window.is_running = () => running;
  window.insert_file = () => {
    mounted = true;
    running = true;
  };
  window.toggle_audio = () => {
    parent.postMessage({ msg: "render_current_audio_state", value: "running" }, "*");
  };
  window.addEventListener("message", async (event) => {
    if (event.data === "poll_state") {
      parent.postMessage({ msg: "render_run_state", value: true, is_warping: false }, "*");
      parent.postMessage({ msg: "render_current_audio_state", value: "suspended" }, "*");
      return;
    }
    if (event.data === "toggle_audio()") {
      window.toggle_audio();
      return;
    }
    if (event.data?.cmd === "load") {
      window.__receivedLoads.push({
        file_name: event.data.file_name,
        hasKickstart: event.data.kickstart_rom instanceof Uint8Array,
        hasExt: event.data.kickstart_ext instanceof Uint8Array,
      });
      window.file_slot_file_name = event.data.file_name;
      window.file_slot_file = event.data.file;
      parent.postMessage({ msg: "render_run_state", value: true, is_warping: false }, "*");
      return;
    }
    if (event.data?.cmd === "script") {
      Function(event.data.script)();
    }
  });
  setTimeout(() => {
    parent.postMessage({ msg: "render_run_state", value: true, is_warping: false }, "*");
    parent.postMessage({ msg: "render_current_audio_state", value: "suspended" }, "*");
  }, 25);
</script>`;
}

function makeServer({ hostedKickstart = false } = {}) {
  const requests = [];
  const server = http.createServer((request, response) => {
    const url = new URL(request.url, "http://127.0.0.1");
    requests.push(url.pathname);

    if (url.pathname === "/play/scorched-tanks/licensed/kickstart-a500-1.3.rom") {
      if (!hostedKickstart) {
        response.writeHead(404, { "Content-Type": "text/plain" });
        response.end("not provisioned");
        return;
      }
      response.writeHead(200, { "Content-Type": "application/octet-stream" });
      response.end(Buffer.alloc(262144, 0x13));
      return;
    }

    const relativePath = decodeURIComponent(url.pathname).replace(/^\/+/, "");
    let resolved = path.resolve(staticRoot, relativePath);
    if (fs.existsSync(resolved) && fs.statSync(resolved).isDirectory()) {
      resolved = path.join(resolved, "index.html");
    }
    if (!resolved.startsWith(staticRoot) || !fs.existsSync(resolved)) {
      response.writeHead(404, { "Content-Type": "text/plain" });
      response.end("not found");
      return;
    }

    const mimeType = mimeTypes.get(path.extname(resolved)) || "application/octet-stream";
    response.writeHead(200, { "Content-Type": mimeType });
    fs.createReadStream(resolved).pipe(response);
  });

  return new Promise((resolve) => {
    server.listen(0, "127.0.0.1", () => {
      resolve({
        baseUrl: `http://127.0.0.1:${server.address().port}`,
        close: () => new Promise((done) => server.close(done)),
        requests,
      });
    });
  });
}

async function withBrowser(task) {
  const browser = await chromium.launch({ headless: true });
  try {
    await task(browser);
  } finally {
    await browser.close();
  }
}

async function installVamigaStub(page, receivedFrames) {
  await page.route("https://vamigaweb.github.io/**", async (route) => {
    receivedFrames.push(route.request().url());
    await route.fulfill({
      status: 200,
      contentType: "text/html",
      body: stubVamigaPage(),
    });
  });
}

async function readProof(page) {
  await page.waitForFunction(() => window.__scorchedTanksOriginal?.getProof);
  return page.evaluate(() => window.__scorchedTanksOriginal.getProof());
}

async function waitForFirmware(page, expectedFirmware) {
  await page.waitForFunction(
    (firmware) => window.__scorchedTanksOriginal?.getProof().firmware === firmware,
    expectedFirmware,
    { timeout: 5000 },
  );
  return readProof(page);
}

async function readStubLoads(page) {
  const frame = page.frames().find((candidate) =>
    candidate.url().startsWith("https://vamigaweb.github.io/"),
  );
  assert(frame, "vAmigaWeb stub frame was not mounted");
  await frame.waitForFunction(() => window.__receivedLoads?.length > 0, { timeout: 5000 });
  return frame.evaluate(() => window.__receivedLoads);
}

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

await withBrowser(async (browser) => {
  {
    const server = await makeServer({ hostedKickstart: false });
    const page = await browser.newPage();
    const frames = [];
    await installVamigaStub(page, frames);
    await page.goto(`${server.baseUrl}/play/scorched-tanks/index.html`);
    const proof = await waitForFirmware(page, "AROS 68k 2026-04-28");
    assert(
      server.requests.includes("/play/scorched-tanks/licensed/kickstart-a500-1.3.rom"),
      "auto mode did not probe hosted Kickstart path",
    );
    assert(
      server.requests.includes("/play/scorched-tanks/assets/aros-rom-20260428.bin"),
      "auto mode did not fall back to bundled AROS ROM",
    );
    assert(proof.firmwareSource === "bundled-free-aros-nightly", "auto fallback proof source mismatch");
    assert(frames.length === 1, "auto fallback should mount one vAmigaWeb frame");
    const loads = await readStubLoads(page);
    assert(loads[0].hasKickstart && loads[0].hasExt, "auto fallback did not inject bundled AROS ROM/ext");
    await page.close();
    await server.close();
  }

  {
    const server = await makeServer({ hostedKickstart: false });
    const page = await browser.newPage();
    const frames = [];
    await installVamigaStub(page, frames);
    await page.goto(`${server.baseUrl}/play/scorched-tanks/index.html?firmware=hosted-kickstart`);
    await page.waitForFunction(
      () => document.getElementById("runtime-status")?.textContent.includes("not provisioned"),
      { timeout: 5000 },
    );
    assert(
      !server.requests.includes("/play/scorched-tanks/assets/aros-rom-20260428.bin"),
      "strict hosted mode silently fell back to AROS",
    );
    assert(frames.length === 0, "strict hosted mode should not mount runtime without licensed ROM");
    await page.close();
    await server.close();
  }

  {
    const server = await makeServer({ hostedKickstart: true });
    const page = await browser.newPage();
    const frames = [];
    await installVamigaStub(page, frames);
    await page.goto(`${server.baseUrl}/play/scorched-tanks/index.html?firmware=hosted-kickstart`);
    const proof = await waitForFirmware(page, "hosted Kickstart 1.3");
    assert(proof.firmwareSource === "hosted-rights-cleared-fallback", "hosted proof source mismatch");
    assert(
      !server.requests.includes("/play/scorched-tanks/assets/aros-rom-20260428.bin"),
      "hosted mode should not fetch AROS ROM",
    );
    assert(frames.length === 1, "hosted mode should mount one vAmigaWeb frame");
    const loads = await readStubLoads(page);
    assert(loads[0].hasKickstart && !loads[0].hasExt, "hosted mode did not inject hosted Kickstart only");
    await page.close();
    await server.close();
  }
});

console.log("scorched launcher firmware routing verified");
