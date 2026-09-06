"""
data_logger.py — Simulation Data Logger for ML Training
[ML PERSON] — Logs robot positions each tick so you can train the congestion model.

Usage:
    logger = DataLogger("data/sim_log.jsonl")
    # each tick:
    logger.log_tick(t=time.time(), robots=[r1, r2, r3])
    logger.close()
"""

import json
import os
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.robot_agent import Robot


class DataLogger:
    """
    Appends one JSON line per simulation tick to a log file.
    Used to generate training data for CongestionPredictor.

    Log format (one line per tick):
        {"t": 1728000000.123, "robots": [{"id": "R1", "x": 5, "y": 3}, ...]}
    """

    def __init__(self, path: str = "data/sim_log.jsonl"):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.path = path
        self._file = open(path, "a", buffering=1)   # line-buffered
        self._tick_count = 0

    def log_tick(self, t: float, robots: list["Robot"]) -> None:
        """Log all robot positions at time t."""
        entry = {
            "t": t,
            "robots": [
                {"id": r.robot_id, "x": r.position[0], "y": r.position[1],
                 "status": r.status, "battery": round(r.battery, 1)}
                for r in robots
            ],
        }
        self._file.write(json.dumps(entry) + "\n")
        self._tick_count += 1

    def close(self) -> None:
        self._file.close()
        print(f"[DataLogger] Wrote {self._tick_count} ticks to {self.path}")

    def __del__(self):
        try:
            self._file.close()
        except Exception:
            pass
