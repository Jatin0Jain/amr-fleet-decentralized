# 🤖 AMR Fleet — Implementation Plan
## 2-Day Sprint for Decentralized Coordination Framework

---

> **Team Size**: 5 people | **Duration**: 48 hours | **Stack**: Python simulation, WebSockets (P2P), Web UI

---

## 🗺️ Big Picture: How Everything Comes Together

```
┌──────────────────────────────────────────────────────────────────────┐
│                          THE FULL SYSTEM                             │
│                                                                      │
│  ┌─────────────┐    WebSocket P2P     ┌─────────────┐               │
│  │   Robot A   │◄────────────────────►│   Robot B   │               │
│  │ (Python     │                      │ (Python     │               │
│  │  process)   │◄──────────────────►  │  process)   │               │
│  └──────┬──────┘    Broadcast msgs    └──────┬──────┘               │
│         │                                    │                       │
│         └───────────────┬────────────────────┘                      │
│                         │                                            │
│                  ┌──────▼──────┐                                     │
│                  │   Robot C   │                                     │
│                  └──────┬──────┘                                     │
│                         │                                            │
│         All robots emit JSON state via WebSocket                     │
│                         │                                            │
│                  ┌──────▼───────────────┐                           │
│                  │   Fleet Dashboard    │                            │
│                  │  (Browser UI)        │                            │
│                  │  - Live positions    │                            │
│                  │  - Battery status    │                            │
│                  │  - Path overlays     │                            │
│                  └──────────────────────┘                            │
└──────────────────────────────────────────────────────────────────────┘
```

### Integration Contract — Shared JSON Schema

Every robot broadcasts this JSON message every 200ms:
```json
{
  "robot_id": "R1",
  "position": {"x": 5, "y": 3},
  "velocity": {"vx": 0, "vy": 1},
  "planned_path": [[5,3],[5,4],[5,5],[6,5]],
  "current_task": {"task_id": "T12", "pickup": [2,2], "dropoff": [8,8]},
  "battery": 87,
  "status": "moving",
  "timestamp": 1728000000.123
}
```

> ⚠️ **This JSON schema is the integration glue. Everyone must use it from Day 1.**

---

## 📅 Master Timeline

```
DAY 1
├── 09:00 AM  ALL: Agree on JSON schema (15 min standup)
├── 09:15 AM  ALL: Clone shared repo, create folder structure
├── 09:30 AM  Everyone starts their Day 1 work
├── 01:00 PM  CHECKPOINT: Quick sync — any blockers? (15 min)
├── 06:00 PM  DSA: grid.py + pathfinder.py done
│             ML: task_allocator.py (greedy) done
│             P2P: robot_node.py (AI-generated) done
│             UI: Dashboard layout + canvas done
│             HW: battery_model.py done
└── 11:00 PM  Everyone commits. Sleep!

DAY 2
├── 09:00 AM  ALL: Integration standup
├── 09:30 AM  P2P: runs sim_runner.py with stub robots
├── 10:00 AM  DSA + P2P: real robots in simulation
├── 11:00 AM  ML + DSA: integrate task allocator
├── 12:00 PM  UI: dashboard connected to live simulation
├── 01:00 PM  HW: inject battery + sensor models
├── 02:00 PM  FULL SYSTEM TEST: all components running
├── 03:00 PM  Bug fixes + polish
├── 04:00 PM  Record demo video
├── 05:00 PM  Slides finalized
└── 06:00 PM  🎉 DONE!
```

---

## 👥 Person-by-Person Plan

---

## 🧮 Person 1 — DSA Expert
### Path Planning Engine + Conflict Resolution Core

### DAY 1

**Step 1: Set Up (30 min)**
```bash
pip install pygame numpy
```

**Step 2: `core/grid.py` — Reservation system (1 hr)**
Implement 3 methods:
- `reserve_cell(x, y, robot_id, duration)` — claim a cell for X seconds
- `clear_reservations(robot_id)` — release all of a robot's claims
- `is_passable(x, y, robot_id)` — check if a cell can be entered

**Step 3: `core/pathfinder.py` — A* (3 hrs)**
Standard A* on the grid. Key addition: check `grid.is_passable()` to avoid reserved cells. Add `congestion_weights` parameter for ML integration.

**Step 4: `core/conflict.py` — 3 strategies (3 hrs)**
- **Priority wait**: lower battery = higher priority
- **Deadlock detection**: find circular waits using DFS on wait-for graph
- **Re-route trigger**: if blocked >3s, call A* again

### DAY 2

**Step 5: `core/robot_agent.py` — `step()` (2 hrs)**
Per-tick logic: get action → move/wait/reroute → update battery → check task completion

**Step 6: Run tests (1 hr)**
```bash
python -m pytest tests/test_core.py -v
```

**Step 7: Benchmark (1 hr)**
Run 100 tasks with conflict resolution ON vs OFF. Save `benchmark_results.json`. Must show ≥20% improvement.

---

## 🤖 Person 2 — ML Expert
### Intelligent Task Allocator + Congestion Predictor

### DAY 1

**Step 1: Set Up (30 min)**
```bash
pip install scikit-learn numpy pandas joblib
```

**Step 2: Understand greedy allocator (1 hr)**
`ml/task_allocator.py` greedy mode is already done. Read and understand `_allocate_greedy()` and `compute_score()`.

