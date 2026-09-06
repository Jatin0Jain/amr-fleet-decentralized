# 📋 TASKS.md — Who Does What

> Quick coordination reference for the 2-day sprint.
> **Legend**: ✅ Done — no changes needed | 🟡 Fill stubs | 🔴 Write from scratch

---

## 🧮 DSA Person

### `core/grid.py` — 🟡 Fill 3 stubs

| Method | Line | What to write |
|--------|------|---------------|
| `reserve_cell()` | 71 | Store `{robot_id, expires_at}` in `self.reservations[(x,y)]`. Return `False` if another robot already holds it. |
| `clear_reservations()` | 85 | Remove every entry in `self.reservations` where `robot_id` matches. |
| `is_passable()` | 98 | Return `True` only if: in-bounds + not obstacle + not reserved by a different robot. |

> Everything else in `grid.py` is already written. Do **not** touch the other methods.

---

### `core/pathfinder.py` — 🟡 Fill 1 stub

| Method | Line | What to write |
|--------|------|---------------|
| `astar()` | 18 | Standard A* using `heapq`. Skip cells where `grid.is_passable()` is False. Add `congestion_weights.get(cell, 0)` to the cost. Full pseudocode is in the comments. |

---

### `core/conflict.py` — 🟡 Fill 3 stubs

| Method | Line | What to write |
|--------|------|---------------|
| `resolve_head_on()` | 70 | Detect if two robots want the same next cell (or are swapping). Lower battery = higher priority = other robot waits. |
| `detect_deadlock()` | 110 | Build a "who is waiting for who" graph. Find cycles (DFS). Return robot_ids in the cycle. |
| `should_reroute()` | 135 | Return `True` if `time.time() - robot.blocked_since > 3.0` and robot is stuck. |

> `resolve()` at the top of the file (the orchestrator) is already written — it calls your 3 methods.

---

### `core/robot_agent.py` — 🟡 Fill 1 stub

| Method | Line | What to write |
|--------|------|---------------|
| `step()` | 145 | Per-tick logic: get action from resolver → move/wait/reroute accordingly → update battery → check if arrived at pickup/dropoff. Full pseudocode in comments. |

> `__init__`, `assign_task`, `_replan`, `next_cell`, `to_json` are all **already written**.

---

### `tests/test_core.py` — ✅ Done

Run your tests after every method you implement:
```bash
python -m pytest tests/test_core.py -v
```

---

## 🤖 ML Person

### `ml/task_allocator.py` — ✅ Greedy done | 🟡 ML mode (Day 2)

| Method | Line | What to write |
|--------|------|---------------|
| `_allocate_ml()` | 107 | Day 2 only. Use `compute_score()` for each (robot, task) pair, pick minimum cost assignment. |
| `compute_score()` | 123 | Already written — just tune the weights if needed. |

> `allocate()`, `_allocate_greedy()`, `reallocate_on_block()` are all **done**.

---

### `ml/congestion_model.py` — 🟡 Fill 1 stub

| Method | Line | What to write |
|--------|------|---------------|
| `_train()` | 95 | `train_test_split` → fit `RandomForestClassifier` → `joblib.dump`. ~10 lines. |

> `train_from_log()`, `predict_congestion()`, `_heuristic_congestion()`, `_extract_features()` are all **done**.

**Generate training data first:**
```bash
# Run a short simulation (even with stub robots) to produce data/sim_log.jsonl
# Then call: predictor.train_from_log("data/sim_log.jsonl")
```

### `ml/data_logger.py` — ✅ Done

---

## 🔌 P2P / Simulation Person (use Claude/ChatGPT for these)

### `network/robot_node.py` — 🔴 Write 4 methods

