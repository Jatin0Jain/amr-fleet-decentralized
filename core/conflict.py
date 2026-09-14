"""
conflict.py — Multi-Agent Conflict Detection & Resolution
[DSA PERSON] — Deadlock + collision avoidance logic.

Three strategies:
  1. Priority-based waiting  (head-on / same-cell conflicts)
  2. Deadlock detection + break  (circular wait)
  3. Re-route trigger  (persistent blockage)
"""

import time
from typing import TYPE_CHECKING, Optional  # Fixed: moved to top to avoid NameError

if TYPE_CHECKING:
    from core.robot_agent import Robot

# How long (seconds) a robot must be blocked before we force a re-route
REROUTE_THRESHOLD_SECONDS = 3.0


# ---------------------------------------------------------------------------
# Action constants returned by ConflictResolver.resolve()
# ---------------------------------------------------------------------------
ACTION_MOVE = "move"
ACTION_WAIT = "wait"
ACTION_REROUTE = "reroute"


class ConflictResolver:
    """
    Evaluates all robots each tick and decides who moves, waits, or re-routes.

    Usage (called every simulation tick inside sim_runner.py):
        resolver = ConflictResolver()
        actions = resolver.resolve(robots, grid)
        # actions = {"R1": "move", "R2": "wait", "R3": "reroute"}
    """

    def __init__(self):
        self.recent_conflicts = []

    def resolve(self, robots: list["Robot"], grid) -> dict[str, str]:
        """
        Main entry point. Evaluate all robots and return action for each.

        Args:
            robots: List of all Robot instances in the simulation.
            grid:   WarehouseGrid instance.

        Returns:
            Dict mapping robot_id → action string ("move" | "wait" | "reroute").
        """
        # Start with everyone moving, then override
        actions = {r.robot_id: ACTION_MOVE for r in robots}
        self.recent_conflicts = []

        # 1. Detect deadlocks first (highest priority to break)
        deadlocked = self.detect_deadlock(robots)
        for robot_id in deadlocked:
            actions[robot_id] = ACTION_REROUTE
            self.recent_conflicts.append({
                "type": "deadlock",
                "msg": f"Deadlock detected! {robot_id} rerouting."
            })

        # 2. Resolve head-on / same-cell conflicts
        for i, ra in enumerate(robots):
            for rb in robots[i + 1:]:
                result = self.resolve_head_on(ra, rb)
                if result:
                    waiter, mover = result
                    if actions[waiter] != ACTION_REROUTE:
                        actions[waiter] = ACTION_WAIT
                        loc = ra.position if waiter == ra.robot_id else rb.position
                        self.recent_conflicts.append({
                            "type": "yield",
                            "msg": f"{waiter} yielding to {mover} near {loc}"
                        })

        # 3. Check if any robot should be forced to re-route
        for robot in robots:
            if self.should_reroute(robot):
                actions[robot.robot_id] = ACTION_REROUTE
                self.recent_conflicts.append({
                    "type": "reroute",
                    "msg": f"{robot.robot_id} persistently blocked. Rerouting."
                })

        return actions

    # ------------------------------------------------------------------
    # Strategy 1 — Priority-based waiting
    # ------------------------------------------------------------------

    def resolve_head_on(
        self, ra: "Robot", rb: "Robot"
    ) -> Optional[tuple[str, str]]:
        """
        Detect if ra and rb are about to collide (same next cell or swap cells).

        Args:
            ra, rb: Two Robot instances.

        Returns:
            (waiter_id, mover_id) tuple if conflict detected, else None.

        Priority rules:
            - Lower battery → higher priority (they need to finish and charge)
            - If equal battery → lower robot_id number has priority
        """
        next_a = ra.next_cell()
        next_b = rb.next_cell()

        # No conflict possible if either robot has no next cell
        if next_a is None or next_b is None:
            return None

        conflict = False

        # Check 1: Both robots want to move to the SAME cell
        if next_a == next_b:
            conflict = True

        # Check 2: Robots want to SWAP positions (head-on)
        if next_a == rb.position and next_b == ra.position:
            conflict = True

        if not conflict:
            return None

        # Determine priority: lower battery = higher priority (needs to charge sooner)
        # In case of equal battery, lower robot_id string wins (e.g. "R1" < "R2")
        if ra.battery < rb.battery:
            # ra has lower battery → ra has priority → rb waits
            return (rb.robot_id, ra.robot_id)
        elif rb.battery < ra.battery:
            # rb has lower battery → rb has priority → ra waits
            return (ra.robot_id, rb.robot_id)
        else:
            # Equal battery: lexicographic — "R1" wins over "R2"
            if ra.robot_id <= rb.robot_id:
                return (rb.robot_id, ra.robot_id)
            else:
                return (ra.robot_id, rb.robot_id)

    # ------------------------------------------------------------------
    # Strategy 2 — Deadlock detection
    # ------------------------------------------------------------------

    def detect_deadlock(self, robots: list["Robot"]) -> list[str]:
        """
        Detect circular wait among robots.

        A deadlock exists when robot A waits for robot B, B waits for C, C waits for A.

        Returns:
            List of robot_ids that are in a deadlock cycle (one will be told to re-route).

        Algorithm:
            - Build a directed "wait-for" graph: {robot_id: robot_id_it_is_waiting_for}
            - Detect a cycle in that graph (DFS or follow pointers)
            - Return all robot_ids in the cycle
        """
        # Build a map from position → robot_id for quick lookup
        pos_to_robot: dict[tuple, str] = {r.position: r.robot_id for r in robots}
        robot_map: dict[str, "Robot"] = {r.robot_id: r for r in robots}

        # Build wait-for graph: robot A is "waiting for" robot B if:
        #   - A is in a waiting/blocked state
        #   - A's next cell is currently occupied by B (B is at that position)
        wait_for: dict[str, str] = {}
        for robot in robots:
            if robot.status not in ("waiting", "blocked"):
                continue
            next_c = robot.next_cell()
            if next_c is None:
                continue
            blocking_robot = pos_to_robot.get(next_c)
            if blocking_robot and blocking_robot != robot.robot_id:
                wait_for[robot.robot_id] = blocking_robot

        # Also check grid reservations: if next cell is reserved by another robot
        for robot in robots:
            if robot.robot_id in wait_for:
                continue  # already found a dependency
            next_c = robot.next_cell()
            if next_c is None:
                continue
            # Check the grid's reservation dict if accessible
            reservation = robot.grid.reservations.get(next_c)
            if reservation and reservation["robot_id"] != robot.robot_id:
                holder = reservation["robot_id"]
                # Only add if holder is a known robot
                if holder in robot_map:
                    wait_for[robot.robot_id] = holder

        if not wait_for:
            return []

        # DFS cycle detection on wait_for graph
        # Returns the cycle as a list of robot_ids, or [] if no cycle
        def find_cycle(start: str) -> list[str]:
            path = []
            visited_in_path = set()
            current = start
            while current in wait_for:
                if current in visited_in_path:
                    # Found a cycle — extract just the cycle portion
                    cycle_start_idx = path.index(current)
                    return path[cycle_start_idx:]
                visited_in_path.add(current)
                path.append(current)
                current = wait_for[current]
            return []

        deadlocked: list[str] = []
        globally_visited: set[str] = set()

        for robot_id in wait_for:
            if robot_id in globally_visited:
                continue
            cycle = find_cycle(robot_id)
            if cycle:
                # Mark all robots in cycle as globally visited
                globally_visited.update(cycle)
                # Only reroute the robot with the highest battery in the cycle
                # (least urgent — they can afford to wait and take a new path)
                cycle_robots = [robot_map[rid] for rid in cycle if rid in robot_map]
                if cycle_robots:
                    reroute_victim = max(cycle_robots, key=lambda r: r.battery)
                    if reroute_victim.robot_id not in deadlocked:
                        deadlocked.append(reroute_victim.robot_id)

        return deadlocked

    # ------------------------------------------------------------------
    # Strategy 3 — Re-route trigger
    # ------------------------------------------------------------------

    def should_reroute(self, robot: "Robot") -> bool:
        """
        Return True if robot has been blocked/waiting too long and needs a new path.

        Threshold: REROUTE_THRESHOLD_SECONDS (default 3 seconds).
        """
        if robot.status not in ("waiting", "blocked"):
            return False
        if robot.blocked_since == 0.0:
            return False
        return (time.time() - robot.blocked_since) > REROUTE_THRESHOLD_SECONDS
