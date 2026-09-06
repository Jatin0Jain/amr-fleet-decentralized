# 🤖 AMR Fleet — Decentralized Coordination Framework

> Smart Warehouse Robot Fleet with P2P Communication & Collision Avoidance

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run simulation (medium difficulty)
python simulation/sim_runner.py --scenario medium

# 3. Open dashboard in browser
# → Open dashboard/index.html (or http://localhost:3000 if using a server)

# 4. Run unit tests
python -m pytest tests/ -v

# 5. Run benchmark
python simulation/sim_runner.py --benchmark
```

## Project Structure

```
amr_fleet/
├── core/               # [DSA]  Path planning + conflict resolution
│   ├── grid.py
│   ├── pathfinder.py
│   ├── conflict.py
│   └── robot_agent.py
├── ml/                 # [ML]   Task allocation + congestion prediction
│   ├── task_allocator.py
│   ├── congestion_model.py
│   └── data_logger.py
├── network/            # [P2P]  WebSocket peer-to-peer messaging
│   ├── robot_node.py
│   └── message_broker.py
├── simulation/         # [P2P]  Master simulation loop
│   └── sim_runner.py
├── environment/        # [HW+ENV]  Warehouse, scenarios, hardware models
│   ├── warehouse_layout.py
│   ├── scenario_generator.py
│   ├── battery_model.py
│   ├── sensor_model.py
│   └── network_model.py
├── dashboard/          # [UI]   Web-based fleet monitoring UI
│   ├── index.html
│   ├── style.css
│   └── app.js
├── tests/              # [DSA]  Unit tests
│   └── test_core.py
├── SCHEMA.md           # ← Read this first! Shared JSON contract
└── requirements.txt
```

## Message Schema

All robots broadcast JSON every 200ms. See [SCHEMA.md](SCHEMA.md) for the full contract.

## Team

| Person | Module | Key Deliverable |
|--------|--------|-----------------|
| DSA    | `core/` | A*, conflict resolver, robot agent |
| ML     | `ml/`  | Task allocator, congestion model |
| P2P    | `network/` + `simulation/` | WebSocket P2P, sim runner |
| UI     | `dashboard/` | Live fleet dashboard |
| Env    | `environment/` | Warehouse, scenarios |
| HW     | `environment/` | Battery, sensor, network models |
