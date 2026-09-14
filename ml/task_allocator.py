"""
task_allocator.py — Intelligent Task Allocation
[ML PERSON] — Assign tasks to robots using greedy + ML-guided scoring.

Integration:
    Called by sim_runner.py whenever new tasks are available or a robot is freed.
    Uses robot positions and battery from Robot.to_json() state.
"""

import json
import math
import time
from typing import Optional


# ---------------------------------------------------------------------------
# Data classes (mirrors the SCHEMA.md task format)
# ---------------------------------------------------------------------------

class TaskSpec:
    """Lightweight task description used by the allocator."""

    def __init__(self, task_id: str, pickup: tuple, dropoff: tuple, priority: int = 1):
        self.task_id = task_id
        self.pickup = tuple(pickup)
        self.dropoff = tuple(dropoff)
        self.priority = priority
        self.created_at = time.time()

    @staticmethod
    def from_dict(d: dict) -> "TaskSpec":
        return TaskSpec(
            task_id=d["task_id"],
            pickup=tuple(d["pickup"]),
            dropoff=tuple(d["dropoff"]),
            priority=d.get("priority", 1),
        )


class RobotState:
    """Lightweight snapshot of a robot's state (parsed from its JSON broadcast)."""

    def __init__(self, robot_id: str, position: tuple, battery: float, status: str):
        self.robot_id = robot_id
        self.position = position
        self.battery = battery
        self.status = status

    @staticmethod
    def from_json(raw: str) -> "RobotState":
        d = json.loads(raw)
        return RobotState(
            robot_id=d["robot_id"],
            position=(d["position"]["x"], d["position"]["y"]),
            battery=d["battery"],
            status=d["status"],
        )


# ---------------------------------------------------------------------------
# Core allocator
# ---------------------------------------------------------------------------

