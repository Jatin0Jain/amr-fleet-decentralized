/**
 * app.js — AMR Fleet Dashboard Logic
 * [VIBE CODER #1] — WebSocket + Canvas rendering
 *
 * Connects to sim_runner.py WebSocket (ws://localhost:8080)
 * and renders the live fleet state on a Canvas.
 */

'use strict';

// ─────────────────────────────────────────────────────────────
// Constants & Config
// ─────────────────────────────────────────────────────────────

const WS_URL        = 'ws://localhost:8080';
const GRID_SIZE     = 20;
const RECONNECT_MS  = 2000;

/** Color assigned to each robot */
const ROBOT_COLORS = {
  R1: '#6366f1',  // indigo
  R2: '#06b6d4',  // cyan
  R3: '#a855f7',  // purple
};

// ─────────────────────────────────────────────────────────────
// State
// ─────────────────────────────────────────────────────────────

let ws          = null;
let paused      = false;
let startTime   = Date.now();
let tasksCompleted = 0;
let conflictsAvoided = 0;
let scenarioIndex = 1;  // 0=easy,1=medium,2=hard
const SCENARIOS = ['Easy', 'Medium', 'Hard'];

/** Last received fleet state */
let fleetState = {
  robots: [],
  grid: { width: 20, height: 20, obstacles: [] },
  tasks_remaining: 0,
  dead_zones: [],
};

/** Animated robot positions (for smooth glide) */
const robotAnim = {};   // { R1: { x: float, y: float, targetX, targetY } }

// ─────────────────────────────────────────────────────────────
// WebSocket Connection
// ─────────────────────────────────────────────────────────────

function connect() {
  updateConnectionUI('connecting');
  ws = new WebSocket(WS_URL);

  ws.onopen = () => {
    updateConnectionUI('connected');
    addLogEntry('Connected to simulation server', 'complete');
  };

  ws.onmessage = (event) => {
    if (paused) return;
    try {
      const data = JSON.parse(event.data);

      // Handle different message types
      if (data.type === 'fleet_update') {
        handleFleetUpdate(data);
      } else if (data.type === 'event') {
        handleSimEvent(data);
      } else if (data.robot_id) {
        // Single robot state broadcast (also accepted)
        handleSingleRobotUpdate(data);
      }
    } catch (e) {
      console.warn('[Dashboard] Parse error:', e);
    }
  };

  ws.onclose = () => {
    updateConnectionUI('disconnected');
    addLogEntry('Disconnected — retrying in 2s…', 'conflict');
    setTimeout(connect, RECONNECT_MS);
  };

  ws.onerror = () => {
    updateConnectionUI('disconnected');
  };
}

// ─────────────────────────────────────────────────────────────
// Message Handlers
// ─────────────────────────────────────────────────────────────

function handleFleetUpdate(data) {
  fleetState = data;
  if (data.dead_zones) fleetState.dead_zones = data.dead_zones;

  data.robots.forEach(robot => {
    updateRobotCard(robot);
    updateRobotAnim(robot);
    updateNetworkCard(robot);
  });

  updateTopbarMetrics(data);
  // Canvas re-draws every frame via requestAnimationFrame (see render loop below)
}

function handleSingleRobotUpdate(robot) {
  // Update just one robot within fleetState
  const idx = fleetState.robots.findIndex(r => r.robot_id === robot.robot_id);
  if (idx >= 0) fleetState.robots[idx] = robot;
  else fleetState.robots.push(robot);

  updateRobotCard(robot);
  updateRobotAnim(robot);
}

function handleSimEvent(data) {
  const { event_type, robot_id, description } = data;
  const typeMap = {
    conflict:   'conflict',
    reroute:    'reroute',
    complete:   'complete',
    dead_zone:  'deadzone',
  };
  addLogEntry(`[${robot_id}] ${description}`, typeMap[event_type] || '');

  if (event_type === 'conflict') conflictsAvoided++;
  if (event_type === 'complete') tasksCompleted++;
}

// ─────────────────────────────────────────────────────────────
// Robot Cards
// ─────────────────────────────────────────────────────────────

