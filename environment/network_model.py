"""
network_model.py — Wi-Fi Dead Zone & Latency Simulation
[ELECTRONICS/HARDWARE PERSON] — Simulates the problem statement's core risk.

The problem statement specifically mentions:
  "Wi-Fi dead-zone vulnerabilities"

This module simulates dead zones so we can demonstrate our system handles them.

Integration:
    net = NetworkModel()
    latency = net.get_latency(robot.position)
    if net.in_dead_zone(robot.position):
        # Robot must rely on last known peer states — can't receive updates
        robot.use_stale_peer_data = True
"""

import random
import time


# ---------------------------------------------------------------------------
# Dead zone definitions (cells with poor Wi-Fi signal)
# ---------------------------------------------------------------------------
DEFAULT_DEAD_ZONES = [
    # Center of warehouse (metal shelving blocks signal)
    (9, 9), (10, 9), (9, 10), (10, 10),
    # Behind tall shelf column C
    (8, 4), (8, 5), (8, 6),
    # Corner dead zone
    (18, 18), (18, 17), (17, 18),
]


class NetworkModel:
    """
    Simulates real Wi-Fi network conditions in a warehouse.

    Key behaviors:
      - Normal zones: 1–5ms latency (excellent P2P performance)
      - Weak signal zones: 50–300ms latency (degraded but functional)
      - Dead zones: 500ms–2s latency + high packet loss (near-disconnected)

    When a robot enters a dead zone:
      - It cannot receive fresh peer states
      - It must continue using its LAST KNOWN state for path planning
      - This demonstrates the "decentralized" advantage: robot keeps moving
        without needing a server or peer connection
    """

    def __init__(self, dead_zones: list[tuple] = None, seed: int = None):
        """
        Args:
            dead_zones: List of (x, y) grid cells with poor signal.
                        Defaults to DEFAULT_DEAD_ZONES.
            seed:       Random seed for reproducibility.
        """
        self.dead_zones = set(dead_zones or DEFAULT_DEAD_ZONES)
        self._rng = random.Random(seed)

        # Track which robots are currently in dead zones
        self._robots_in_dead_zone: dict[str, float] = {}  # {robot_id: entered_at}

    def add_dead_zone(self, x: int, y: int) -> None:
        """Dynamically add a dead zone (e.g., triggered by a forklift blocking signal)."""
        self.dead_zones.add((x, y))

    def remove_dead_zone(self, x: int, y: int) -> None:
        self.dead_zones.discard((x, y))

    def in_dead_zone(self, position: tuple[int, int]) -> bool:
        """Return True if the robot at `position` is in a Wi-Fi dead zone."""
        return tuple(position) in self.dead_zones

    def get_latency(self, position: tuple[int, int]) -> float:
        """
        Return simulated message latency in seconds for a robot at `position`.

        Returns:
            Latency in seconds:
              - Normal:    0.001 – 0.005s
              - Weak:      0.050 – 0.300s
              - Dead zone: 0.500 – 2.000s
        """
        pos = tuple(position)

        if pos in self.dead_zones:
            # Dead zone: high latency
            return self._rng.uniform(0.5, 2.0)

        # Check if near a dead zone (1 cell radius = weak signal)
        for dz in self.dead_zones:
            if abs(dz[0] - pos[0]) + abs(dz[1] - pos[1]) <= 1:
                return self._rng.uniform(0.05, 0.3)

        # Normal zone
        return self._rng.uniform(0.001, 0.005)

    def get_packet_loss_rate(self, position: tuple[int, int]) -> float:
        """
        Return packet loss probability for a robot at `position`.

        Returns:
            Float in [0.0, 1.0]:
              - Normal:    0.01 – 0.03 (1–3%)
              - Weak:      0.10 – 0.20 (10–20%)
              - Dead zone: 0.40 – 0.80 (40–80%)
        """
        pos = tuple(position)
        if pos in self.dead_zones:
            return self._rng.uniform(0.4, 0.8)
        for dz in self.dead_zones:
            if abs(dz[0] - pos[0]) + abs(dz[1] - pos[1]) <= 1:
                return self._rng.uniform(0.10, 0.20)
        return self._rng.uniform(0.01, 0.03)

    def update_robot_zone_status(self, robot_id: str, position: tuple) -> dict:
        """
        Track zone entry/exit events for the event log.

        Returns:
            {"event": "entered_dead_zone" | "exited_dead_zone" | None,
             "robot_id": str, "position": tuple}
        """
        in_dz = self.in_dead_zone(position)
        was_in_dz = robot_id in self._robots_in_dead_zone

        event = None
        if in_dz and not was_in_dz:
            self._robots_in_dead_zone[robot_id] = time.time()
            event = "entered_dead_zone"
        elif not in_dz and was_in_dz:
            del self._robots_in_dead_zone[robot_id]
            event = "exited_dead_zone"

        return {
            "event": event,
            "robot_id": robot_id,
            "position": list(position),
            "latency_ms": round(self.get_latency(position) * 1000, 1),
        }

    def get_dashboard_overlay(self) -> list[dict]:
        """Return dead zone cell list for dashboard to render as red overlay."""
        return [{"x": x, "y": y, "type": "dead_zone"} for x, y in self.dead_zones]