| Method | Line | What to write |
|--------|------|---------------|
| `run()` | 75 | `asyncio.gather(_serve(), _connect_to_peers(), _broadcast_loop(), _connect_dashboard())` |
| `_serve()` | 98 | `websockets.serve()` on `self.port`. On message: parse JSON, store in `self.peer_states`, call `on_message`. |
| `_connect_to_peers()` | 118 | Loop over `self.peer_urls`, `websockets.connect()`, store connection. Retry on disconnect. |
| `_broadcast_loop()` | 133 | Every 200ms: `await conn.send(self._current_state_json)` to all connections. |

**AI Prompt to use:**
> *"Write Python asyncio WebSocket P2P where each node is both a server (listening on its port) and a client (connecting to peer ports). Every 200ms broadcast a JSON string to all connected peers. Handle reconnection. Use the `websockets` library."*

---

### `simulation/sim_runner.py` — 🔴 Write 1 method

| Method | Line | What to write |
|--------|------|---------------|
| `simulation_loop()` | 52 | The main game loop. Each tick: call `resolver.resolve()` → `robot.step()` for all robots → `allocator.allocate()` → `broadcast_to_dashboard()` → `logger.log_tick()` → `asyncio.sleep(1/fps)`. Full pseudocode in comments. |

> `main()`, `dashboard_server()`, `broadcast_to_dashboard()` are all **done**.

---

## 🖥️ UI Person (Vibe Coder #1)

### `dashboard/app.js` — ✅ Mostly done | 🟡 Polish

| Task | What to do |
|------|-----------|
| Real latency display | Replace fake `Math.random()` on line ~210 with actual `network_model` data from the WebSocket message |
| Task list update | Call `updateTaskList(data.tasks)` inside `handleFleetUpdate()` |
| Performance chart | Draw two bars on `#perfCanvas` — smart routing time vs stop-and-wait time (from `benchmark_results.json`) |
| Smooth animations | Already implemented via `lerpRobots()`. Tune the `SPEED = 0.15` constant if movement feels too slow/fast. |

### `dashboard/index.html` — ✅ Done
### `dashboard/style.css` — ✅ Done

---

## ⚡ Electronics / Hardware Person

### `environment/battery_model.py` — ✅ Done
### `environment/sensor_model.py` — ✅ Done
### `environment/network_model.py` — ✅ Done
### `environment/warehouse_layout.py` — ✅ Done
### `environment/scenario_generator.py` — ✅ Done

### Additional tasks (Day 2)

| Task | File to create | What to write |
|------|---------------|---------------|
| Hardware spec | `docs/hardware_spec.md` | Raspberry Pi 4 specs, sensor list, power budget |
| Deployment guide | `docs/raspberry_pi_deployment.md` | Step-by-step to run the code on a real Pi |
| Edge performance | `docs/edge_performance.md` | CPU/RAM usage measurements from the simulation |

---

## 🔗 Integration Order (Day 2 Morning)

```
Step 1: DSA finishes robot_agent.py ──────────────────┐
Step 2: P2P runs sim_runner.py with real robots ───────┤
Step 3: ML allocator connected to sim_runner ──────────┤
Step 4: Hardware models injected into robot_agent ─────┤
Step 5: Dashboard WebSocket connected to sim_runner ────┘
Step 6: Full system test — all robots moving + dashboard live
```

---

## ✅ Completion Checklist

```
[ ] core/grid.py         — DSA: 3 stubs done
[ ] core/pathfinder.py   — DSA: astar() done
[ ] core/conflict.py     — DSA: 3 stubs done
[ ] core/robot_agent.py  — DSA: step() done
[ ] python -m pytest tests/test_core.py  — All tests pass

[ ] ml/congestion_model.py   — ML: _train() done
[ ] ml/task_allocator.py     — ML: ML mode done (Day 2)

[ ] network/robot_node.py    — P2P: WebSocket working
[ ] simulation/sim_runner.py — P2P: loop running, dashboard receiving data

[ ] dashboard live with 3 robots moving
[ ] battery bars draining in real time
[ ] conflict event shows in event log

[ ] benchmark_results.json shows ≥20% improvement
[ ] docs/raspberry_pi_deployment.md written
[ ] 5-minute demo recorded
```
