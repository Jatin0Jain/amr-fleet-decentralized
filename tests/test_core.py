"""
test_core.py — Unit Tests for Core Modules
[DSA PERSON] — Run these to verify your implementations are correct.

Run with:
    python -m pytest tests/test_core.py -v
    # or just:
    python tests/test_core.py
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import unittest
from core.grid import WarehouseGrid, FREE, OBSTACLE
from core.pathfinder import astar, manhattan
from core.robot_agent import Robot, Task
from core.conflict import ConflictResolver, ACTION_MOVE, ACTION_WAIT, ACTION_REROUTE


# ─────────────────────────────────────────────────────────────
# Grid Tests
# ─────────────────────────────────────────────────────────────

class TestWarehouseGrid(unittest.TestCase):

    def setUp(self):
        self.grid = WarehouseGrid(width=10, height=10)

    def test_in_bounds(self):
        self.assertTrue(self.grid._in_bounds(0, 0))
        self.assertTrue(self.grid._in_bounds(9, 9))
        self.assertFalse(self.grid._in_bounds(-1, 0))
        self.assertFalse(self.grid._in_bounds(10, 0))

    def test_add_obstacle(self):
        self.grid.add_obstacle(3, 4)
        self.assertTrue(self.grid.is_obstacle(3, 4))
        self.assertFalse(self.grid.is_obstacle(3, 5))

    def test_add_obstacle_rect(self):
        self.grid.add_obstacle_rect(2, 2, 4, 2)
        for x in range(2, 5):
            self.assertTrue(self.grid.is_obstacle(x, 2))

    def test_passable_free_cell(self):
        self.assertTrue(self.grid.is_passable(5, 5, "R1"))

    def test_passable_obstacle_cell(self):
        self.grid.add_obstacle(5, 5)
        self.assertFalse(self.grid.is_passable(5, 5, "R1"))

    def test_reserve_cell(self):
        success = self.grid.reserve_cell(3, 3, "R1", duration=5.0)
        self.assertTrue(success)
        # Same robot can re-reserve its own cell
        success2 = self.grid.reserve_cell(3, 3, "R1", duration=5.0)
        self.assertTrue(success2)
        # Different robot cannot take reserved cell
        success3 = self.grid.reserve_cell(3, 3, "R2", duration=5.0)
        self.assertFalse(success3)

    def test_clear_reservations(self):
        self.grid.reserve_cell(3, 3, "R1", duration=60.0)
        self.grid.clear_reservations("R1")
        # Now R2 should be able to reserve it
        success = self.grid.reserve_cell(3, 3, "R2", duration=5.0)
        self.assertTrue(success)

    def test_get_neighbors(self):
        neighbors = self.grid.get_neighbors(5, 5)
        self.assertIn((6, 5), neighbors)
        self.assertIn((4, 5), neighbors)
        self.assertIn((5, 6), neighbors)
        self.assertIn((5, 4), neighbors)
        self.assertEqual(len(neighbors), 4)

    def test_get_neighbors_corner(self):
        neighbors = self.grid.get_neighbors(0, 0)
        self.assertEqual(len(neighbors), 2)  # only right and down


# ─────────────────────────────────────────────────────────────
# Pathfinder Tests
# ─────────────────────────────────────────────────────────────

class TestAstar(unittest.TestCase):

    def setUp(self):
        self.grid = WarehouseGrid(width=10, height=10)

    def test_simple_path(self):
        path = astar(self.grid, (0, 0), (3, 0), "R1")
        self.assertIsNotNone(path)
        self.assertEqual(path[0], (0, 0))
        self.assertEqual(path[-1], (3, 0))
        self.assertEqual(len(path), 4)  # (0,0),(1,0),(2,0),(3,0)

    def test_path_around_obstacle(self):
        # Block straight path: add wall from (1,0) to (1,3)
        for y in range(4):
            self.grid.add_obstacle(1, y)

        path = astar(self.grid, (0, 0), (2, 0), "R1")
        self.assertIsNotNone(path)
        self.assertEqual(path[-1], (2, 0))
        # Path should not go through obstacles
        for cell in path:
            self.assertFalse(self.grid.is_obstacle(*cell))

    def test_no_path_exists(self):
        # Completely surround the goal
        for x in range(10):
            self.grid.add_obstacle(x, 5)  # horizontal wall
        path = astar(self.grid, (0, 0), (5, 9), "R1")
        self.assertIsNone(path)

    def test_start_equals_goal(self):
        path = astar(self.grid, (3, 3), (3, 3), "R1")
        self.assertIsNotNone(path)
        self.assertEqual(len(path), 1)
        self.assertEqual(path[0], (3, 3))

    def test_manhattan_heuristic(self):
        self.assertEqual(manhattan((0, 0), (3, 4)), 7)
        self.assertEqual(manhattan((5, 5), (5, 5)), 0)


# ─────────────────────────────────────────────────────────────
# Conflict Resolution Tests
# ─────────────────────────────────────────────────────────────

class TestConflictResolver(unittest.TestCase):

    def setUp(self):
        self.grid = WarehouseGrid(width=10, height=10)
        self.resolver = ConflictResolver()

    def _make_robot(self, rid, pos, path, battery=80):
        r = Robot(rid, pos, self.grid, self.resolver)
        r.planned_path = list(path)
        r.battery = battery
        r.status = "moving"
        return r

    def test_no_conflict_different_paths(self):
        r1 = self._make_robot("R1", (0, 0), [(1, 0), (2, 0)])
        r2 = self._make_robot("R2", (0, 5), [(0, 6), (0, 7)])
        result = self.resolver.resolve_head_on(r1, r2)
        self.assertIsNone(result)

    def test_head_on_conflict_detected(self):
        # R1 going right, R2 going left — about to collide at (2,0)
        r1 = self._make_robot("R1", (1, 0), [(2, 0), (3, 0)])
        r2 = self._make_robot("R2", (3, 0), [(2, 0), (1, 0)])
        result = self.resolver.resolve_head_on(r1, r2)
        self.assertIsNotNone(result)
        waiter, mover = result
        self.assertIn(waiter, ["R1", "R2"])
        self.assertIn(mover, ["R1", "R2"])
        self.assertNotEqual(waiter, mover)

    def test_lower_battery_has_priority(self):
        # R1 has lower battery → R1 should have priority → R2 waits
        r1 = self._make_robot("R1", (1, 0), [(2, 0)], battery=20)
        r2 = self._make_robot("R2", (3, 0), [(2, 0)], battery=80)
        result = self.resolver.resolve_head_on(r1, r2)
        if result:
            waiter, mover = result
            self.assertEqual(waiter, "R2")   # R2 waits, R1 moves

    def test_deadlock_detection(self):
        # Circular wait: R1 waits for R2, R2 waits for R1
        r1 = self._make_robot("R1", (2, 0), [(3, 0)])
        r2 = self._make_robot("R2", (3, 0), [(2, 0)])
        r1.status = "waiting"
        r2.status = "waiting"
        # After reservations are made:
        self.grid.reserve_cell(3, 0, "R2", duration=60)
        self.grid.reserve_cell(2, 0, "R1", duration=60)

        deadlocked = self.resolver.detect_deadlock([r1, r2])
        self.assertTrue(len(deadlocked) > 0, "Should detect deadlock")

    def test_resolve_returns_all_robots(self):
        r1 = self._make_robot("R1", (0, 0), [(1, 0)])
        r2 = self._make_robot("R2", (5, 5), [(6, 5)])
        r3 = self._make_robot("R3", (9, 9), [(9, 8)])
        actions = self.resolver.resolve([r1, r2, r3], self.grid)
        self.assertIn("R1", actions)
        self.assertIn("R2", actions)
        self.assertIn("R3", actions)
        for action in actions.values():
            self.assertIn(action, [ACTION_MOVE, ACTION_WAIT, ACTION_REROUTE])


# ─────────────────────────────────────────────────────────────
# Integration Smoke Test
# ─────────────────────────────────────────────────────────────

class TestRobotSerialization(unittest.TestCase):
    """Quick smoke test: can we create a robot and get valid JSON?"""

    def test_to_json_schema(self):
        import json
        grid = WarehouseGrid()
        resolver = ConflictResolver()
        robot = Robot("R1", (5, 5), grid, resolver)
        robot.battery = 75.0
        robot.status = "idle"

        raw = robot.to_json()
        data = json.loads(raw)

        # Verify required schema fields from SCHEMA.md
        self.assertIn("robot_id", data)
        self.assertIn("position", data)
        self.assertIn("velocity", data)
        self.assertIn("planned_path", data)
        self.assertIn("battery", data)
        self.assertIn("status", data)
        self.assertIn("timestamp", data)

        self.assertEqual(data["robot_id"], "R1")
        self.assertEqual(data["position"]["x"], 5)
        self.assertEqual(data["position"]["y"], 5)
        self.assertEqual(data["battery"], 75.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
