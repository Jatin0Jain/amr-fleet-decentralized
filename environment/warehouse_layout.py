"""
warehouse_layout.py — Physical Warehouse Definition
[ENVIRONMENT PERSON] — Define shelves, charging stations, corridors.

This file is imported by EVERYONE. Keep it stable after Day 1 morning.
"""

from core.grid import WarehouseGrid

# ---------------------------------------------------------------------------
# Warehouse configuration (20×20 grid)
# ---------------------------------------------------------------------------
WAREHOUSE_CONFIG = {
    "size": (20, 20),

    # Shelf rows: each entry is a rectangle (x1, y1) → (x2, y2)
    "shelf_rows": [
        (2, 2, 2, 8),    # Column A
        (5, 2, 5, 8),    # Column B
        (8, 2, 8, 8),    # Column C
        (11, 2, 11, 8),  # Column D
        (14, 2, 14, 8),  # Column E
        (2, 11, 2, 17),  # Column A (lower)
        (5, 11, 5, 17),  # Column B (lower)
        (8, 11, 8, 17),  # Column C (lower)
        (11, 11, 11, 17),# Column D (lower)
        (14, 11, 14, 17),# Column E (lower)
    ],

    # Charging stations (free cells where robots go when battery < 15%)
    "charging_stations": [(0, 0), (0, 19), (19, 0), (19, 19)],

    # Pickup zones (where goods are collected)
    "pickup_zones": [(1, 5), (1, 14), (17, 5), (17, 14), (9, 0)],

    # Dropoff zones (where goods are delivered)
    "dropoff_zones": [(9, 19), (0, 9), (19, 9), (9, 9)],

    # Narrow corridors between shelves (choke points — 1 cell wide)
    # These are the gaps between shelf columns: x=3, x=6, x=9, x=12
    "narrow_corridors": [
        (3, 5), (6, 5), (9, 5), (12, 5),
        (3, 14), (6, 14), (9, 14), (12, 14),
    ],
}


def build_warehouse() -> WarehouseGrid:
    """
    Construct and return the WarehouseGrid with all obstacles placed.

    Returns:
        Configured WarehouseGrid instance ready for simulation.
    """
    width, height = WAREHOUSE_CONFIG["size"]
    grid = WarehouseGrid(width=width, height=height)

    # Place shelf obstacles
    for (x1, y1, x2, y2) in WAREHOUSE_CONFIG["shelf_rows"]:
        grid.add_obstacle_rect(x1, y1, x2, y2)

    # Outer walls (border)
    # (Optional: uncomment to add solid borders)
    # for x in range(width):
    #     grid.add_obstacle(x, 0)
    #     grid.add_obstacle(x, height - 1)
    # for y in range(height):
    #     grid.add_obstacle(0, y)
    #     grid.add_obstacle(width - 1, y)

    return grid


def get_charging_stations() -> list[tuple[int, int]]:
    return [tuple(c) for c in WAREHOUSE_CONFIG["charging_stations"]]


def get_pickup_zones() -> list[tuple[int, int]]:
    return [tuple(p) for p in WAREHOUSE_CONFIG["pickup_zones"]]


def get_dropoff_zones() -> list[tuple[int, int]]:
    return [tuple(d) for d in WAREHOUSE_CONFIG["dropoff_zones"]]


def nearest_charging_station(pos: tuple[int, int]) -> tuple[int, int]:
    """Return the nearest charging station to `pos` using Manhattan distance."""
    stations = get_charging_stations()
    return min(stations, key=lambda s: abs(s[0] - pos[0]) + abs(s[1] - pos[1]))
