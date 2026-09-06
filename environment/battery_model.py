"""
battery_model.py — Realistic Battery Drain Simulation
[ELECTRONICS/HARDWARE PERSON] — Models real LiPo battery behavior on AMRs.

Integration:
    battery = BatteryModel(capacity_pct=100.0)
    new_level = battery.drain(action="moving", dt=0.1)
    if battery.should_charge():
        robot.status = "charging"
"""

import time


# Drain rates in % per second for each action
DRAIN_RATES = {
    "moving": 0.033,      # ~2% per minute
    "turning": 0.050,     # ~3% per minute (motors working harder)
    "idle": 0.008,        # ~0.5% per minute (standby power)
    "waiting": 0.008,     # same as idle
    "charging": -0.5,     # charging: +30% per minute (recharging)
    "blocked": 0.012,     # slightly more than idle (systems still active)
}

# Multiplier when carrying heavy load (>10kg)
LOAD_MULTIPLIER = 1.5

# Battery thresholds
CRITICAL_THRESHOLD = 10.0   # % — emergency: must charge now
LOW_THRESHOLD = 20.0        # % — should plan to charge soon
FULL_THRESHOLD = 95.0       # % — stop charging


class BatteryModel:
    """
    Simulates the battery drain of an AMR with a LiPo battery pack.

    Based on a 10,000mAh / 25.9V pack (typical for Raspberry Pi AMR).
    Simplified to percentage for simulation.

    Usage:
        model = BatteryModel(initial_pct=100.0)
        for each tick:
            model.drain(action=robot.status, dt=0.1, heavy_load=False)
            robot.battery = model.level
            if model.should_charge():
                trigger_charge_routine(robot)
    """

    def __init__(self, initial_pct: float = 100.0, load_heavy: bool = False):
        """
        Args:
            initial_pct: Starting battery percentage (0-100).
            load_heavy:  Whether robot is carrying a heavy load (increases drain).
        """
        self.level: float = max(0.0, min(100.0, initial_pct))
        self.load_heavy: bool = load_heavy
        self._charge_start_time: float = 0.0
        self.total_energy_consumed: float = 0.0  # % consumed over session

    def drain(self, action: str, dt: float) -> float:
        """
        Update battery level for one simulation tick.

        Args:
            action: Current robot status (must be a key in DRAIN_RATES).
            dt:     Time delta in seconds (e.g. 0.1 for 10 FPS).

        Returns:
            Updated battery level (0.0 – 100.0).
        """
        rate = DRAIN_RATES.get(action, DRAIN_RATES["idle"])

        # Apply load multiplier for heavy loads (but not while charging)
        if self.load_heavy and action not in ("charging", "idle"):
            rate *= LOAD_MULTIPLIER

        delta = rate * dt

        if action == "charging":
            # Charging: add power (rate is negative drain = positive gain)
            self.level = min(100.0, self.level - delta)   # rate is already negative
            if self.level >= FULL_THRESHOLD:
                self.level = FULL_THRESHOLD
        else:
            self.level = max(0.0, self.level - delta)
            self.total_energy_consumed += abs(delta)

        return self.level

    def should_charge(self) -> bool:
        """Return True if robot should go to a charging station."""
        return self.level <= LOW_THRESHOLD

    def is_critical(self) -> bool:
        """Return True if battery is critically low — robot must stop and charge."""
        return self.level <= CRITICAL_THRESHOLD

    def is_full(self) -> bool:
        """Return True if battery is sufficiently charged to resume work."""
        return self.level >= FULL_THRESHOLD

    def charge_tick(self, dt: float) -> float:
        """Convenience method: apply charging for one tick."""
        return self.drain("charging", dt)

    def get_status_color(self) -> str:
        """Return CSS color string for dashboard battery bar."""
        if self.level >= 50:
            return "#22c55e"   # green
        elif self.level >= LOW_THRESHOLD:
            return "#f59e0b"   # amber
        else:
            return "#ef4444"   # red

    def to_dict(self) -> dict:
        return {
            "level": round(self.level, 1),
            "should_charge": self.should_charge(),
            "is_critical": self.is_critical(),
            "color": self.get_status_color(),
        }

    def __repr__(self) -> str:
        return f"Battery({self.level:.1f}%)"
