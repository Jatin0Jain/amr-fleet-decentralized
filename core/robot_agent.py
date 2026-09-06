"""
robot_agent.py — Robot Agent Class
[DSA PERSON] — Ties together grid, pathfinder, conflict resolver.

This is the central class that each robot "is" in the simulation.
Every robot is an instance of this class running inside sim_runner.py.
"""

import time
import json
from typing import Optional, TYPE_CHECKING

from core.grid import WarehouseGrid
from core.pathfinder import astar
from core.conflict import ConflictResolver, ACTION_MOVE, ACTION_WAIT, ACTION_REROUTE

if TYPE_CHECKING:
    from environment.battery_model import BatteryModel
    from environment.sensor_model import SensorModel


class Task:
    """Represents a warehouse task (pickup → dropoff)."""

    def __init__(
        self,
        task_id: str,
        pickup: tuple[int, int],
        dropoff: tuple[int, int],
        priority: int = 1,
    ):
        self.task_id = task_id
        self.pickup = pickup
        self.dropoff = dropoff
        self.priority = priority
        self.assigned_at = time.time()

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "pickup": list(self.pickup),
            "dropoff": list(self.dropoff),
            "priority": self.priority,
        }


class Robot:
    """
    A single Autonomous Mobile Robot in the simulation.

    Lifecycle per tick (sim_runner calls robot.step() at 10 FPS):
        1. Check conflict resolver → get action ("move" | "wait" | "reroute")
        2. If "move": advance one step along planned_path, update grid reservation
        3. If "wait": stay still, increment blocked timer
        4. If "reroute": call A* to get a new path, reset blocked timer
        5. Update battery via BatteryModel
        6. Emit state via to_json()

    Usage:
        grid = WarehouseGrid()
        resolver = ConflictResolver()
        robot = Robot("R1", start_pos=(0,0), grid=grid, resolver=resolver)
        robot.assign_task(Task("T1", pickup=(2,2), dropoff=(8,8)))

        # each simulation tick:
        robot.step(dt=0.1, other_robots=[r2, r3])
        state = robot.to_json()   # send to dashboard / network
    """

    def __init__(
        self,
        robot_id: str,
        start_pos: tuple[int, int],
        grid: WarehouseGrid,
        resolver: ConflictResolver,
        battery_model: Optional["BatteryModel"] = None,
        sensor_model: Optional["SensorModel"] = None,
    ):
        self.robot_id = robot_id
        self.position: tuple[int, int] = start_pos
        self.grid = grid
        self.resolver = resolver
        self.battery_model = battery_model
        self.sensor_model = sensor_model

        # Path & task state
        self.planned_path: list[tuple[int, int]] = []
        self.current_task: Optional[Task] = None
        self.task_phase: str = "pickup"   # "pickup" → "dropoff" → done

        # Runtime state
        self.status: str = "idle"         # See SCHEMA.md for valid values
        self.battery: float = 100.0
        self.blocked_since: float = 0.0   # epoch time when robot got blocked
        self.velocity: tuple[int, int] = (0, 0)

        # Congestion weights provided by ML module (updated externally)
        self.congestion_weights: dict[tuple, float] = {}

    # ------------------------------------------------------------------
    # Task assignment
    # ------------------------------------------------------------------

    def assign_task(self, task: Task) -> None:
        """Assign a new task and immediately compute path to pickup."""
        self.current_task = task
        self.task_phase = "pickup"
        self.status = "moving"
        self._replan()

    def _replan(self) -> None:
        """Compute a new A* path based on current task phase."""
        if self.current_task is None:
            self.planned_path = []
            self.status = "idle"
            return

        goal = (
            self.current_task.pickup
            if self.task_phase == "pickup"
            else self.current_task.dropoff
        )
        # TODO [DSA]: Call astar() with self.congestion_weights
        path = astar(
            self.grid,
            self.position,
            goal,
            self.robot_id,
            congestion_weights=self.congestion_weights,
        )
        if path:
            self.planned_path = path[1:]   # exclude current position
            self.status = "moving"
        else:
            self.planned_path = []
            self.status = "blocked"
            self.blocked_since = time.time()

    # ------------------------------------------------------------------
    # Per-tick update
    # ------------------------------------------------------------------

    def step(self, dt: float, other_robots: list["Robot"]) -> "Robot":
        """
        Advance robot state by one simulation tick.

        Args:
            dt:           Time delta in seconds (typically 0.1 for 10 FPS).
            other_robots: List of all other Robot instances (for conflict checks).

        Returns:
            self (for chaining / convenience).
        """
        # TODO [DSA]: Implement the step logic.
        #
        # 1. Get action from resolver:
        #    action = self.resolver.resolve([self] + other_robots, self.grid)[self.robot_id]
        #    (or resolve is called centrally in sim_runner — coordinate with P2P person)
        #
        # 2. If ACTION_MOVE and self.planned_path:
        #    - next_cell = self.planned_path[0]
        #    - Reserve next_cell in grid
        #    - Update self.velocity = (next_cell[0]-self.position[0], next_cell[1]-self.position[1])
        #    - self.position = next_cell
        #    - self.planned_path.pop(0)
        #    - Check if arrived at pickup / dropoff → advance task_phase or complete task
        #
        # 3. If ACTION_WAIT:
        #    - self.status = "waiting"
        #    - self.velocity = (0, 0)
        #    - if self.blocked_since == 0: self.blocked_since = time.time()
        #
        # 4. If ACTION_REROUTE:
        #    - self.grid.clear_reservations(self.robot_id)
        #    - self.blocked_since = 0.0
        #    - self._replan()
        #
        # 5. Update battery:
        #    if self.battery_model:
        #        self.battery = self.battery_model.drain(self.status, dt)
        #    else:
        #        self.battery = max(0, self.battery - 0.01 * dt)   # simple fallback
        #
        # 6. If battery < 15%: self.status = "charging", go to nearest charge station

        raise NotImplementedError("DSA person: implement step()")

    def next_cell(self) -> Optional[tuple[int, int]]:
        """Return the next cell on the planned path, or None if path is empty."""
        return self.planned_path[0] if self.planned_path else None

    # ------------------------------------------------------------------
    # Serialization  ← THIS IS THE INTEGRATION CONTRACT
    # ------------------------------------------------------------------

    def to_json(self) -> str:
        """
        Serialize robot state to JSON string matching SCHEMA.md exactly.

        Called by sim_runner every tick to broadcast to:
          - Other robots via P2P network
          - Dashboard via WebSocket on port 8080
        """
        # Apply sensor noise if sensor model is available
        reported_pos = self.position
        if self.sensor_model:
            noisy = self.sensor_model.get_noisy_position(
                (float(self.position[0]), float(self.position[1]))
            )
            reported_pos = (round(noisy[0], 2), round(noisy[1], 2))

        state = {
            "robot_id": self.robot_id,
            "position": {"x": reported_pos[0], "y": reported_pos[1]},
            "velocity": {"vx": self.velocity[0], "vy": self.velocity[1]},
            "planned_path": [list(cell) for cell in self.planned_path[:10]],  # cap at 10
            "current_task": self.current_task.to_dict() if self.current_task else None,
            "battery": round(self.battery, 1),
            "status": self.status,
            "timestamp": time.time(),
        }
        return json.dumps(state)

    @staticmethod
    def from_json(data: str) -> dict:
        """Parse a JSON state message received from another robot over the network."""
        return json.loads(data)

    def __repr__(self) -> str:
        return (
            f"Robot({self.robot_id} @ {self.position} "
            f"| {self.status} | battery={self.battery:.0f}%)"
        )
