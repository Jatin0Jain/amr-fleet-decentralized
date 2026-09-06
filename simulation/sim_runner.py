"""
sim_runner.py — Master Simulation Orchestrator
[P2P PERSON] — The main entry point. Launches all robots and the simulation loop.

Run with:
    python simulation/sim_runner.py
    python simulation/sim_runner.py --scenario medium
    python simulation/sim_runner.py --benchmark

This file is the INTEGRATION HUB. It imports from every other module.
"""

import asyncio
import argparse
import json
import time
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.grid import WarehouseGrid
from core.robot_agent import Robot, Task
from core.conflict import ConflictResolver
from environment.warehouse_layout import build_warehouse, WAREHOUSE_CONFIG
from environment.scenario_generator import generate_scenario
from environment.battery_model import BatteryModel
from environment.sensor_model import SensorModel
from environment.network_model import NetworkModel
from ml.task_allocator import TaskAllocator, TaskSpec, RobotState
from ml.data_logger import DataLogger

# ---------------------------------------------------------------------------
# Dashboard WebSocket broadcaster
# ---------------------------------------------------------------------------

# Connected dashboard clients
_dashboard_clients: set = set()


async def dashboard_server(websocket, path="/"):
    """Accept browser dashboard connections and keep them alive."""
    _dashboard_clients.add(websocket)
    print(f"[Dashboard] Client connected. Total: {len(_dashboard_clients)}")
    try:
        await websocket.wait_closed()
    finally:
        _dashboard_clients.discard(websocket)
        print(f"[Dashboard] Client disconnected. Total: {len(_dashboard_clients)}")


async def broadcast_to_dashboard(message: str) -> None:
    """Send a JSON string to all connected dashboard browser clients."""
    if not _dashboard_clients:
        return
    dead = set()
    for client in _dashboard_clients:
        try:
            await client.send(message)
        except Exception:
            dead.add(client)
    _dashboard_clients -= dead


# ---------------------------------------------------------------------------
# Simulation loop
# ---------------------------------------------------------------------------

async def simulation_loop(
    robots: list[Robot],
    grid: WarehouseGrid,
    tasks: list[Task],
    allocator: TaskAllocator,
    logger: DataLogger,
    network_model: NetworkModel,
    fps: int = 10,
    benchmark_mode: bool = False,
) -> dict:
    """
    Main simulation tick loop. Runs at `fps` ticks per second.

    TODO [P2P PERSON]: Implement the loop body.

    Each tick should:
        1. Compute conflict actions for all robots (call resolver centrally):
               resolver = ConflictResolver()
               actions = resolver.resolve(robots, grid)

        2. Step each robot:
               for robot in robots:
                   robot.step(dt=1/fps, other_robots=[r for r in robots if r != robot])

        3. Allocate pending tasks to idle robots:
               idle = [r for r in robots if r.status == "idle"]
               robot_states = [RobotState(r.robot_id, r.position, r.battery, r.status) for r in robots]
               pending_tasks = [TaskSpec(t.task_id, t.pickup, t.dropoff, t.priority) for t in unassigned]
               assignments = allocator.allocate(pending_tasks, robot_states)
               for task_id, robot_id in assignments.items():
                   robot = next(r for r in robots if r.robot_id == robot_id)
                   task = next(t for t in unassigned if t.task_id == task_id)
                   robot.assign_task(task)
                   unassigned.remove(task)

        4. Broadcast fleet state to dashboard:
               fleet_state = {
                   "type": "fleet_update",
                   "robots": [json.loads(r.to_json()) for r in robots],
                   "grid": grid.to_dict(),
                   "tasks_remaining": len(unassigned),
                   "tick": tick_number,
               }
               await broadcast_to_dashboard(json.dumps(fleet_state))

        5. Log tick for ML training:
               logger.log_tick(time.time(), robots)

        6. Apply network dead zone effects via network_model

        7. Sleep: await asyncio.sleep(1 / fps)

        8. Exit when all tasks complete.

    Returns:
        Benchmark dict: {"total_time": float, "tasks_completed": int, "collisions": int}
    """
    # TODO [P2P PERSON]: Implement simulation loop
    raise NotImplementedError("P2P person: implement simulation_loop()")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def main():
    parser = argparse.ArgumentParser(description="AMR Fleet Simulation")
    parser.add_argument("--scenario", choices=["easy", "medium", "hard"],
                        default="medium", help="Scenario difficulty")
    parser.add_argument("--benchmark", action="store_true",
                        help="Run benchmark mode (no UI, measure performance)")
    parser.add_argument("--fps", type=int, default=10, help="Simulation FPS")
    parser.add_argument("--dashboard-port", type=int, default=8080,
                        help="WebSocket port for dashboard")
    args = parser.parse_args()

    # --- Build warehouse ---
    grid = build_warehouse()
    print(f"[Sim] Warehouse: {grid.width}x{grid.height}")

    # --- Generate scenario ---
    scenario = generate_scenario(
        num_robots=3,
        num_tasks=10,
        difficulty=args.scenario,
    )
    print(f"[Sim] Scenario '{args.scenario}': "
          f"{len(scenario['robots'])} robots, {len(scenario['tasks'])} tasks")

    # --- Create robots ---
    resolver = ConflictResolver()
    robots = []
    for rconf in scenario["robots"]:
        robot = Robot(
            robot_id=rconf["robot_id"],
            start_pos=tuple(rconf["start"]),
            grid=grid,
            resolver=resolver,
            battery_model=BatteryModel(),
            sensor_model=SensorModel(),
        )
        robots.append(robot)
        print(f"[Sim] Created {robot}")

    # --- Task list ---
    tasks = [
        Task(
            task_id=t["task_id"],
            pickup=tuple(t["pickup"]),
            dropoff=tuple(t["dropoff"]),
            priority=t.get("priority", 1),
        )
        for t in scenario["tasks"]
    ]

    # --- ML allocator ---
    allocator = TaskAllocator(mode="greedy")   # upgrade to "ml" on Day 2

    # --- Logger ---
    logger = DataLogger("data/sim_log.jsonl")

    # --- Network model ---
    network_model = NetworkModel()

    # --- Start dashboard server ---
    import websockets as ws_lib
    dashboard_server_task = ws_lib.serve(
        dashboard_server, "localhost", args.dashboard_port
    )
    print(f"[Sim] Dashboard WebSocket listening on ws://localhost:{args.dashboard_port}")
    print(f"[Sim] Open dashboard/index.html in your browser!")

    async with dashboard_server_task:
        result = await simulation_loop(
            robots=robots,
            grid=grid,
            tasks=tasks,
            allocator=allocator,
            logger=logger,
            network_model=network_model,
            fps=args.fps,
            benchmark_mode=args.benchmark,
        )

    logger.close()
    print("[Sim] Done!")
    print(f"[Sim] Results: {json.dumps(result, indent=2)}")

    if args.benchmark:
        # Save benchmark results for DSA person's 20% improvement proof
        with open("benchmark_results.json", "w") as f:
            json.dump(result, f, indent=2)
        print("[Sim] Saved benchmark_results.json")


if __name__ == "__main__":
    asyncio.run(main())