function updateRobotCard(robot) {
  const cardId = `card-${robot.robot_id}`;
  let card = document.getElementById(cardId);
  if (!card) {
    card = document.createElement('div');
    card.id = cardId;
    card.className = 'robot-card';
    document.getElementById('robotCards').appendChild(card);
  }

  card.classList.remove('skeleton');
  const color = ROBOT_COLORS[robot.robot_id] || '#6366f1';
  card.style.setProperty('--robot-color', color);

  const battColor = robot.battery > 40 ? '#22c55e' : robot.battery > 20 ? '#f59e0b' : '#ef4444';
  const taskStr = robot.current_task
    ? `📦 ${robot.current_task.task_id}: (${robot.current_task.pickup}) → (${robot.current_task.dropoff})`
    : 'No task assigned';

  card.innerHTML = `
    <div class="robot-header">
      <span class="robot-id" style="color:${color}">${robot.robot_id}</span>
      <span class="robot-status-badge badge-${robot.status}">${robot.status}</span>
    </div>
    <div class="robot-pos">📍 (${Math.round(robot.position.x)}, ${Math.round(robot.position.y)})</div>
    <div class="battery-bar-wrap">
      <div class="battery-bar-track">
        <div class="battery-bar-fill" style="width:${robot.battery}%;background:${battColor}"></div>
      </div>
      <span class="battery-pct">${Math.round(robot.battery)}%</span>
    </div>
    <div class="robot-task">${taskStr}</div>
  `;
}

// ─────────────────────────────────────────────────────────────
// Smooth Animation
// ─────────────────────────────────────────────────────────────

function updateRobotAnim(robot) {
  const id = robot.robot_id;
  if (!robotAnim[id]) {
    robotAnim[id] = {
      x: robot.position.x,
      y: robot.position.y,
      targetX: robot.position.x,
      targetY: robot.position.y,
    };
  } else {
    robotAnim[id].targetX = robot.position.x;
    robotAnim[id].targetY = robot.position.y;
  }
}

function lerpRobots() {
  const SPEED = 0.15;  // interpolation factor per frame
  for (const id in robotAnim) {
    const a = robotAnim[id];
    a.x += (a.targetX - a.x) * SPEED;
    a.y += (a.targetY - a.y) * SPEED;
  }
}

// ─────────────────────────────────────────────────────────────
// Canvas — Warehouse Map Renderer
// ─────────────────────────────────────────────────────────────

const canvas = document.getElementById('warehouseCanvas');
const ctx    = canvas.getContext('2d');

function resizeCanvas() {
  const wrap = document.getElementById('canvasWrap');
  const size = Math.min(wrap.clientWidth, wrap.clientHeight) - 24;
  canvas.width  = size;
  canvas.height = size;
}

window.addEventListener('resize', resizeCanvas);
resizeCanvas();

function getCellSize() {
  return canvas.width / GRID_SIZE;
}

function render() {
  lerpRobots();
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  const cs = getCellSize();

  drawGrid(cs);
  drawDeadZones(cs);
  drawObstacles(cs);
  drawZoneMarkers(cs);
  drawPaths(cs);
  drawRobots(cs);

  requestAnimationFrame(render);
}

function drawGrid(cs) {
  ctx.strokeStyle = 'rgba(30,45,74,0.5)';
  ctx.lineWidth = 0.5;
  for (let i = 0; i <= GRID_SIZE; i++) {
    ctx.beginPath();
    ctx.moveTo(i * cs, 0);
    ctx.lineTo(i * cs, canvas.height);
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(0, i * cs);
    ctx.lineTo(canvas.width, i * cs);
    ctx.stroke();
  }
}

function drawDeadZones(cs) {
  ctx.fillStyle = 'rgba(239,68,68,0.12)';
  (fleetState.dead_zones || []).forEach(dz => {
    ctx.fillRect(dz.x * cs, dz.y * cs, cs, cs);
  });
}

