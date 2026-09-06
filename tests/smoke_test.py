import sys
sys.path.insert(0, '.')
from environment.warehouse_layout import build_warehouse, get_pickup_zones
from environment.battery_model import BatteryModel
from environment.sensor_model import SensorModel
from environment.network_model import NetworkModel
from environment.scenario_generator import generate_scenario
from ml.task_allocator import TaskAllocator, TaskSpec, RobotState
from ml.data_logger import DataLogger
from network.message_broker import make_state_msg, make_conflict_msg, parse_message

print("All modules imported OK")

grid = build_warehouse()
print(f"Warehouse: {grid.width}x{grid.height}, obstacles placed")

battery = BatteryModel(initial_pct=100.0)
lvl = battery.drain('moving', 0.1)
print(f"Battery drain: 100.0 -> {lvl:.3f}%")

sensor = SensorModel(seed=42)
pos = sensor.get_noisy_position((5.0, 3.0))
print(f"Sensor noise: noisy=({pos[0]:.3f}, {pos[1]:.3f})")

net = NetworkModel(seed=42)
lat_normal = net.get_latency((5, 5))
lat_dz = net.get_latency((9, 9))
print(f"Latency normal={lat_normal*1000:.1f}ms  dead_zone={lat_dz*1000:.0f}ms")

sc = generate_scenario(num_robots=3, num_tasks=5, difficulty='hard')
print(f"Scenario: {len(sc['robots'])} robots, {len(sc['tasks'])} tasks")

allocator = TaskAllocator()
tasks = [TaskSpec('T1', (1,5), (9,19), priority=2), TaskSpec('T2', (17,5), (0,9), priority=1)]
robots = [RobotState('R1', (0,0), 90.0, 'idle'), RobotState('R2', (19,0), 75.0, 'idle')]
assignments = allocator.allocate(tasks, robots)
print(f"Allocator: {assignments}")

msg = make_conflict_msg('R1', 5, 3)
mtype, payload = parse_message(msg)
print(f"Message broker: type={mtype} cell={payload['cell']}")

print("\n=== ALL SMOKE TESTS PASSED ===")
