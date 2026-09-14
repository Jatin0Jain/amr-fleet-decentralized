"""
grid.py — Warehouse Grid Representation
[DSA PERSON] — Your starting point.

Represents the 20x20 warehouse as a 2D grid.
Cells can be: FREE, OBSTACLE, or RESERVED by a robot.
"""

import time

# Cell state constants
FREE = 0
OBSTACLE = 1
RESERVED = 2


class WarehouseGrid:
    """
    20×20 grid representing the warehouse floor.

    Coordinate system:
        (0,0) = top-left corner
        x increases right, y increases down

    Usage:
        grid = WarehouseGrid()
        grid.add_obstacle(5, 3)
        grid.reserve_cell(5, 4, "R1", duration=1.0)
        if grid.is_passable(5, 4, "R1"):
            ...
    """

    def __init__(self, width: int = 20, height: int = 20):
        self.width = width
        self.height = height

        # 2D list: grid[y][x] = FREE | OBSTACLE
        self.cells = [[FREE] * width for _ in range(height)]

        # Reservations: {(x, y): {"robot_id": str, "expires_at": float}}
        self.reservations: dict[tuple, dict] = {}

    # ------------------------------------------------------------------
    # Obstacle management
    # ------------------------------------------------------------------

    def add_obstacle(self, x: int, y: int) -> None:
        """Mark cell (x, y) as a permanent obstacle (shelf, wall, etc.)."""
        if self._in_bounds(x, y):
            self.cells[y][x] = OBSTACLE

    def add_obstacle_rect(self, x1: int, y1: int, x2: int, y2: int) -> None:
        """Add a rectangular block of obstacles from (x1,y1) to (x2,y2) inclusive."""
        for y in range(min(y1, y2), max(y1, y2) + 1):
            for x in range(min(x1, x2), max(x1, x2) + 1):
                self.add_obstacle(x, y)

    def remove_obstacle(self, x: int, y: int) -> None:
        """Remove an obstacle from cell (x, y)."""
        if self._in_bounds(x, y):
            self.cells[y][x] = FREE

    def is_obstacle(self, x: int, y: int) -> bool:
        """Return True if (x, y) is a permanent obstacle."""
        return self._in_bounds(x, y) and self.cells[y][x] == OBSTACLE

    # ------------------------------------------------------------------
    # Reservation management (time-space planning)
    # ------------------------------------------------------------------

    def reserve_cell(self, x: int, y: int, robot_id: str, duration: float = 1.0) -> bool:
        """
        Reserve cell (x, y) for robot_id for `duration` seconds.

        Returns True if reservation was successful, False if already
        reserved by a DIFFERENT robot.
        """
        self._expire_old_reservations()
        existing = self.reservations.get((x, y))
        if existing is not None and existing["robot_id"] != robot_id:
            # Cell is held by a different robot — cannot reserve
            return False
        # Either free, or same robot is re-reserving — allow it
        self.reservations[(x, y)] = {
            "robot_id": robot_id,
            "expires_at": time.time() + duration,
        }
        return True

    def clear_reservations(self, robot_id: str) -> None:
        """Release all reservations held by robot_id."""
        keys_to_remove = [
            cell for cell, data in self.reservations.items()
            if data["robot_id"] == robot_id
        ]
        for key in keys_to_remove:
            del self.reservations[key]

    def _expire_old_reservations(self) -> None:
        """Remove reservations that have passed their expiry time."""
        now = time.time()
        expired = [cell for cell, data in self.reservations.items()
                   if data["expires_at"] < now]
        for cell in expired:
            del self.reservations[cell]

    def is_passable(self, x: int, y: int, robot_id: str) -> bool:
        """
        Return True if robot_id can enter cell (x, y).

        A cell is passable if:
        1. It is within bounds
        2. It is not a permanent obstacle
        3. It is not reserved by a DIFFERENT robot
        """
        self._expire_old_reservations()
        if not self._in_bounds(x, y):
            return False
        if self.cells[y][x] == OBSTACLE:
            return False
        existing = self.reservations.get((x, y))
        if existing is not None and existing["robot_id"] != robot_id:
            return False
        return True

    def get_neighbors(self, x: int, y: int) -> list[tuple[int, int]]:
        """Return list of valid (x, y) neighbors (4-directional, no diagonals)."""
        candidates = [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]
        return [(nx, ny) for nx, ny in candidates if self._in_bounds(nx, ny)]

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def _in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def to_dict(self) -> dict:
        """Serialize grid state (obstacles only) for dashboard rendering."""
        obstacles = []
        for y in range(self.height):
            for x in range(self.width):
                if self.cells[y][x] == OBSTACLE:
                    obstacles.append({"x": x, "y": y})
        return {
            "width": self.width,
            "height": self.height,
            "obstacles": obstacles,
        }

    def __repr__(self) -> str:
        lines = []
        for y in range(self.height):
            row = ""
            for x in range(self.width):
                if self.cells[y][x] == OBSTACLE:
                    row += "█"
                elif (x, y) in self.reservations:
                    row += "R"
                else:
                    row += "·"
            lines.append(row)
        return "\n".join(lines)