function drawObstacles(cs) {
  ctx.fillStyle = '#172240';
  (fleetState.grid?.obstacles || []).forEach(obs => {
    ctx.fillRect(obs.x * cs + 1, obs.y * cs + 1, cs - 2, cs - 2);
  });
}

function drawZoneMarkers(cs) {
  // Pickup zones — green diamonds
  const pickups  = [[1,5],[1,14],[17,5],[17,14],[9,0]];
  const dropoffs = [[9,19],[0,9],[19,9],[9,9]];
  const charges  = [[0,0],[0,19],[19,0],[19,19]];

  drawCellMarkers(pickups,  cs, '#22c55e', '⬆');
  drawCellMarkers(dropoffs, cs, '#f59e0b', '⬇');
  drawCellMarkers(charges,  cs, '#6366f1', '⚡');
}

function drawCellMarkers(cells, cs, color, symbol) {
  ctx.fillStyle = color + '33';
  ctx.strokeStyle = color + '88';
  ctx.lineWidth = 1;
  ctx.font = `${Math.max(8, cs * 0.45)}px Inter`;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';

  cells.forEach(([x, y]) => {
    ctx.fillRect(x * cs, y * cs, cs, cs);
    ctx.strokeRect(x * cs + 0.5, y * cs + 0.5, cs - 1, cs - 1);
    ctx.fillStyle = color;
    ctx.fillText(symbol, x * cs + cs / 2, y * cs + cs / 2);
    ctx.fillStyle = color + '33';
  });
}

function drawPaths(cs) {
  fleetState.robots.forEach(robot => {
    if (!robot.planned_path || robot.planned_path.length < 2) return;
    const color = ROBOT_COLORS[robot.robot_id] || '#6366f1';

    ctx.strokeStyle = color + '55';
    ctx.lineWidth = 2;
    ctx.setLineDash([cs * 0.2, cs * 0.15]);
    ctx.beginPath();

    const anim = robotAnim[robot.robot_id];
    if (anim) {
      ctx.moveTo((anim.x + 0.5) * cs, (anim.y + 0.5) * cs);
    }

    robot.planned_path.forEach(([px, py]) => {
      ctx.lineTo((px + 0.5) * cs, (py + 0.5) * cs);
    });
    ctx.stroke();
    ctx.setLineDash([]);
  });
}

function drawRobots(cs) {
  fleetState.robots.forEach(robot => {
    const anim = robotAnim[robot.robot_id];
    if (!anim) return;

    const cx = (anim.x + 0.5) * cs;
    const cy = (anim.y + 0.5) * cs;
    const r  = cs * 0.35;
    const color = ROBOT_COLORS[robot.robot_id] || '#6366f1';

    // Glow effect
    const grd = ctx.createRadialGradient(cx, cy, 0, cx, cy, r * 2);
    grd.addColorStop(0, color + '40');
    grd.addColorStop(1, 'transparent');
    ctx.fillStyle = grd;
    ctx.beginPath();
    ctx.arc(cx, cy, r * 2, 0, Math.PI * 2);
    ctx.fill();

    // Robot circle
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.arc(cx, cy, r, 0, Math.PI * 2);
    ctx.fill();

    // Direction arrow
    const vx = robot.velocity?.vx || 0;
    const vy = robot.velocity?.vy || 0;
    if (vx !== 0 || vy !== 0) {
      ctx.strokeStyle = 'white';
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.moveTo(cx, cy);
      ctx.lineTo(cx + vx * r * 0.9, cy + vy * r * 0.9);
      ctx.stroke();
    }

    // Robot ID label
    ctx.fillStyle = 'white';
    ctx.font = `bold ${Math.max(7, cs * 0.3)}px Inter`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(robot.robot_id, cx, cy);

    // Status ring
    if (robot.status === 'waiting') {
      ctx.strokeStyle = '#f59e0b';
      ctx.lineWidth = 2;
      ctx.setLineDash([3, 3]);
      ctx.beginPath();
      ctx.arc(cx, cy, r + 4, 0, Math.PI * 2);
      ctx.stroke();
      ctx.setLineDash([]);
    } else if (robot.status === 'blocked') {
      ctx.strokeStyle = '#ef4444';
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.arc(cx, cy, r + 4, 0, Math.PI * 2);
      ctx.stroke();
    }
  });
}

