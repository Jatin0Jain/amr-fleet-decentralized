# Hardware Specification — AMR Fleet (SIH2026)

## Compute Unit — Raspberry Pi 4 Model B (4GB RAM)

| Parameter | Value |
|-----------|-------|
| CPU | Broadcom BCM2711, Quad-core Cortex-A72 (ARM v8) 64-bit @ 1.8GHz |
| RAM | 4GB LPDDR4-3200 SDRAM |
| Storage | 32GB Class-10 microSD (OS + code) |
| Wireless | 2.4GHz and 5.0GHz IEEE 802.11ac (Wi-Fi 5), Bluetooth 5.0 |
| I/O | 40-pin GPIO, 2× USB 3.0, 2× USB 2.0, Gigabit Ethernet |
| Power Draw | ~3W idle, ~6-8W under full load |
| Dimensions | 85mm × 56mm × 17mm |

---

## Lidar Sensor — RPLidar A1M8

| Parameter | Value |
|-----------|-------|
| Scan Range | 0.15m – 12m |
| Scan Rate | 5.5Hz (typical), up to 10Hz |
| Angular Resolution | < 1° |
| Interface | UART (115200 baud), micro-USB |
| Power | 5V, 500mA |
| Obstacle Detection | 360° planar scan |
| Used For | Obstacle detection, localization, SLAM |

**Simulation mapping:** `SensorModel.get_noisy_position()` simulates 8cm position uncertainty (RPLidar + encoder fusion).

---

## IMU — MPU-6050 (Gyroscope + Accelerometer)

| Parameter | Value |
|-----------|-------|
| Gyroscope Range | ±250/500/1000/2000°/s |
| Accelerometer Range | ±2/4/8/16g |
| Interface | I2C (up to 400kHz) |
| Power | 3.3V – 5V, 3.9mA active |
| Heading Accuracy | ±2° (simulated in `SensorModel.add_heading_jitter()`) |
| Used For | Velocity estimation, dead reckoning in Wi-Fi dead zones |

---

## Battery Pack — LiPo 10,000mAh / 25.9V

| Parameter | Value |
|-----------|-------|
| Chemistry | Lithium Polymer (LiPo) |
| Capacity | 10,000mAh |
| Nominal Voltage | 25.9V (7S configuration) |
| Peak Discharge | 10C = 100A instantaneous |
| Runtime | ~45 min continuous movement |
| Charge Rate | ~1C = 10A, ~1 hour to full |

**Drain rates modeled in `BatteryModel`:**
- Moving: 0.033%/s (~2%/min)
- Idle/Waiting: 0.008%/s (~0.5%/min)
- Charging: -0.5%/s (+30%/min recovery)
- Critical threshold: 10% → emergency stop
- Low threshold: 20% → route to charging station

---

## Drivetrain — Differential Drive

| Parameter | Value |
|-----------|-------|
| Wheels | 2× 10cm diameter rubber wheels |
| Motors | 2× DC gearmotor 12V, 150 RPM |
| Motor Driver | L298N dual H-bridge |
| Max Speed | ~0.5 m/s |
| Payload | Up to 10kg |

---

## Wi-Fi Network — IEEE 802.11ac (5GHz)

| Zone | Latency | Packet Loss |
|------|---------|-------------|
| Open floor | 1–5ms | 1–3% |
| Near shelving | 50–300ms | 10–20% |
| Dead zone (dense metal) | 500ms–2s | 40–80% |

**Dead zone locations** in simulation (see `NetworkModel`):
- Center warehouse: (9,9), (10,9), (9,10), (10,10) — metal shelving blocks signal
- Behind Column C: (8,4), (8,5), (8,6)
- Far corner: (18,17), (18,18), (17,18)

---

## Power Budget

| Component | Voltage | Current | Power |
|-----------|---------|---------|-------|
| Raspberry Pi 4 | 5V | 3A | 15W |
| RPLidar A1 | 5V | 0.5A | 2.5W |
| MPU-6050 | 3.3V | 3.9mA | ~0.013W |
| 2× Motors (moving) | 12V | 2A each | 48W |
| 2× Motors (idle) | 12V | 0.2A each | 4.8W |
| **Total (moving)** | — | — | **~65.5W** |
| **Total (idle)** | — | — | **~22W** |

**Battery runtime estimate:** 10,000mAh × 25.9V = 259Wh ÷ 65.5W = **~3.95 hours** continuous movement.
