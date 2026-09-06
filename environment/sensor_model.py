"""
sensor_model.py — Sensor Noise & Packet Loss Simulation
[ELECTRONICS/HARDWARE PERSON] — Makes the simulation feel like real hardware.

On real Raspberry Pi AMRs, sensors aren't perfect:
  - LIDAR has ~1-2cm position uncertainty
  - IMU drifts over time
  - Wi-Fi packets get dropped (~1-2% in a busy warehouse)

This module simulates those imperfections.

Integration:
    sensor = SensorModel()
    noisy_pos = sensor.get_noisy_position(robot.position)
    message = sensor.simulate_packet_loss(robot.to_json())
    if message is None:
        pass  # packet was "dropped" — peer doesn't hear this update
"""

import numpy as np
import random


class SensorModel:
    """
    Simulates real sensor imperfections:
      1. Position noise (Gaussian, simulates LIDAR/encoder drift)
      2. Packet loss (Bernoulli, simulates Wi-Fi drops)
      3. Heading jitter (small angular uncertainty)

    All parameters are calibrated to match real Raspberry Pi + RPLidar A1 specs.
    """

    def __init__(
        self,
        position_noise_sigma: float = 0.08,
        packet_loss_prob: float = 0.02,
        seed: int = None,
    ):
        """
        Args:
            position_noise_sigma: Standard deviation of position noise in grid cells.
                                  0.08 ≈ 8cm uncertainty in a warehouse with 1m cells.
            packet_loss_prob:     Probability of a message being dropped (0.0 – 1.0).
                                  0.02 = 2% packet loss (realistic for busy Wi-Fi).
            seed:                 Optional random seed for reproducibility.
        """
        self.noise_sigma = position_noise_sigma
        self.packet_loss_prob = packet_loss_prob
        self._rng = np.random.default_rng(seed)
        self._packet_rng = random.Random(seed)

    def get_noisy_position(self, true_pos: tuple[float, float]) -> tuple[float, float]:
        """
        Add Gaussian noise to robot's true position.

        Args:
            true_pos: (x, y) in grid coordinates (can be float for sub-cell precision).

        Returns:
            (x_noisy, y_noisy) — position with sensor noise applied.

        Physical meaning:
            In a real warehouse with 1m grid cells, sigma=0.08 means
            ~8cm position uncertainty (typical for LIDAR + wheel odometry fusion).
        """
        noise = self._rng.normal(loc=0.0, scale=self.noise_sigma, size=2)
        x_noisy = true_pos[0] + float(noise[0])
        y_noisy = true_pos[1] + float(noise[1])
        return (x_noisy, y_noisy)

    def simulate_packet_loss(self, message: str) -> str | None:
        """
        Simulate Wi-Fi packet loss.

        Args:
            message: The JSON string to (maybe) drop.

        Returns:
            The original message string, or None if "dropped".

        Physical meaning:
            In a warehouse with multiple 2.4GHz devices, expect 1-3% packet loss
            on Wi-Fi. Our P2P protocol must handle missing updates gracefully —
            robots use their last known state of peers when a packet is dropped.
        """
        if self._packet_rng.random() < self.packet_loss_prob:
            return None   # packet dropped
        return message

    def add_heading_jitter(self, heading_deg: float, jitter_sigma: float = 2.0) -> float:
        """
        Add small noise to reported heading (compass/IMU drift).

        Args:
            heading_deg:   True heading in degrees (0 = East, 90 = North).
            jitter_sigma:  Standard deviation in degrees (default 2° for MPU-6050).

        Returns:
            Noisy heading in degrees.
        """
        jitter = float(self._rng.normal(0.0, jitter_sigma))
        return (heading_deg + jitter) % 360.0

    def get_battery_noise(self, true_level: float, sigma: float = 1.0) -> float:
        """
        Add small noise to battery reading (ADC quantization on Pi).

        Returns:
            Noisy battery percentage, clamped to [0, 100].
        """
        noisy = true_level + float(self._rng.normal(0.0, sigma))
        return max(0.0, min(100.0, noisy))

    def to_dict(self) -> dict:
        """Return configuration for logging/dashboard display."""
        return {
            "position_noise_sigma": self.noise_sigma,
            "packet_loss_prob": self.packet_loss_prob,
        }