// ─────────────────────────────────────────────────────────────
// Top Bar Metrics
// ─────────────────────────────────────────────────────────────

function updateTopbarMetrics(data) {
  document.getElementById('metricTasksDone').textContent = tasksCompleted;
  document.getElementById('metricConflicts').textContent = conflictsAvoided;

  const eff = conflictsAvoided > 0
    ? `+${Math.min(99, Math.round((conflictsAvoided / (conflictsAvoided + 1)) * 100))}%`
    : '—';
  document.getElementById('metricEfficiency').textContent = eff;
}

function updateUptime() {
  const elapsed = Math.floor((Date.now() - startTime) / 1000);
  const m = String(Math.floor(elapsed / 60)).padStart(2, '0');
  const s = String(elapsed % 60).padStart(2, '0');
  document.getElementById('metricUptime').textContent = `${m}:${s}`;
}

setInterval(updateUptime, 1000);

// ─────────────────────────────────────────────────────────────
// Network Cards
// ─────────────────────────────────────────────────────────────

function updateNetworkCard(robot) {
  const el = document.getElementById(`latR${robot.robot_id.slice(1)}`);
  if (!el) return;
  const latency = Math.round(Math.random() * 4 + 1);  // TODO: real latency from network_model
  el.textContent = `${latency}ms`;
}

// ─────────────────────────────────────────────────────────────
// Event Log
// ─────────────────────────────────────────────────────────────

const MAX_LOG_ENTRIES = 50;

function addLogEntry(text, type = '') {
  const log = document.getElementById('eventLog');
  const placeholder = log.querySelector('.log-placeholder');
  if (placeholder) placeholder.remove();

  const entry = document.createElement('div');
  entry.className = `log-entry ${type}`;
  const time = new Date().toLocaleTimeString('en', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
  entry.textContent = `${time}  ${text}`;
  log.prepend(entry);

  // Keep log trimmed
  while (log.children.length > MAX_LOG_ENTRIES) {
    log.removeChild(log.lastChild);
  }
}

// ─────────────────────────────────────────────────────────────
// Task List
// ─────────────────────────────────────────────────────────────

function updateTaskList(tasks) {
  const list = document.getElementById('taskList');
  list.innerHTML = '';
  if (!tasks || tasks.length === 0) {
    list.innerHTML = '<p class="log-placeholder">No active tasks</p>';
    return;
  }
  tasks.forEach(task => {
    const item = document.createElement('div');
    item.className = 'task-item';
    item.innerHTML = `
      <span class="task-id">${task.task_id}</span>
      <span class="task-assignee">${task.assignee || 'Unassigned'}</span>
    `;
    list.appendChild(item);
  });
}

// ─────────────────────────────────────────────────────────────
// UI Controls
// ─────────────────────────────────────────────────────────────

function togglePause() {
  paused = !paused;
  const btn = document.getElementById('btnPause');
  btn.textContent = paused ? '▶ Resume' : '⏸ Pause';
  addLogEntry(paused ? 'Simulation paused' : 'Simulation resumed', '');
}

function cycleScenario() {
  scenarioIndex = (scenarioIndex + 1) % 3;
  document.getElementById('scenarioLabel').textContent = SCENARIOS[scenarioIndex];
  addLogEntry(`Switched to ${SCENARIOS[scenarioIndex]} scenario`, '');
}

// ─────────────────────────────────────────────────────────────
// Connection Status UI
// ─────────────────────────────────────────────────────────────

function updateConnectionUI(state) {
  const dot  = document.getElementById('statusDot');
  const text = document.getElementById('statusText');
  dot.className = `status-dot ${state}`;
  const labels = { connected: 'Live', disconnected: 'Disconnected', connecting: 'Connecting…' };
  text.textContent = labels[state] || state;
}

// ─────────────────────────────────────────────────────────────
// Boot
// ─────────────────────────────────────────────────────────────

connect();
requestAnimationFrame(render);
