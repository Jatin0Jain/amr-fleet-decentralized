"""
conflict.py — Multi-Agent Conflict Detection & Resolution
[DSA PERSON] — Deadlock + collision avoidance logic.

Three strategies:
  1. Priority-based waiting  (head-on / same-cell conflicts)
  2. Deadlock detection + break  (circular wait)
  3. Re-route trigger  (persistent blockage)
"""

import time
from typing import TYPE_CHECKING

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

    def resolve(self, robots: list["Robot"], grid) -> dict[str, str]:
        """
        Main entry point. Evaluate all robots and return action for each.

        Args:
            robots: List of all Robot instances in the simulation.
            grid:   WarehouseGrid instance.

        Returns:
            Dict mapping robot_id → action string ("move" | "wait" | "reroute").
        """
        # TODO [DSA]: Orchestrate the three strategies below.
        #
        # Suggested order:
        #   1. Detect deadlocks first (highest priority to break)
        #   2. Resolve head-on / same-cell conflicts
        #   3. Check if any robot should be forced to re-route
        #
        # Start with everyone moving, then override:
        actions = {r.robot_id: ACTION_MOVE for r in robots}

        deadlocked = self.detect_deadlock(robots)
        for robot_id in deadlocked:
            actions[robot_id] = ACTION_REROUTE

        for i, ra in enumerate(robots):
            for rb in robots[i + 1:]:
                result = self.resolve_head_on(ra, rb)
                if result:
                    waiter, _ = result
                    if actions[waiter] != ACTION_REROUTE:
                        actions[waiter] = ACTION_WAIT

        for robot in robots:
            if self.should_reroute(robot):
                actions[robot.robot_id] = ACTION_REROUTE

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
        # TODO [DSA]: Implement conflict detection between two robots.
        #
        # Check 1 — Same next cell:
        #   if ra.next_cell() == rb.next_cell() → conflict
        #
        # Check 2 — Swap (head-on):
        #   if ra.next_cell() == rb.position and rb.next_cell() == ra.position → conflict
        #
        # Priority: robot with LOWER battery has HIGHER priority (let them finish first)
        raise NotImplementedError("DSA person: implement resolve_head_on()")

    # ------------------------------------------------------------------
    # Strategy 2 — Deadlock detection
    # ------------------------------------------------------------------

    def detect_deadlock(self, robots: list["Robot"]) -> list[str]:
        """
        Detect circular wait among robots.

        A deadlock exists when robot A waits for robot B, B waits for C, C waits for A.

        Returns:
            List of robot_ids that are in a deadlock cycle (one will be told to re-route).

        Algorithm hint:
            - Build a directed "wait-for" graph: {robot_id: robot_id_it_is_waiting_for}
            - Detect a cycle in that graph (DFS or follow pointers)
            - Return all robot_ids in the cycle
        """
        # TODO [DSA]: Implement deadlock detection.
        #
        # Hint: a robot is "waiting for" another robot if:
        #   robot.status == "waiting" AND the cell it wants is reserved by another robot
        raise NotImplementedError("DSA person: implement detect_deadlock()")

    # ------------------------------------------------------------------
    # Strategy 3 — Re-route trigger
    # ------------------------------------------------------------------

    def should_reroute(self, robot: "Robot") -> bool:
        """
        Return True if robot has been blocked/waiting too long and needs a new path.

        Threshold: REROUTE_THRESHOLD_SECONDS (default 3 seconds).
        """
        # TODO [DSA]: Check robot.blocked_since timestamp.
        #   return (time.time() - robot.blocked_since) > REROUTE_THRESHOLD_SECONDS
        #   Only applies if robot.status in ("waiting", "blocked")
        raise NotImplementedError("DSA person: implement should_reroute()")


# ---------------------------------------------------------------------------
# Helper: needed for Optional type hint above without full import
# ---------------------------------------------------------------------------
from typing import Optional  # noqa: E402 — kept at bottom to avoid circular imports
