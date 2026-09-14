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
    """
    if congestion_weights is None:
        congestion_weights = {}

    # Edge case: already at goal
    if start == goal:
        return [start]

    # open_heap entries: (f_score, g_score, node)
    # Using g_score as tiebreaker ensures consistent expansion
    open_heap = []
    heapq.heappush(open_heap, (manhattan(start, goal), 0, start))

    came_from: dict[tuple, tuple] = {}
    g_score: dict[tuple, float] = {start: 0}
    # Track visited to avoid reprocessing
    closed: set[tuple] = set()

    while open_heap:
        f, g, current = heapq.heappop(open_heap)

        if current in closed:
            continue
        closed.add(current)

        if current == goal:
            return reconstruct_path(came_from, current)

        for neighbor in grid.get_neighbors(*current):
            if neighbor in closed:
                continue
            # Skip cells that are impassable (obstacles or reserved by others)
            if not grid.is_passable(*neighbor, robot_id):
                continue

            # Cost: 1 per step + congestion penalty from ML
            step_cost = 1.0 + congestion_weights.get(neighbor, 0.0)
            new_g = g + step_cost

            if new_g < g_score.get(neighbor, float("inf")):
                came_from[neighbor] = current
                g_score[neighbor] = new_g
                f_new = new_g + manhattan(neighbor, goal)
                heapq.heappush(open_heap, (f_new, new_g, neighbor))

    return None  # No path found


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