class TaskAllocator:
    """
    Assigns tasks to the most suitable available robot.

    Usage:
        allocator = TaskAllocator()
        assignments = allocator.allocate(tasks, robot_states)
        # assignments = {"T1": "R2", "T2": "R1"}

    Two modes:
        - "greedy"  : pure distance-based (baseline, always works)
        - "ml"      : uses CongestionPredictor to weigh paths (Day 2)
    """

    def __init__(self, mode: str = "greedy"):
        """
        Args:
            mode: "greedy" or "ml". Start with "greedy" and upgrade to "ml" on Day 2.
        """
        self.mode = mode
        self.congestion_predictor = None   # Set this on Day 2

    def set_congestion_predictor(self, predictor) -> None:
        """Inject the trained CongestionPredictor (called from sim_runner.py on Day 2)."""
        self.congestion_predictor = predictor
        self.mode = "ml"

    # ------------------------------------------------------------------
    # Main allocation entry point
    # ------------------------------------------------------------------

    def allocate(
        self, tasks: list[TaskSpec], robot_states: list[RobotState]
    ) -> dict[str, str]:
        """
        Assign each task to the best available robot.

        Args:
            tasks:        List of unassigned TaskSpec objects.
            robot_states: List of current RobotState snapshots.

        Returns:
            Dict mapping task_id → robot_id.
            Only idle robots are eligible.
        """
        idle_robots = [r for r in robot_states if r.status == "idle"]
        if not idle_robots or not tasks:
            return {}

        if self.mode == "ml" and self.congestion_predictor:
            return self._allocate_ml(tasks, idle_robots)
        return self._allocate_greedy(tasks, idle_robots)

    # ------------------------------------------------------------------
    # Strategy 1 — Greedy (baseline)
    # ------------------------------------------------------------------

    def _allocate_greedy(
        self, tasks: list[TaskSpec], idle_robots: list[RobotState]
    ) -> dict[str, str]:
        """
        Assign each task to the nearest idle robot.

        TODO [ML PERSON]: Implement this.
        Steps:
            1. Sort tasks by priority (descending)
            2. For each task, find the idle robot with smallest manhattan distance
               to task.pickup
            3. Remove that robot from the idle pool (one task per robot)
            4. Return {task_id: robot_id}
        """
        assignments: dict[str, str] = {}
        available = list(idle_robots)

        # Sort tasks: higher priority first
        sorted_tasks = sorted(tasks, key=lambda t: -t.priority)

        for task in sorted_tasks:
            if not available:
                break
            # TODO [ML]: Find nearest robot to task.pickup
            best_robot = None
            best_dist = float("inf")
            for robot in available:
                dist = _manhattan(robot.position, task.pickup)
                if dist < best_dist:
                    best_dist = dist
                    best_robot = robot

            if best_robot:
                assignments[task.task_id] = best_robot.robot_id
                available.remove(best_robot)

        return assignments

    # ------------------------------------------------------------------
    # Strategy 2 — ML-guided (Day 2 upgrade)
    # ------------------------------------------------------------------

    def _allocate_ml(
        self, tasks: list[TaskSpec], idle_robots: list[RobotState]
    ) -> dict[str, str]:
        """
        Assign tasks by minimizing a composite cost score per (robot, task) pair.

        Uses compute_score() which incorporates distance, battery, load factor,
        and congestion probability from the trained ML model.
        """
        if not self.congestion_predictor:
            return self._allocate_greedy(tasks, idle_robots)

        assignments: dict[str, str] = {}
        available = list(idle_robots)
        all_positions = [r.position for r in idle_robots]

        # Sort tasks by priority (highest first)
        sorted_tasks = sorted(tasks, key=lambda t: -t.priority)

        for task in sorted_tasks:
            if not available:
                break

            # Find robot with minimum cost score for this task
            best_robot = None
            best_score = float("inf")
            for robot in available:
                score = self.compute_score(robot, task, other_robot_positions=all_positions)
                if score < best_score:
                    best_score = score
                    best_robot = robot

            if best_robot:
                assignments[task.task_id] = best_robot.robot_id
                available.remove(best_robot)

        return assignments

    def compute_score(
        self,
        robot: RobotState,
        task: TaskSpec,
        other_robot_positions: Optional[list[tuple]] = None,
    ) -> float:
        """
        Compute assignment cost for a specific (robot, task) pair.

        TODO [ML PERSON]: Tune these weights for best performance.
        """
        distance = _manhattan(robot.position, task.pickup)
        battery_penalty = (100.0 - robot.battery) * 0.5
        load_factor = 1.0 if robot.status == "idle" else 5.0

        congestion = 0.0
        if self.congestion_predictor and other_robot_positions:
            congestion = self.congestion_predictor.predict_congestion(
                task.pickup, time.time(), other_robot_positions
            )

        return distance + battery_penalty + load_factor + congestion * 10.0

    # ------------------------------------------------------------------
    # Dynamic re-allocation (called when a robot gets blocked)
    # ------------------------------------------------------------------

    def reallocate_on_block(
        self,
        blocked_robot_id: str,
        unfinished_task: TaskSpec,
        available_robots: list[RobotState],
    ) -> Optional[str]:
        """
        Re-assign unfinished_task from a blocked robot to another available robot.

        Args:
            blocked_robot_id:  The robot that got stuck.
            unfinished_task:   The task that needs a new owner.
            available_robots:  Current snapshot of all robot states.

        Returns:
            robot_id of the new assignee, or None if no robot is available.

        TODO [ML PERSON]: Implement this. Very similar to _allocate_greedy()
        but exclude blocked_robot_id from candidates and skip robots that
        already have a task.
        """
        candidates = [
            r for r in available_robots
            if r.robot_id != blocked_robot_id and r.status == "idle"
        ]
        if not candidates:
            return None

        result = self._allocate_greedy([unfinished_task], candidates)
        return result.get(unfinished_task.task_id)


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _manhattan(a: tuple, b: tuple) -> float:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])
