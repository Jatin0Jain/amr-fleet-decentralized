# AMR Fleet — Decentralized Coordination Framework
## Shared Message Schema (DO NOT CHANGE WITHOUT TEAM AGREEMENT)

Every robot broadcasts this JSON every 200ms.

```json
{
  "robot_id": "R1",
  "position": {"x": 5, "y": 3},
  "velocity": {"vx": 0, "vy": 1},
  "planned_path": [[5,3],[5,4],[5,5],[6,5]],
  "current_task": {
    "task_id": "T12",
    "pickup": [2, 2],
    "dropoff": [8, 8],
    "priority": 1
  },
  "battery": 87.5,
  "status": "moving",
  "timestamp": 1728000000.123
}
```

### Status values
- `"moving"` — robot is actively traversing its path
- `"waiting"` — robot is paused due to conflict resolution
- `"charging"` — robot is at a charging station
- `"blocked"` — robot cannot find a path (needs re-routing)
- `"idle"` — robot has no assigned task

### Port assignments
- R1 → WebSocket port 8001
- R2 → WebSocket port 8002
- R3 → WebSocket port 8003
- Dashboard feed → WebSocket port 8080
