"""
pathfinder.py — A* Path Planning with Time-Space Reservation
[DSA PERSON] — Core algorithm file.

Implements A* search that respects cell reservations by other robots.
"""

import heapq
from typing import Optional
from core.grid import WarehouseGrid


def manhattan(a: tuple[int, int], b: tuple[int, int]) -> int:
    """Manhattan distance heuristic."""
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def astar(
    grid: WarehouseGrid,
    start: tuple[int, int],
    goal: tuple[int, int],
    robot_id: str,
    congestion_weights: Optional[dict[tuple, float]] = None,
) -> Optional[list[tuple[int, int]]]:
    """
    Find shortest path from start to goal on the grid for robot_id.

    Args:
        grid: The warehouse grid (checks passability + obstacles).
        start: (x, y) starting cell.
        goal:  (x, y) target cell.
        robot_id: ID of the robot requesting the path (used for reservation checks).
        congestion_weights: Optional dict {(x,y): float} of extra costs per cell.
                            Provided by ML person's CongestionPredictor.

    Returns:
        List of (x, y) tuples from start → goal (inclusive), or None if no path exists.

    Algorithm:
        Standard A* with:
        - Manhattan distance heuristic
        - Extra cost for reserved cells (treated as high-cost, not impassable)
        - Extra cost from congestion_weights if provided
    """
    # TODO [DSA]: Implement A* here.
    #
    # Pseudocode:
    #   open_heap = [(f_score, g_score, node)]
    #   came_from = {}
    #   g_score = {start: 0}
    #
    #   while open_heap:
    #       _, g, current = heappop(open_heap)
    #       if current == goal: return reconstruct_path(came_from, current)
    #
    #       for neighbor in grid.get_neighbors(*current):
    #           if not grid.is_passable(*neighbor, robot_id): continue
    #           new_g = g + 1 + congestion_weights.get(neighbor, 0)
    #           if new_g < g_score.get(neighbor, inf):
    #               came_from[neighbor] = current
    #               g_score[neighbor] = new_g
    #               f = new_g + manhattan(neighbor, goal)
    #               heappush(open_heap, (f, new_g, neighbor))
    #
    #   return None  # no path found

    raise NotImplementedError("DSA person: implement astar()")


def reconstruct_path(
    came_from: dict[tuple, tuple], current: tuple[int, int]
) -> list[tuple[int, int]]:
    """Trace back the path from goal to start using the came_from map."""
    path = [current]
    while current in came_from:
        current = came_from[current]
        path.append(current)
    path.reverse()
    return path
