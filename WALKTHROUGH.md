# 🚀 Project Walkthrough

> Summary of what's been built, what's been tested, and what's remaining.

---

## What Was Built

Full starter scaffold for the AMR Fleet decentralized coordination system.
**18 source files** across 6 modules, all importable and smoke-tested.

---

## File Status

### ✅ Complete — No Changes Needed

| File | Description |
|------|-------------|
| `environment/warehouse_layout.py` | 20×20 grid with shelves, corridors, zones |
| `environment/scenario_generator.py` | Easy / Medium / Hard scenarios |
| `environment/battery_model.py` | Realistic LiPo drain (moving=0.033%/s) |
| `environment/sensor_model.py` | Gaussian position noise + packet loss |
| `environment/network_model.py` | Wi-Fi dead zones (538ms vs 3ms latency) |
| `ml/task_allocator.py` | Greedy allocation working |
| `ml/data_logger.py` | JSONL tick logger for ML training |
| `network/message_broker.py` | All P2P message type constructors |
| `dashboard/index.html` | Dashboard HTML layout |
| `dashboard/style.css` | Dark ops-center theme |
| `dashboard/app.js` | Canvas renderer + WebSocket + animations |
| `tests/test_core.py` | Unit tests for all core modules |
| `SCHEMA.md` | Shared JSON contract |
| `TASKS.md` | Team coordination reference |

### 🟡 Has Stubs — Team Must Fill In

| File | Owner | Stubs |
|------|-------|-------|
| `core/grid.py` | DSA | `reserve_cell`, `clear_reservations`, `is_passable` |
| `core/pathfinder.py` | DSA | `astar()` |
| `core/conflict.py` | DSA | `resolve_head_on`, `detect_deadlock`, `should_reroute` |
| `core/robot_agent.py` | DSA | `step()` |
| `ml/congestion_model.py` | ML | `_train()` |
| `network/robot_node.py` | P2P | `run`, `_serve`, `_connect_to_peers`, `_broadcast_loop` |
| `simulation/sim_runner.py` | P2P | `simulation_loop()` |

---

## Smoke Test Results

All completed modules verified working:

```
All modules imported OK
Warehouse: 20x20, obstacles placed
Battery drain: 100.0 -> 99.997%
Sensor noise: noisy=(5.024, 2.917)
Latency normal=3.6ms  dead_zone=538ms
Scenario: 3 robots, 5 tasks
Allocator: {'T1': 'R1', 'T2': 'R2'}
Message broker: type=conflict cell=[5, 3]

=== ALL SMOKE TESTS PASSED ===
```

Run it yourself:
```bash
python tests/smoke_test.py
```

---

## Architecture

```
core/            ← DSA: path planning + conflict resolution
ml/              ← ML: task allocation + congestion prediction
network/         ← P2P: WebSocket peer-to-peer messaging
simulation/      ← P2P: master simulation loop (integration hub)
environment/     ← HW+Env: warehouse, battery, sensor, network models
dashboard/       ← UI: browser-based live fleet monitor
```

**Critical path** (what blocks what):
```
core/grid.py → core/pathfinder.py → core/robot_agent.py
                                           ↓
                              simulation/sim_runner.py
                                           ↓
                               dashboard WebSocket
```

DSA person's files must be done before P2P person can run the full simulation.

---

## How to Run

```bash
# Install dependencies
pip install -r requirements.txt

# Smoke test
python tests/smoke_test.py

# Run simulation (once stubs are filled)
python simulation/sim_runner.py --scenario medium

# Open dashboard
# → Open dashboard/index.html in browser
# → Connect to ws://localhost:8080

# Run unit tests
python -m pytest tests/test_core.py -v

# Run benchmark
python simulation/sim_runner.py --benchmark
```

---

## Port Reference

| Service | Port |
|---------|------|
| Robot R1 WebSocket server | 8001 |
| Robot R2 WebSocket server | 8002 |
| Robot R3 WebSocket server | 8003 |
| Dashboard feed | 8080 |

---

## Success Criteria

- [ ] Zero inter-robot collisions during 5-minute demo run
- [ ] ≥20% faster task completion vs stop-and-wait (`benchmark_results.json`)
- [ ] P2P communication — no central server required
- [ ] Live dashboard showing positions, battery, tasks, events
- [ ] Deadlock + dead zone scenarios demonstrated