**Step 3: Generate training data (2 hrs)**
Run short simulations to produce `data/sim_log.jsonl` via `DataLogger`. Each line = one tick with all robot positions.

**Step 4: Train congestion model (3 hrs)**
Implement `_train()` in `ml/congestion_model.py`:
```python
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2)
self.model = RandomForestClassifier(n_estimators=100, random_state=42)
self.model.fit(X_train, y_train)
joblib.dump(self.model, MODEL_PATH)
```

### DAY 2

**Step 5: Connect congestion to A* (1 hr)**
Pass `predictor.predict_congestion()` output as `congestion_weights` to `astar()`.

**Step 6: Dynamic re-allocation (2 hrs)**
`reallocate_on_block()` is already stubbed — implement it (very similar to greedy).

**Step 7: Benchmark allocator (1 hr)**
Compare random vs greedy vs ML. Save `ml/allocation_benchmark.json`.

---

## 🔌 Person 3 — P2P / Simulation (AI-Assisted)
### Communication Network + Simulation Orchestrator

> ✅ You do NOT need ROS. Use Python WebSockets.

### DAY 1

**Step 1: Set Up (30 min)**
```bash
pip install websockets
```

**Step 2: Generate `robot_node.py` with AI (2 hrs)**

Paste this into Claude/ChatGPT:
```
Write a Python asyncio WebSocket P2P network where:
- Each node runs a WebSocket SERVER on a unique port (R1=8001, R2=8002, R3=8003)
- Each node also acts as a CLIENT connecting to all OTHER nodes
- Every 200ms, broadcast a JSON string to all connected peers
- On receive: call on_message(sender_id, data) callback
- Handle reconnection if a peer goes offline
- Use Python asyncio and websockets library
```

**Step 3: `simulation/sim_runner.py` — simulation loop (3 hrs)**
Main loop: tick all robots → resolve conflicts → allocate tasks → broadcast to dashboard → sleep

### DAY 2

**Step 4: Integration (4 hrs)**
Connect everything. Run:
```bash
python simulation/sim_runner.py --scenario medium
```
Verify dashboard at `http://localhost:8080` receives JSON.

**Step 5: Test stability (2 hrs)**
Run for 5 minutes without crashes. Check `network/comm_log.txt`.

---

## 💻 Person 4 — Vibe Coder #1
### Fleet Dashboard UI

### DAY 1

Dashboard is mostly pre-built. Focus on:
- Polish the Canvas robot animation (tune `SPEED` constant in `app.js`)
- Add real task list updates in `handleFleetUpdate()`
- Test with mock data by opening `dashboard/index.html` directly

### DAY 2

- Connect to live simulation WebSocket
- Add performance chart (smart vs stop-and-wait bars)
- Record 2-minute demo video

---

## 🖥️ Person 5 — Vibe Coder #2 / Integration Lead
### Simulation Environment + Final Integration

### DAY 1

- Review all scenario files in `environment/`
- Add more obstacle layouts if needed in `warehouse_layout.py`
- Write `viz/pygame_renderer.py` as backup visualizer

### DAY 2 — **Your Most Important Day**

Integration checklist:
```
[ ] DSA person's robot_agent.py exports valid JSON
[ ] ML task_allocator.py connects to sim_runner
[ ] P2P network sends data to dashboard
[ ] python simulation/sim_runner.py runs without errors
[ ] Open dashboard — robots appear and move
[ ] Battery bars drain over time
[ ] Event log shows conflict resolutions
```

Write the 5-minute demo script and prepare slides.

---

## ⚡ Person 6 — Electronics / Hardware
### Hardware Realism + Deployment Docs

### DAY 1

All three hardware models are already written:
- `environment/battery_model.py` ✅
- `environment/sensor_model.py` ✅
- `environment/network_model.py` ✅

Write:
- `docs/hardware_spec.md` — Raspberry Pi 4 specs, RPLidar, MPU-6050, power budget

### DAY 2

- Write `docs/raspberry_pi_deployment.md` — step-by-step to run on real Pi
- Demonstrate dead zone scenario: force a robot into `(9,9)` and show it keeps moving
- Measure simulation CPU usage, document in `docs/edge_performance.md`

---

## 🔗 Integration Points

| Provider | Delivers | Consumer | Method |
|----------|----------|----------|--------|
| DSA | `Robot.to_json()`, `astar()` | P2P, ML, UI | `from core.robot_agent import Robot` |
| ML | `allocate(tasks, robots)` | P2P (sim_runner) | `from ml.task_allocator import TaskAllocator` |
| P2P | WebSocket on port 8080 | Dashboard | `new WebSocket('ws://localhost:8080')` |
| HW | `BatteryModel`, `SensorModel` | DSA (robot_agent) | `from environment.battery_model import BatteryModel` |

---

## ✅ Success Criteria

- [ ] Zero inter-robot collisions during 5-minute demo
- [ ] ≥20% faster completion vs stop-and-wait (`benchmark_results.json`)
- [ ] All 3 robots communicate P2P — no central server
- [ ] Dashboard shows live positions, battery, task queue
- [ ] Deadlock scenario demonstrated and resolved
- [ ] Wi-Fi dead zone scenario demonstrated
- [ ] `docs/raspberry_pi_deployment.md` exists
