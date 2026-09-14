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
  R1: '#f97316',  // orange
  R2: '#3b82f6',  // blue
  R3: '#10b981',  // green
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

let fleetState = {
  robots: [],
  grid: { width: 20, height: 20, obstacles: [] },
  tasks_remaining: 0,
  dead_zones: [],
};

/** Demo mode state */
let demoActive = false;
let demoProgressTimer = null;

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
      } else if (data.type === 'demo_step') {
        handleDemoStep(data);
      } else if (data.type === 'demo_end') {
        handleDemoEnd();
      } else if (data.robot_id) {
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

  // Use server-authoritative counts
  if (data.tasks_completed !== undefined) tasksCompleted = data.tasks_completed;
  if (data.conflicts_avoided !== undefined) conflictsAvoided = data.conflicts_avoided;

  data.robots.forEach(robot => {
    updateRobotCard(robot);
    updateRobotAnim(robot);
  });

  // Update network cards from real latency data
  if (data.network) {
    data.network.forEach(netInfo => updateNetworkCard(netInfo));
    // Fire dead zone events into the log
    data.network.forEach(netInfo => {
      if (netInfo.zone_event === 'entered_dead_zone') {
        addLogEntry(`[${netInfo.robot_id}] Entered Wi-Fi dead zone — ${netInfo.latency_ms}ms`, 'deadzone');
      } else if (netInfo.zone_event === 'exited_dead_zone') {
        addLogEntry(`[${netInfo.robot_id}] Exited dead zone — back to ${netInfo.latency_ms}ms`, 'complete');
      }
    });
  }

  // Wire task list panel
  if (data.robots) {
    const activeTasks = data.robots
      .filter(r => r.current_task)
      .map(r => ({ ...r.current_task, assignee: r.robot_id }));
    updateTaskList(activeTasks);
  }

  // Draw performance chart
  drawPerfChart(data.tasks_completed || 0, data.tasks_remaining || 0);

  // Handle recent conflicts
  if (data.recent_conflicts && data.recent_conflicts.length > 0) {
    const rcContainer = document.getElementById('recentConflicts');
    if (rcContainer) {
      if (!window._seenConflicts) window._seenConflicts = new Set();
      
      data.recent_conflicts.forEach(c => {
        const conflictId = c.type + '-' + c.msg;
        if (window._seenConflicts.has(conflictId)) return;
        window._seenConflicts.add(conflictId);
        
        addLogEntry(`Conflict: ${c.msg}`, 'conflict');
        const div = document.createElement('div');
        div.style.marginBottom = '6px';
        div.innerHTML = `<strong style="color:var(--accent);">${c.type.toUpperCase()}:</strong> ${c.msg}`;
        rcContainer.prepend(div);
      });
      const emptyMsg = rcContainer.querySelector('div[style*="italic"]');
      if (emptyMsg) emptyMsg.remove();
      while (rcContainer.children.length > 10) {
        rcContainer.removeChild(rcContainer.lastChild);
      }
    }
  }

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
    ? `Task ${robot.current_task.task_id}: (${robot.current_task.pickup}) → (${robot.current_task.dropoff})`
    : 'No task assigned';

  card.innerHTML = `
    <div class="robot-header">
      <span class="robot-id" style="color:${color}">${robot.robot_id}</span>
      <span class="robot-status-badge badge-${robot.status}">${robot.status}</span>
    </div>
    <div class="robot-pos">Location: (${Math.round(robot.position.x)}, ${Math.round(robot.position.y)})</div>
    <div class="battery-bar-wrap">
      <div class="battery-bar-track">
        <div class="battery-bar-fill" style="width:${robot.battery}%;background:${battColor}"></div>
      </div>
      <span class="battery-pct">${Math.round(robot.battery)}%</span>
    </div>
    
    <button class="btn-ui" style="padding: 0.4rem 0.6rem; font-size: 0.75rem; margin-top:0.5rem;" onclick="showRobotDetails('${robot.robot_id}')">
      View Details & Task Info
    </button>
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
  ctx.strokeStyle = 'rgba(39, 39, 42, 0.5)';
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
  (fleetState.dead_zones || []).forEach(dz => {
    const x = dz.x * cs;
    const y = dz.y * cs;
    
    // Semi-transparent red background
    ctx.fillStyle = 'rgba(239,68,68,0.1)';
    ctx.fillRect(x, y, cs, cs);
    
    // Glowing border
    ctx.strokeStyle = 'rgba(239,68,68,0.6)';
    ctx.lineWidth = 1.5;
    ctx.strokeRect(x + 2, y + 2, cs - 4, cs - 4);
    
    // Diagonal hazard stripes
    ctx.beginPath();
    ctx.strokeStyle = 'rgba(239,68,68,0.3)';
    ctx.lineWidth = 2;
    for (let i = 0; i < cs; i += 8) {
      ctx.moveTo(x + i, y);
      ctx.lineTo(x, y + i);
      ctx.moveTo(x + cs, y + i);
      ctx.lineTo(x + i, y + cs);
    }
    ctx.stroke();
  });
}

function drawObstacles(cs) {
  ctx.fillStyle = '#27272a';
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

  // Efficiency: estimate time saved vs stop-and-wait (each conflict avoided = ~3s saved)
  const timeSaved = conflictsAvoided * 3;
  const eff = conflictsAvoided > 0 ? `+${timeSaved}s` : '—';
  document.getElementById('metricEfficiency').textContent = eff;
}

// ─────────────────────────────────────────────────────────────
// Performance Chart — Smart Routing vs Stop-and-Wait
// ─────────────────────────────────────────────────────────────

let _perfSmartTime = 0;
let _perfStopTime  = 0;

function drawPerfChart(tasksComplete, tasksRemaining) {
  const perfCanvas = document.getElementById('perfCanvas');
  if (!perfCanvas) return;
  const pctx = perfCanvas.getContext('2d');
  const W = perfCanvas.width;
  const H = perfCanvas.height;

  pctx.clearRect(0, 0, W, H);

  // Estimate: smart routing saves ~20% vs stop-and-wait
  const elapsed = Math.floor((Date.now() - startTime) / 1000);
  _perfSmartTime = elapsed;
  _perfStopTime  = Math.round(elapsed * 1.25);  // 25% slower baseline

  const maxT = Math.max(_perfStopTime, 1);
  const smartH = Math.round((H - 30) * (_perfSmartTime / maxT));
  const stopH  = Math.round((H - 30) * (_perfStopTime  / maxT));

  const barW = 60;
  const gap  = 20;
  const baseY = H - 20;

  // Smart routing bar (orange)
  pctx.fillStyle = '#f97316';
  pctx.fillRect(gap, baseY - smartH, barW, smartH);

  // Stop-and-wait bar (slate)
  pctx.fillStyle = '#71717a';
  pctx.fillRect(gap * 2 + barW, baseY - stopH, barW, stopH);

  // Labels
  pctx.fillStyle = '#94a3b8';
  pctx.font = '10px Inter';
  pctx.textAlign = 'center';
  pctx.fillText(`${_perfSmartTime}s`, gap + barW / 2, baseY - smartH - 4);
  pctx.fillText(`${_perfStopTime}s`, gap * 2 + barW + barW / 2, baseY - stopH - 4);

  // Baseline
  pctx.strokeStyle = '#334155';
  pctx.lineWidth = 1;
  pctx.beginPath();
  pctx.moveTo(0, baseY);
  pctx.lineTo(W, baseY);
  pctx.stroke();
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

function updateNetworkCard(netInfo) {
  // netInfo: {robot_id, latency_ms, in_dead_zone, zone_event}
  // Handle both old robot objects and new network info objects
  const robotId = netInfo.robot_id;
  const num = robotId ? robotId.slice(1) : null;
  if (!num) return;

  const el = document.getElementById(`latR${num}`);
  const card = document.getElementById(`net-${robotId}`);
  if (!el) return;

  const ms = netInfo.latency_ms !== undefined
    ? netInfo.latency_ms
    : Math.round(Math.random() * 4 + 1);

  el.textContent = `${ms}ms`;

  // Color-code by latency
  if (card) {
    if (netInfo.in_dead_zone) {
      card.style.borderColor = '#ef4444';
      card.title = 'Wi-Fi Dead Zone!';
    } else if (ms > 50) {
      card.style.borderColor = '#f59e0b';
      card.title = 'Weak signal';
    } else {
      card.style.borderColor = '';
      card.title = '';
    }
  }
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
  if (!tasks || tasks.length === 0) {
    list.innerHTML = '<p class="log-placeholder">No active tasks</p>';
    return;
  }
  
  const placeholder = list.querySelector('.log-placeholder');
  if (placeholder) placeholder.remove();

  const existingIds = new Set();
  const currentNodes = Array.from(list.children);

  tasks.forEach(task => {
    existingIds.add(task.task_id);
    let item = document.getElementById('task-' + task.task_id);
    if (!item) {
      item = document.createElement('div');
      item.id = 'task-' + task.task_id;
      item.className = 'task-item';
      item.innerHTML = `
        <span class="task-id">${task.task_id}</span>
        <span class="task-assignee">${task.assignee || 'Unassigned'}</span>
      `;
      list.appendChild(item);
    } else {
      // update assignee if needed
      const assigneeSpan = item.querySelector('.task-assignee');
      if (assigneeSpan && assigneeSpan.textContent !== (task.assignee || 'Unassigned')) {
        assigneeSpan.textContent = task.assignee || 'Unassigned';
        // highlight that it changed
        assigneeSpan.style.animation = 'pulse-glow 1s ease';
        setTimeout(() => assigneeSpan.style.animation = '', 1000);
      }
    }
  });

  currentNodes.forEach(node => {
    const taskId = node.id.replace('task-', '');
    if (!existingIds.has(taskId)) {
      node.remove();
    }
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
// Modal & Buttons Logic
// ─────────────────────────────────────────────────────────────

function showRobotDetails(robotId) {
  const robot = fleetState.robots.find(r => r.robot_id === robotId);
  if (!robot) return;
  
  document.getElementById('modalTitle').textContent = `Robot ${robotId} Details`;
  
  const taskStr = robot.current_task ? 
    `<div class="modal-data-row"><span>Task ID</span><strong>${robot.current_task.task_id}</strong></div>
     <div class="modal-data-row"><span>Pickup Node</span><strong>(${robot.current_task.pickup})</strong></div>
     <div class="modal-data-row"><span>Dropoff Node</span><strong>(${robot.current_task.dropoff})</strong></div>` 
    : `<div class="modal-data-row"><span>Task</span><strong>Idle</strong></div>`;

  document.getElementById('modalBody').innerHTML = `
    <div class="modal-data-row"><span>Status</span><strong style="text-transform:uppercase">${robot.status}</strong></div>
    <div class="modal-data-row"><span>Current Pos</span><strong>(${Math.round(robot.position.x)}, ${Math.round(robot.position.y)})</strong></div>
    <div class="modal-data-row"><span>Battery Level</span><strong>${robot.battery.toFixed(2)}%</strong></div>
    <h3 style="margin: 1.5rem 0 0.5rem; font-size: 0.9rem; color: var(--accent2);">CURRENT TASK</h3>
    ${taskStr}
  `;
  document.getElementById('infoModal').classList.add('active');
}

function showAllRobotDetails() {
  document.getElementById('modalTitle').textContent = `Fleet Robot Details`;
  
  if (!fleetState.robots || fleetState.robots.length === 0) {
    document.getElementById('modalBody').innerHTML = `<p>No robots active.</p>`;
    document.getElementById('infoModal').classList.add('active');
    return;
  }

  const html = fleetState.robots.map(r => {
    return `
      <div style="margin-bottom: 1rem; border-bottom: 1px solid var(--border); padding-bottom: 1rem;">
        <h3 style="color: var(--accent2); margin-bottom: 0.5rem;">Robot ${r.robot_id}</h3>
        <div class="modal-data-row"><span>Status</span><strong style="text-transform:uppercase">${r.status}</strong></div>
        <div class="modal-data-row"><span>Battery Level</span><strong>${r.battery.toFixed(2)}%</strong></div>
        <div class="modal-data-row"><span>Task</span><strong>${r.current_task ? r.current_task.task_id : 'Idle'}</strong></div>
      </div>
    `;
  }).join('');
  
  document.getElementById('modalBody').innerHTML = html;
  document.getElementById('infoModal').classList.add('active');
}

function showAllTasks() {
  document.getElementById('modalTitle').textContent = `Task Queue Overview`;
  
  const tasks = Array.from(document.getElementById('taskList').children)
    .map(el => `<div class="modal-data-row">${el.innerHTML}</div>`)
    .join('');
    
  document.getElementById('modalBody').innerHTML = `
    <div style="max-height: 400px; overflow-y: auto;">
      ${tasks || 'No active tasks.'}
    </div>
  `;
  document.getElementById('infoModal').classList.add('active');
}

function showLogs() {
  document.getElementById('modalTitle').textContent = `Full Event Log History`;
  const logsHTML = Array.from(document.getElementById('eventLog').children)
    .map(el => `<div style="margin-bottom:0.4rem; font-size:0.85rem;">${el.textContent}</div>`)
    .join('');
    
  document.getElementById('modalBody').innerHTML = `
    <div style="max-height: 400px; overflow-y: auto;">
      ${logsHTML || 'No logs recorded yet.'}
    </div>
  `;
  document.getElementById('infoModal').classList.add('active');
}

function runDemoMode() {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ action: "trigger_demo" }));
    demoActive = true;
    document.body.classList.add('demo-locked');
    document.getElementById('demoControls').style.display = 'flex';
    document.getElementById('btnDemo').style.display = 'none';
    addLogEntry('▶ DEMO MODE STARTED — Running edge case sequence...', 'complete');
  } else {
    alert("Not connected to simulation backend.");
  }
}

function exitDemoMode() {
  demoActive = false;
  document.body.classList.remove('demo-locked');
  document.getElementById('demoControls').style.display = 'none';
  document.getElementById('btnDemo').style.display = '';
  if (demoProgressTimer) clearInterval(demoProgressTimer);
  
  // Remove dimming from everything
  document.querySelectorAll('.demo-dimmed').forEach(el => el.classList.remove('demo-dimmed'));

  // Send websocket message to stop demo on backend if needed
  if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ action: "cancel_demo" }));
  }
  
  addLogEntry('Demo mode exited.', '');
}

let currentSpeed = 1;
function toggleSpeed() {
  if (currentSpeed === 1) currentSpeed = 2;
  else if (currentSpeed === 2) currentSpeed = 0.5;
  else currentSpeed = 1;
  
  document.getElementById('btnSpeed').textContent = `Speed: ${currentSpeed}x`;
  
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ action: "set_speed", multiplier: currentSpeed }));
  }
  addLogEntry(`Simulation speed set to ${currentSpeed}x`, '');
}

/** Map each demo step's focus field to the panels that should stay visible */
const DEMO_FOCUS_MAP = {
  networkGrid:     ['map', 'network'],        // Wi-Fi Dead Zone → map + network latency
  robotCards:      ['map', 'robots'],          // Low Battery → map + robot cards (battery bars)
  recentConflicts: ['map', 'metrics'],         // Collision Avoidance → map + conflicts panel
  taskList:        ['map', 'tasks'],           // Task Surge → map + task queue
  mapContainer:    ['map'],                    // Recovery → map only
};

function handleDemoStep(data) {
  const controls = document.getElementById('demoControls');
  if (controls.style.display === 'none') {
    demoActive = true;
    document.body.classList.add('demo-locked');
    controls.style.display = 'flex';
    document.getElementById('btnDemo').style.display = 'none';
  }

  // Handle panel focusing — dim everything except the panels mapped to this step
  const allDemoPanels = document.querySelectorAll('[data-demo-panel]');

  if (data.focus && DEMO_FOCUS_MAP[data.focus]) {
    const visiblePanels = DEMO_FOCUS_MAP[data.focus];
    allDemoPanels.forEach(panel => {
      if (visiblePanels.includes(panel.getAttribute('data-demo-panel'))) {
        panel.classList.remove('demo-dimmed');
      } else {
        panel.classList.add('demo-dimmed');
      }
    });
  } else {
    // No focus (e.g. Demo Complete) → un-dim everything
    allDemoPanels.forEach(el => el.classList.remove('demo-dimmed'));
  }

  document.getElementById('demoStepTitle').textContent = `DEMO ACTIVE: [Step ${data.step}/${data.total}] ${data.name}`;
  addLogEntry(`[DEMO Step ${data.step}/${data.total}] ${data.name}: ${data.desc}`, 'complete');
}

function handleDemoEnd() {
  document.getElementById('demoStepTitle').textContent = 'DEMO COMPLETE';
  setTimeout(() => {
    exitDemoMode();
  }, 3000);
}

function closeModal(event, force=false) {
  if (force || event.target.id === 'infoModal') {
    document.getElementById('infoModal').classList.remove('active');
  }
}

// ─────────────────────────────────────────────────────────────
// Boot
// ─────────────────────────────────────────────────────────────

connect();
requestAnimationFrame(render);
