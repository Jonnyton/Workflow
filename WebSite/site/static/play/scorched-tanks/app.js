(function () {
  const WIDTH = 960;
  const HEIGHT = 540;
  const GROUND_FLOOR = HEIGHT - 34;
  const GRAVITY = 0.125;
  const FIRE_DELAY_MS = 850;

  const canvas = document.getElementById("game");
  if (!canvas) {
    return;
  }
  const ctx = canvas.getContext("2d");
  const fullscreenButton = document.getElementById("compat-fullscreen-button");
  const stage = document.querySelector(".compat-stage");
  const turnLabel = document.getElementById("turn-label");
  const windLabel = document.getElementById("wind-label");
  const status = document.getElementById("status");
  const angleControl = document.getElementById("angle-control");
  const angleValue = document.getElementById("angle-value");
  const powerControl = document.getElementById("power-control");
  const powerValue = document.getElementById("power-value");
  const weaponControl = document.getElementById("weapon-control");
  const fireButton = document.getElementById("fire-button");
  const newRoundButton = document.getElementById("new-round-button");

  const weapons = {
    single: { name: "Single Shot", radius: 30, damage: 42, dirt: false, count: 1 },
    big: { name: "Big Shot", radius: 46, damage: 62, dirt: false, count: 1 },
    dirt: { name: "Dirt Slinger", radius: 34, damage: 8, dirt: true, count: 1 },
    split: { name: "Scatter Shot", radius: 24, damage: 28, dirt: false, count: 3 }
  };

  let lastFrame = 0;
  let botTimer = null;

  const state = {
    round: 1,
    phase: "aim",
    terrain: [],
    tanks: [],
    current: 0,
    wind: 0,
    projectiles: [],
    particles: [],
    flashes: [],
    stars: [],
    message: "Ready"
  };

  function clamp(value, min, max) {
    return Math.max(min, Math.min(max, value));
  }

  function randomRange(min, max) {
    return min + Math.random() * (max - min);
  }

  function setStatus(text) {
    state.message = text;
    status.textContent = text;
  }

  function updateReadouts() {
    const tank = activeTank();
    const windText = state.wind === 0 ? "0.0" : state.wind.toFixed(1);
    windLabel.textContent = `Wind ${windText}`;
    if (tank) {
      turnLabel.textContent = `${tank.name} ${Math.max(0, Math.ceil(tank.hp))}%`;
    }
    angleValue.textContent = angleControl.value;
    powerValue.textContent = powerControl.value;
  }

  function setControlsEnabled(enabled) {
    const usable = enabled && state.phase === "aim" && activeTank()?.human;
    angleControl.disabled = !usable;
    powerControl.disabled = !usable;
    weaponControl.disabled = !usable;
    fireButton.disabled = !usable;
  }

  function activeTank() {
    return state.tanks[state.current] || null;
  }

  function aliveTanks() {
    return state.tanks.filter((tank) => tank.alive);
  }

  function makeTerrain() {
    const controlPoints = [];
    for (let x = -80; x <= WIDTH + 80; x += 80) {
      const height =
        348 +
        Math.sin((x + state.round * 73) * 0.012) * 38 +
        Math.sin((x + state.round * 21) * 0.027) * 20 +
        randomRange(-34, 34);
      controlPoints.push({ x, y: clamp(height, 278, 438) });
    }

    state.terrain = new Array(WIDTH);
    for (let i = 0; i < controlPoints.length - 1; i += 1) {
      const left = controlPoints[i];
      const right = controlPoints[i + 1];
      const span = right.x - left.x;
      for (let x = Math.max(0, left.x); x < Math.min(WIDTH, right.x); x += 1) {
        const t = (x - left.x) / span;
        const eased = t * t * (3 - 2 * t);
        state.terrain[x] = left.y + (right.y - left.y) * eased;
      }
    }

    for (let pass = 0; pass < 4; pass += 1) {
      const next = state.terrain.slice();
      for (let x = 2; x < WIDTH - 2; x += 1) {
        next[x] =
          state.terrain[x - 2] * 0.1 +
          state.terrain[x - 1] * 0.2 +
          state.terrain[x] * 0.4 +
          state.terrain[x + 1] * 0.2 +
          state.terrain[x + 2] * 0.1;
      }
      state.terrain = next;
    }
  }

  function terrainAt(x) {
    const index = clamp(Math.round(x), 0, WIDTH - 1);
    return state.terrain[index] || GROUND_FLOOR;
  }

  function makeTank(name, x, color, human) {
    return {
      name,
      x,
      y: terrainAt(x) - 8,
      color,
      human,
      alive: true,
      hp: 100,
      angle: human ? 45 : x < WIDTH / 2 ? 50 : 130,
      power: human ? 68 : 64,
      weapon: "single",
      cooldown: 0
    };
  }

  function placeTanks() {
    state.tanks = [
      makeTank("Commander", 118, "#e24d35", true),
      makeTank("Mira", 378, "#e4ba4d", false),
      makeTank("Kade", 642, "#4ca36a", false),
      makeTank("Orin", 836, "#55a7d9", false)
    ];
    settleTanks();
  }

  function settleTanks() {
    state.tanks.forEach((tank) => {
      if (!tank.alive) {
        return;
      }
      tank.y = terrainAt(tank.x) - 8;
      if (tank.y > GROUND_FLOOR - 8) {
        tank.alive = false;
        tank.hp = 0;
      }
    });
  }

  function startRound() {
    clearTimeout(botTimer);
    state.phase = "aim";
    state.projectiles = [];
    state.particles = [];
    state.flashes = [];
    state.wind = randomRange(-2.4, 2.4);
    makeTerrain();
    placeTanks();
    state.current = 0;
    setStatus("Ready");
    syncControlsFromTank();
    beginTurn();
  }

  function syncControlsFromTank() {
    const tank = activeTank();
    if (!tank) {
      return;
    }
    angleControl.value = Math.round(tank.angle);
    powerControl.value = Math.round(tank.power);
    weaponControl.value = tank.weapon;
    updateReadouts();
  }

  function beginTurn() {
    const winner = winnerTank();
    if (winner) {
      state.phase = "gameover";
      setControlsEnabled(false);
      setStatus(`${winner.name} wins round ${state.round}`);
      return;
    }

    while (!activeTank()?.alive) {
      state.current = (state.current + 1) % state.tanks.length;
    }

    const tank = activeTank();
    state.phase = "aim";
    syncControlsFromTank();
    setControlsEnabled(true);
    setStatus(tank.human ? "Ready" : `${tank.name} aiming`);

    if (!tank.human) {
      setControlsEnabled(false);
      botTimer = setTimeout(() => botFire(tank), FIRE_DELAY_MS);
    }
  }

  function winnerTank() {
    const alive = aliveTanks();
    return alive.length === 1 ? alive[0] : null;
  }

  function nextTurn() {
    state.wind = clamp(state.wind + randomRange(-0.45, 0.45), -3.2, 3.2);
    for (let i = 0; i < state.tanks.length; i += 1) {
      state.current = (state.current + 1) % state.tanks.length;
      if (activeTank()?.alive) {
        break;
      }
    }
    beginTurn();
  }

  function selectedWeapon() {
    return weapons[weaponControl.value] || weapons.single;
  }

  function fireCurrentTank() {
    const tank = activeTank();
    if (!tank || !tank.alive || state.phase !== "aim") {
      return;
    }

    tank.angle = Number(angleControl.value);
    tank.power = Number(powerControl.value);
    tank.weapon = weaponControl.value;

    const weapon = selectedWeapon();
    const shots = weapon.count;
    const offsets = shots === 3 ? [-6, 0, 6] : [0];
    const speed = tank.power * 0.145;
    const muzzle = muzzlePoint(tank);

    state.projectiles = offsets.map((offset, index) => {
      const angle = ((tank.angle + offset) * Math.PI) / 180;
      return {
        x: muzzle.x,
        y: muzzle.y,
        vx: Math.cos(angle) * speed,
        vy: -Math.sin(angle) * speed,
        weaponKey: tank.weapon,
        trail: [],
        age: index * -5
      };
    });

    state.phase = "firing";
    setControlsEnabled(false);
    setStatus(`${tank.name} fired ${weapon.name}`);
  }

  function botFire(tank) {
    if (state.phase !== "aim" || activeTank() !== tank || !tank.alive) {
      return;
    }

    const targets = state.tanks.filter((candidate) => candidate.alive && candidate !== tank);
    const primary = state.tanks[0].alive ? state.tanks[0] : targets[0];
    const target = primary || targets[0];
    const dx = target.x - tank.x;
    const highArc = Math.abs(dx) > 260;
    const baseAngle = dx >= 0 ? (highArc ? 47 : 34) : highArc ? 133 : 146;
    const distance = Math.abs(dx);

    tank.angle = clamp(baseAngle + randomRange(-8, 8) - state.wind * 1.6, 8, 172);
    tank.power = clamp(42 + distance / 8.2 + randomRange(-10, 10), 34, 96);
    tank.weapon = Math.random() > 0.78 ? "big" : Math.random() > 0.68 ? "split" : "single";

    angleControl.value = Math.round(tank.angle);
    powerControl.value = Math.round(tank.power);
    weaponControl.value = tank.weapon;
    updateReadouts();
    fireCurrentTank();
  }

  function muzzlePoint(tank) {
    const angle = (tank.angle * Math.PI) / 180;
    return {
      x: tank.x + Math.cos(angle) * 23,
      y: tank.y - 14 - Math.sin(angle) * 23
    };
  }

  function updateProjectiles(delta) {
    if (!state.projectiles.length) {
      return;
    }

    const survivors = [];
    state.projectiles.forEach((projectile) => {
      projectile.age += delta;
      if (projectile.age < 0) {
        survivors.push(projectile);
        return;
      }

      projectile.vx += state.wind * 0.006 * delta;
      projectile.vy += GRAVITY * delta;
      projectile.x += projectile.vx * delta;
      projectile.y += projectile.vy * delta;
      projectile.trail.push({ x: projectile.x, y: projectile.y });
      if (projectile.trail.length > 20) {
        projectile.trail.shift();
      }

      const impactTank = state.tanks.find((tank) => {
        if (!tank.alive) {
          return false;
        }
        const dx = tank.x - projectile.x;
        const dy = tank.y - 10 - projectile.y;
        return Math.hypot(dx, dy) < 18;
      });

      const hitTerrain =
        projectile.x >= 0 &&
        projectile.x < WIDTH &&
        projectile.y >= terrainAt(projectile.x) - 3;
      const outOfBounds =
        projectile.x < -60 ||
        projectile.x > WIDTH + 60 ||
        projectile.y > HEIGHT + 80;

      if (impactTank || hitTerrain) {
        explode(projectile.x, projectile.y, projectile.weaponKey);
      } else if (!outOfBounds) {
        survivors.push(projectile);
      }
    });

    state.projectiles = survivors;
    if (!state.projectiles.length && state.phase === "firing") {
      state.phase = "settling";
      setTimeout(() => {
        settleTanks();
        nextTurn();
      }, 700);
    }
  }

  function explode(x, y, weaponKey) {
    const weapon = weapons[weaponKey] || weapons.single;
    const radius = weapon.radius;
    state.flashes.push({ x, y, radius: 4, max: radius * 1.6, life: 1 });

    if (weapon.dirt) {
      for (let ix = Math.floor(x - radius * 1.7); ix <= Math.ceil(x + radius * 1.7); ix += 1) {
        if (ix < 0 || ix >= WIDTH) {
          continue;
        }
        const distance = Math.abs(ix - x);
        const lift = Math.cos((distance / (radius * 1.7)) * Math.PI * 0.5) * 34;
        if (Number.isFinite(lift) && lift > 0) {
          state.terrain[ix] = clamp(state.terrain[ix] - lift, 154, GROUND_FLOOR);
        }
      }
    } else {
      for (let ix = Math.floor(x - radius); ix <= Math.ceil(x + radius); ix += 1) {
        if (ix < 0 || ix >= WIDTH) {
          continue;
        }
        const distance = Math.abs(ix - x);
        const curve = Math.cos((distance / radius) * Math.PI * 0.5);
        const depth = Math.max(0, curve) * (radius * 0.92);
        state.terrain[ix] = clamp(Math.max(state.terrain[ix], y + depth), 130, GROUND_FLOOR);
      }
    }

    state.tanks.forEach((tank) => {
      if (!tank.alive) {
        return;
      }
      const distance = Math.hypot(tank.x - x, tank.y - 12 - y);
      if (distance < radius * 2.2) {
        const damage = Math.max(0, (1 - distance / (radius * 2.2)) * weapon.damage);
        tank.hp -= damage;
        if (tank.hp <= 0) {
          tank.hp = 0;
          tank.alive = false;
          setStatus(`${tank.name} destroyed`);
        }
      }
    });

    for (let i = 0; i < 34; i += 1) {
      const angle = randomRange(0, Math.PI * 2);
      const speed = randomRange(1, 6.2);
      state.particles.push({
        x,
        y,
        vx: Math.cos(angle) * speed,
        vy: Math.sin(angle) * speed - randomRange(0.5, 2.2),
        life: randomRange(0.45, 1),
        size: randomRange(2, 5),
        color: weapon.dirt ? "#a7824f" : Math.random() > 0.35 ? "#f19a3e" : "#f6d66f"
      });
    }

    settleTanks();
    updateReadouts();
  }

  function updateParticles(delta) {
    state.flashes = state.flashes
      .map((flash) => ({
        ...flash,
        radius: flash.radius + (flash.max - flash.radius) * 0.14 * delta,
        life: flash.life - 0.045 * delta
      }))
      .filter((flash) => flash.life > 0);

    state.particles = state.particles
      .map((particle) => ({
        ...particle,
        x: particle.x + particle.vx * delta,
        y: particle.y + particle.vy * delta,
        vy: particle.vy + 0.12 * delta,
        life: particle.life - 0.018 * delta
      }))
      .filter((particle) => particle.life > 0);
  }

  function drawSky() {
    const sky = ctx.createLinearGradient(0, 0, 0, HEIGHT);
    sky.addColorStop(0, "#162c3b");
    sky.addColorStop(0.55, "#3f6173");
    sky.addColorStop(1, "#9a9f80");
    ctx.fillStyle = sky;
    ctx.fillRect(0, 0, WIDTH, HEIGHT);

    ctx.fillStyle = "rgba(255, 219, 116, 0.9)";
    ctx.beginPath();
    ctx.arc(840, 72, 36, 0, Math.PI * 2);
    ctx.fill();

    drawDistantRidge(0.52, "#263b43", 86, 0.012);
    drawDistantRidge(0.63, "#30413a", 66, 0.018);
  }

  function drawDistantRidge(base, color, amplitude, frequency) {
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.moveTo(0, HEIGHT);
    for (let x = 0; x <= WIDTH; x += 8) {
      const y =
        HEIGHT * base +
        Math.sin(x * frequency + state.round) * amplitude * 0.42 +
        Math.sin(x * frequency * 1.7) * amplitude * 0.24;
      ctx.lineTo(x, y);
    }
    ctx.lineTo(WIDTH, HEIGHT);
    ctx.closePath();
    ctx.fill();
  }

  function drawTerrain() {
    const dirt = ctx.createLinearGradient(0, 270, 0, HEIGHT);
    dirt.addColorStop(0, "#5f8a45");
    dirt.addColorStop(0.34, "#496f38");
    dirt.addColorStop(0.72, "#3a3629");
    dirt.addColorStop(1, "#25251e");

    ctx.fillStyle = dirt;
    ctx.beginPath();
    ctx.moveTo(0, HEIGHT);
    for (let x = 0; x < WIDTH; x += 1) {
      ctx.lineTo(x, state.terrain[x]);
    }
    ctx.lineTo(WIDTH, HEIGHT);
    ctx.closePath();
    ctx.fill();

    ctx.strokeStyle = "#c4d77a";
    ctx.lineWidth = 2;
    ctx.beginPath();
    for (let x = 0; x < WIDTH; x += 3) {
      const y = state.terrain[x];
      if (x === 0) {
        ctx.moveTo(x, y);
      } else {
        ctx.lineTo(x, y);
      }
    }
    ctx.stroke();
  }

  function drawTank(tank) {
    if (!tank.alive) {
      ctx.fillStyle = "rgba(20, 20, 18, 0.55)";
      ctx.fillRect(tank.x - 14, terrainAt(tank.x) - 6, 28, 6);
      return;
    }

    const y = tank.y;
    ctx.save();
    ctx.translate(tank.x, y);

    ctx.fillStyle = "rgba(0, 0, 0, 0.34)";
    ctx.beginPath();
    ctx.ellipse(0, 2, 22, 6, 0, 0, Math.PI * 2);
    ctx.fill();

    ctx.fillStyle = "#242827";
    roundedRect(-20, -9, 40, 14, 4);
    ctx.fill();
    ctx.fillStyle = tank.color;
    roundedRect(-17, -15, 34, 13, 4);
    ctx.fill();

    ctx.fillStyle = lighten(tank.color, 0.24);
    ctx.beginPath();
    ctx.arc(0, -16, 9, Math.PI, 0);
    ctx.closePath();
    ctx.fill();

    const angle = (tank.angle * Math.PI) / 180;
    ctx.strokeStyle = "#202323";
    ctx.lineWidth = 7;
    ctx.lineCap = "round";
    ctx.beginPath();
    ctx.moveTo(Math.cos(angle) * 5, -16 - Math.sin(angle) * 5);
    ctx.lineTo(Math.cos(angle) * 25, -16 - Math.sin(angle) * 25);
    ctx.stroke();

    ctx.strokeStyle = lighten(tank.color, 0.38);
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.moveTo(Math.cos(angle) * 5, -16 - Math.sin(angle) * 5);
    ctx.lineTo(Math.cos(angle) * 25, -16 - Math.sin(angle) * 25);
    ctx.stroke();

    ctx.restore();

    drawHealthBar(tank);
  }

  function drawHealthBar(tank) {
    const width = 46;
    const x = tank.x - width / 2;
    const y = tank.y - 42;
    ctx.fillStyle = "rgba(6, 10, 12, 0.72)";
    ctx.fillRect(x, y, width, 6);
    ctx.fillStyle = tank.hp > 60 ? "#70c66f" : tank.hp > 28 ? "#e6bd4f" : "#e85b42";
    ctx.fillRect(x, y, width * clamp(tank.hp / 100, 0, 1), 6);
  }

  function roundedRect(x, y, width, height, radius) {
    const r = Math.min(radius, width / 2, height / 2);
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.lineTo(x + width - r, y);
    ctx.quadraticCurveTo(x + width, y, x + width, y + r);
    ctx.lineTo(x + width, y + height - r);
    ctx.quadraticCurveTo(x + width, y + height, x + width - r, y + height);
    ctx.lineTo(x + r, y + height);
    ctx.quadraticCurveTo(x, y + height, x, y + height - r);
    ctx.lineTo(x, y + r);
    ctx.quadraticCurveTo(x, y, x + r, y);
    ctx.closePath();
  }

  function lighten(hex, amount) {
    const value = Number.parseInt(hex.slice(1), 16);
    const r = clamp(((value >> 16) & 255) + Math.round(255 * amount), 0, 255);
    const g = clamp(((value >> 8) & 255) + Math.round(255 * amount), 0, 255);
    const b = clamp((value & 255) + Math.round(255 * amount), 0, 255);
    return `rgb(${r}, ${g}, ${b})`;
  }

  function drawProjectiles() {
    state.projectiles.forEach((projectile) => {
      ctx.strokeStyle = "rgba(255, 218, 118, 0.45)";
      ctx.lineWidth = 2;
      ctx.beginPath();
      projectile.trail.forEach((point, index) => {
        if (index === 0) {
          ctx.moveTo(point.x, point.y);
        } else {
          ctx.lineTo(point.x, point.y);
        }
      });
      ctx.stroke();

      if (projectile.age >= 0) {
        ctx.fillStyle = "#fff1a8";
        ctx.beginPath();
        ctx.arc(projectile.x, projectile.y, 4, 0, Math.PI * 2);
        ctx.fill();
      }
    });
  }

  function drawEffects() {
    state.flashes.forEach((flash) => {
      ctx.strokeStyle = `rgba(255, 220, 105, ${Math.max(0, flash.life)})`;
      ctx.lineWidth = 4;
      ctx.beginPath();
      ctx.arc(flash.x, flash.y, flash.radius, 0, Math.PI * 2);
      ctx.stroke();
    });

    state.particles.forEach((particle) => {
      ctx.globalAlpha = clamp(particle.life, 0, 1);
      ctx.fillStyle = particle.color;
      ctx.fillRect(particle.x, particle.y, particle.size, particle.size);
      ctx.globalAlpha = 1;
    });
  }

  function drawOverlay() {
    ctx.fillStyle = "rgba(8, 13, 16, 0.68)";
    roundedRect(18, 16, 186, 58, 6);
    ctx.fill();
    ctx.fillStyle = "#f3f0e8";
    ctx.font = "700 18px system-ui, sans-serif";
    ctx.fillText(`Round ${state.round}`, 34, 40);
    ctx.font = "14px system-ui, sans-serif";
    ctx.fillStyle = "#cbd7d8";
    ctx.fillText(state.message, 34, 62);

    const windX = WIDTH - 154;
    const windY = 38;
    ctx.fillStyle = "rgba(8, 13, 16, 0.68)";
    roundedRect(windX - 18, 16, 136, 58, 6);
    ctx.fill();
    ctx.strokeStyle = "#f3f0e8";
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.moveTo(windX + 20, windY);
    ctx.lineTo(windX + 20 + state.wind * 18, windY);
    ctx.stroke();
    ctx.fillStyle = "#f3f0e8";
    ctx.font = "14px system-ui, sans-serif";
    ctx.fillText("Wind", windX + 16, 62);

    if (state.phase === "gameover") {
      ctx.fillStyle = "rgba(8, 13, 16, 0.72)";
      ctx.fillRect(0, 0, WIDTH, HEIGHT);
      ctx.fillStyle = "#f3f0e8";
      ctx.textAlign = "center";
      ctx.font = "800 38px system-ui, sans-serif";
      ctx.fillText(state.message, WIDTH / 2, HEIGHT / 2 - 12);
      ctx.font = "600 18px system-ui, sans-serif";
      ctx.fillStyle = "#ffce72";
      ctx.fillText("New Round", WIDTH / 2, HEIGHT / 2 + 24);
      ctx.textAlign = "left";
    }
  }

  function draw() {
    drawSky();
    drawTerrain();
    state.tanks.forEach(drawTank);
    drawProjectiles();
    drawEffects();
    drawOverlay();
  }

  function frame(now) {
    const delta = clamp((now - lastFrame) / 16.667 || 1, 0.2, 3);
    lastFrame = now;
    updateProjectiles(delta);
    updateParticles(delta);
    draw();
    window.requestAnimationFrame(frame);
  }

  function onControlInput() {
    const tank = activeTank();
    if (tank?.human) {
      tank.angle = Number(angleControl.value);
      tank.power = Number(powerControl.value);
      tank.weapon = weaponControl.value;
    }
    updateReadouts();
  }

  function bindUi() {
    angleControl.addEventListener("input", onControlInput);
    powerControl.addEventListener("input", onControlInput);
    weaponControl.addEventListener("change", onControlInput);
    fireButton.addEventListener("click", fireCurrentTank);
    newRoundButton.addEventListener("click", () => {
      state.round += 1;
      startRound();
    });

    fullscreenButton?.addEventListener("click", () => {
      if (document.fullscreenElement) {
        document.exitFullscreen();
        return;
      }
      stage.requestFullscreen?.();
    });

    window.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        if (!fireButton.disabled && state.phase === "aim") {
          event.preventDefault();
          fireCurrentTank();
        }
      }
    });

    window.addEventListener("error", (event) => {
      const message = event.message || "Runtime error";
      setStatus(message.length > 90 ? `${message.slice(0, 87)}...` : message);
    });
  }

  function initStars() {
    state.stars = Array.from({ length: 30 }, () => ({
      x: randomRange(0, WIDTH),
      y: randomRange(18, 150),
      size: randomRange(1, 2.5),
      alpha: randomRange(0.15, 0.42)
    }));
  }

  bindUi();
  initStars();
  startRound();
  window.requestAnimationFrame(frame);
})();
