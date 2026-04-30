(function () {
  const VAMIGA_ORIGIN = "https://vamigaweb.github.io";
  const VAMIGA_URL = `${VAMIGA_ORIGIN}/`;
  const ADF_URL = "./assets/scorched-tanks-v1.90-autostart-0fd8b963.adf";

  const installButton = document.getElementById("install-button");
  const fullscreenButton = document.getElementById(
    "emulator-fullscreen-button",
  );
  const arosButton = document.getElementById("start-aros-button");
  const kickstartButton = document.getElementById("start-kickstart-button");
  const resetButton = document.getElementById("reset-emulator-button");
  const kickstartInput = document.getElementById("kickstart-input");
  const emulatorFrameHost = document.getElementById("emulator-frame-host");
  const emulatorPanel = document.getElementById("emulator-panel");
  const runtimeStatus = document.getElementById("runtime-status");
  const mediaStatus = document.getElementById("media-status");
  const romStatus = document.getElementById("rom-status");

  let installPrompt = null;
  let frame = null;
  let pollTimer = null;
  let pendingLaunch = null;
  let currentLaunch = null;
  let kickstartRom = null;

  function setRuntimeStatus(text) {
    runtimeStatus.textContent = text;
  }

  function setMediaStatus(text) {
    mediaStatus.textContent = text;
  }

  function setRomStatus(text) {
    romStatus.textContent = text;
  }

  function browserTouchMode() {
    return window.matchMedia("(pointer: coarse)").matches;
  }

  function emulatorSrc(config) {
    return `${VAMIGA_URL}#${encodeURIComponent(JSON.stringify(config))}`;
  }

  function absoluteAdfUrl() {
    return new URL(ADF_URL, window.location.href).href;
  }

  function baseConfig(extra) {
    return {
      navbar: false,
      wide: true,
      display: "adaptive",
      border: false,
      dialog_on_disk: false,
      port2: true,
      touch: browserTouchMode(),
      warpto: 1200,
      url: absoluteAdfUrl(),
      ...extra,
    };
  }

  function clearPoller() {
    if (pollTimer) {
      window.clearInterval(pollTimer);
      pollTimer = null;
    }
  }

  function startPoller() {
    clearPoller();
    pollTimer = window.setInterval(() => {
      frame?.contentWindow?.postMessage("poll_state", VAMIGA_ORIGIN);
    }, 700);
  }

  async function injectKickstart() {
    if (!pendingLaunch || !frame?.contentWindow) {
      return;
    }

    const launch = pendingLaunch;
    pendingLaunch = null;
    setRuntimeStatus("Loading user ROM");

    try {
      const payload = {
        cmd: "load",
        kickstart_rom: launch.kickstartRom.bytes,
      };

      frame.contentWindow.postMessage(payload, VAMIGA_ORIGIN);
      setMediaStatus("Original v1.90 autostart ADF assigned to df0");
      setRuntimeStatus(`Running with ${launch.kickstartRom.name}`);
    } catch (error) {
      pendingLaunch = launch;
      setRuntimeStatus(error.message || "ROM injection failed");
    }
  }

  function mountEmulator(config, launch) {
    pendingLaunch = launch.kickstartRom ? launch : null;
    currentLaunch = launch;
    clearPoller();
    document.body.classList.remove("is-playing");
    emulatorFrameHost.textContent = "";
    frame = document.createElement("iframe");
    frame.id = "vAmigaWeb";
    frame.title = "vAmigaWeb running Scorched Tanks";
    frame.allow = "fullscreen; gamepad; autoplay";
    frame.src = emulatorSrc(config);
    frame.addEventListener("load", () => {
      setRuntimeStatus("Runtime booting");
      document.body.classList.add("is-playing");
      startPoller();
    });
    emulatorFrameHost.appendChild(frame);
  }

  function startWithAros() {
    setRomStatus("AROS trial; use ROM if stuck");
    setMediaStatus("Original v1.90 autostart ADF assigned to df0");
    mountEmulator(
      baseConfig({
        AROS: true,
      }),
      { kickstartRom: null },
    );
  }

  function startWithKickstart() {
    if (!kickstartRom) {
      setRomStatus("Choose a Kickstart ROM first");
      return;
    }

    mountEmulator(
      baseConfig({
        AROS: false,
        wait_for_kickstart_injection: true,
      }),
      { kickstartRom },
    );
  }

  function resetEmulator() {
    if (!frame) {
      startWithAros();
      return;
    }
    const relaunch = pendingLaunch || currentLaunch || { kickstartRom };
    mountEmulator(
      baseConfig(
        relaunch.kickstartRom
          ? { AROS: false, wait_for_kickstart_injection: true }
          : { AROS: true },
      ),
      relaunch,
    );
  }

  async function onKickstartSelected() {
    const [file] = kickstartInput.files || [];
    if (!file) {
      kickstartRom = null;
      kickstartButton.disabled = true;
      setRomStatus("No Kickstart ROM selected");
      return;
    }

    kickstartRom = {
      name: file.name,
      bytes: new Uint8Array(await file.arrayBuffer()),
    };
    kickstartButton.disabled = false;
    setRomStatus(`${file.name} ready locally`);
  }

  function bindInstall() {
    if ("serviceWorker" in navigator) {
      window.addEventListener("load", () => {
        navigator.serviceWorker
          .register("./service-worker.js", { scope: "./" })
          .catch(() => setRuntimeStatus("Offline cache unavailable"));
      });
    }

    window.addEventListener("beforeinstallprompt", (event) => {
      event.preventDefault();
      installPrompt = event;
      installButton.disabled = false;
    });

    installButton.addEventListener("click", async () => {
      if (!installPrompt) {
        setRuntimeStatus("Install unavailable in this browser");
        return;
      }
      installButton.disabled = true;
      installPrompt.prompt();
      await installPrompt.userChoice;
      installPrompt = null;
    });
  }

  window.addEventListener("message", (event) => {
    if (
      event.origin !== VAMIGA_ORIGIN ||
      event.source !== frame?.contentWindow
    ) {
      return;
    }

    if (event.data?.msg === "render_run_state") {
      if (!pendingLaunch) {
        setRuntimeStatus(
          event.data.value ? "Running AROS trial" : "Runtime ready",
        );
      }
      injectKickstart();
    }
  });

  window.addEventListener("error", (event) => {
    setRuntimeStatus(event.message || "Runtime error");
  });

  fullscreenButton.addEventListener("click", () => {
    if (document.fullscreenElement) {
      document.exitFullscreen();
      return;
    }
    emulatorPanel.requestFullscreen?.();
  });

  arosButton.addEventListener("click", startWithAros);
  kickstartButton.addEventListener("click", startWithKickstart);
  resetButton.addEventListener("click", resetEmulator);
  kickstartInput.addEventListener("change", onKickstartSelected);

  bindInstall();
  setMediaStatus("Original v1.90 autostart ADF ready");
  startWithAros();
})();
