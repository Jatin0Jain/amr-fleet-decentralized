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


_trigger_demo = False
_cancel_demo = False
_sim_speed_multiplier = 1

async def dashboard_server(websocket, path="/"):
    """Accept browser dashboard connections and listen for UI commands."""
    global _trigger_demo, _cancel_demo, _sim_speed_multiplier
    _dashboard_clients.add(websocket)
    print(f"[Dashboard] Client connected. Total: {len(_dashboard_clients)}")
    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                if data.get("action") == "trigger_demo":
                    _trigger_demo = True
                    print("[Sim] Demo mode triggered from UI!")
                elif data.get("action") == "cancel_demo":
                    _cancel_demo = True
                    print("[Sim] Demo mode cancelled from UI!")
                elif data.get("action") == "set_speed":
                    _sim_speed_multiplier = data.get("multiplier", 1)
                    print(f"[Sim] Speed multiplier set to {_sim_speed_multiplier}x")
            except Exception as e:
                pass
    finally:
        _dashboard_clients.discard(websocket)
        print(f"[Dashboard] Client disconnected. Total: {len(_dashboard_clients)}")


async def broadcast_to_dashboard(message: str) -> None:
    """Send a JSON string to all connected dashboard browser clients."""
    global _dashboard_clients
    if not _dashboard_clients:
        return
    dead = set()
    for client in list(_dashboard_clients):
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

    Returns:
        Benchmark dict: {"total_time": float, "tasks_completed": int, "collisions": int}
    """
    dt = 1.0 / fps
    resolver = ConflictResolver()

    # Track unassigned tasks separately (we pop from this as tasks are assigned)
    unassigned = list(tasks)
    tick_number = 0
    start_time = time.time()
    tasks_completed_count = 0
    collisions_avoided = 0

    print(f"[Sim] Starting simulation loop at {fps} FPS...")
    print(f"[Sim] {len(robots)} robots, {len(tasks)} tasks to complete")

    # Demo mode state
    demo_running = False
    demo_step_num = 0
    demo_step_tick = 0
    demo_charging_robot = None  # robot currently force-charging
    demo_charging_ticks = 0     # ticks remaining at charging station
    DEMO_STEPS = [
        {"name": "Wi-Fi Dead Zone Injection", "desc": "Spawning dead zones near R2 — watch the latency spike and rerouting!", "duration_ticks": 40, "focus": "networkGrid"},
        {"name": "Emergency Low Battery", "desc": "R1's battery critically low! It abandons its task and reroutes to the nearest charging station.", "duration_ticks": 120, "focus": "robotCards"},
        {"name": "Head-On Collision Avoidance", "desc": "R1 and R3 are on a collision course — conflict resolver decides who yields.", "duration_ticks": 40, "focus": "recentConflicts"},
        {"name": "Task Surge", "desc": "Multiple high-priority tasks assigned simultaneously — watch the allocator distribute work.", "duration_ticks": 50, "focus": "taskList"},
        {"name": "Recovery & Normalization", "desc": "Dead zones cleared, battery recharged — system self-heals and resumes normal operation.", "duration_ticks": 40, "focus": "mapContainer"},
        {"name": "Demo Complete", "desc": "All edge cases demonstrated successfully!", "duration_ticks": 20, "focus": ""},
    ]

    while True:
        global _trigger_demo, _cancel_demo, _sim_speed_multiplier
        
        if _cancel_demo:
            _cancel_demo = False
            _trigger_demo = False
            if demo_running:
                demo_running = False
                demo_step_num = 0
                demo_charging_robot = None
                demo_charging_ticks = 0
                print("[Sim] === DEMO MODE CANCELLED ===")
                await broadcast_to_dashboard(json.dumps({"type": "demo_end"}))
                
        if _trigger_demo and not demo_running:
            _trigger_demo = False
            demo_running = True
            demo_step_num = 0
            demo_step_tick = 0
            demo_charging_robot = None
            demo_charging_ticks = 0
            print("[Sim] === DEMO MODE STARTED ===")

        # Handle demo steps
        if demo_running:
            step = DEMO_STEPS[demo_step_num]
            if demo_step_tick == 0:
                # Announce this step
                print(f"[Demo] Step {demo_step_num + 1}/{len(DEMO_STEPS)}: {step['name']}")
                await broadcast_to_dashboard(json.dumps({
                    "type": "demo_step",
                    "step": demo_step_num + 1,
                    "total": len(DEMO_STEPS),
                    "name": step["name"],
                    "desc": step["desc"],
                    "focus": step["focus"],
                }))
                # Execute the step's action
                if demo_step_num == 0:
                    # Dead zone injection near R2
                    for r in robots:
                        if r.robot_id == "R2":
                            network_model.add_dead_zone(int(r.position[0]), int(r.position[1]))
                            network_model.add_dead_zone(int(r.position[0])+1, int(r.position[1]))
                            network_model.add_dead_zone(int(r.position[0]), int(r.position[1])+1)
                elif demo_step_num == 1:
                    # Force low battery on R1 → pathfind to nearest charging station
                    for r in robots:
                        if r.robot_id == "R1":
                            r.battery = 10.0
                            r.current_task = None  # drop task so it doesn't go to pickup
                            r.task_phase = "pickup"
                            r.grid.clear_reservations(r.robot_id)
                            # Compute path to nearest charging station
                            from environment.warehouse_layout import nearest_charging_station
                            charge_pos = nearest_charging_station(r.position)
                            charge_path = astar(grid, r.position, charge_pos, r.robot_id, r.congestion_weights)
                            if charge_path:
                                r.planned_path = charge_path[1:]  # exclude current position
                            r.status = "moving"  # move first, switch to charging on arrival
                            demo_charging_robot = r
                            demo_charging_ticks = 30  # will count down after arrival
                elif demo_step_num == 2:
                    # Force R1 and R3 toward same location to cause conflict
                    for r in robots:
                        if r.robot_id == "R3":
                            from core.pathfinder import astar
                            target = robots[0].position  # R1's position
                            path = astar(grid, r.position, target, r.robot_id, r.congestion_weights)
                            if path:
                                r.planned_path = path[1:]
                                r.status = "moving"
                elif demo_step_num == 3:
                    # Task surge — nothing special needed, tasks are already being assigned
                    pass
                elif demo_step_num == 4:
                    # Recovery — clear dead zones, restore battery
                    network_model.clear_dead_zones()
                    for r in robots:
                        if r.battery < 50:
                            r.battery = 90.0
                        if r.status == "charging":
                            r.status = "idle"
                            r.planned_path = []
                elif demo_step_num == 5:
                    # Final step — send demo_end
                    pass

            # Handle charging dwell during low battery step
            if demo_charging_robot and demo_charging_ticks > 0:
                # Robot is still walking to charging station
                if demo_charging_robot.planned_path and demo_charging_robot.status == "moving":
                    pass  # let normal step() handle movement
                # Robot arrived at charging station — switch to charging and dwell
                elif not demo_charging_robot.planned_path and demo_charging_robot.status != "charging":
                    demo_charging_robot.status = "charging"
                    demo_charging_robot.velocity = (0, 0)
                # Robot is dwelling at charging station
                elif demo_charging_robot.status == "charging":
                    demo_charging_ticks -= 1
                    demo_charging_robot.battery = min(100.0, demo_charging_robot.battery + 2.5)
                    demo_charging_robot.planned_path = []  # keep it stationary
                    if demo_charging_ticks <= 0:
                        demo_charging_robot.status = "idle"
                        demo_charging_robot.battery = 95.0
                        demo_charging_robot = None

            demo_step_tick += 1
            if demo_step_tick >= step["duration_ticks"]:
                demo_step_tick = 0
                demo_step_num += 1
                if demo_step_num >= len(DEMO_STEPS):
                    demo_running = False
                    demo_step_num = 0
                    demo_charging_robot = None
                    demo_charging_ticks = 0
                    print("[Sim] === DEMO MODE ENDED ===")
                    await broadcast_to_dashboard(json.dumps({
                        "type": "demo_end",
                    }))

        tick_start = time.time()
        tick_number += 1

        # ── 1. Resolve conflicts for all robots centrally ──
        actions = resolver.resolve(robots, grid)

        # Count conflict events for benchmark
        waiting_count = sum(1 for a in actions.values() if a in ("wait", "reroute"))
        if waiting_count > 0:
            collisions_avoided += waiting_count

        # ── 2. Step each robot ──
        for robot in robots:
            other = [r for r in robots if r is not robot]
            robot.step(dt=dt, other_robots=other)

        # ── 3. Check for task completions (robots that became idle) ──
        for robot in robots:
            if robot.status == "idle" and robot.current_task is None:
                # Count completed tasks via transition to idle
                pass

        # ── 4. Allocate pending tasks to idle robots ──
        if unassigned:
            idle_robot_states = [
                RobotState(r.robot_id, r.position, r.battery, r.status)
                for r in robots if r.status == "idle"
            ]
            pending_specs = [
                TaskSpec(t.task_id, t.pickup, t.dropoff, t.priority)
                for t in unassigned
            ]
            assignments = allocator.allocate(pending_specs, idle_robot_states)

            for task_id, robot_id in assignments.items():
                robot = next((r for r in robots if r.robot_id == robot_id), None)
                task = next((t for t in unassigned if t.task_id == task_id), None)
                if robot and task:
                    robot.assign_task(task)
                    unassigned.remove(task)
                    print(f"[Sim] Assigned {task_id} -> {robot_id}")

        # ── 5. Track task completions ──
        active_task_ids = set()
        for robot in robots:
            if robot.current_task:
                active_task_ids.add(robot.current_task.task_id)

        tasks_completed_count = (
            len(tasks) - len(unassigned) - len(active_task_ids)
        )

        # ── 6. Collect network latency for each robot ──
        network_info = []
        for robot in robots:
            zone_info = network_model.update_robot_zone_status(robot.robot_id, robot.position)
            latency_ms = round(network_model.get_latency(robot.position) * 1000, 1)
            network_info.append({
                "robot_id": robot.robot_id,
                "latency_ms": latency_ms,
                "in_dead_zone": network_model.in_dead_zone(robot.position),
                "zone_event": zone_info.get("event"),
            })

        # ── 7. Broadcast full fleet state to dashboard ──
        fleet_state = {
            "type": "fleet_update",
            "robots": [json.loads(r.to_json()) for r in robots],
            "grid": grid.to_dict(),
            "dead_zones": network_model.get_dashboard_overlay(),
            "network": network_info,
            "tasks_remaining": len(unassigned),
            "tasks_completed": tasks_completed_count,
            "conflicts_avoided": collisions_avoided,
            "recent_conflicts": getattr(resolver, "recent_conflicts", []),
            "tick": tick_number,
        }
        await broadcast_to_dashboard(json.dumps(fleet_state))

        # ── 8. Log tick for ML training ──
        logger.log_tick(time.time(), robots)

        # ── 9. Exit condition: all tasks complete ──
        all_done = (
            len(unassigned) == 0
            and all(r.status in ("idle", "charging") or r.current_task is None
                    for r in robots)
        )
        if all_done:
            total_time = time.time() - start_time
            print(f"\n[Sim] All tasks completed in {total_time:.1f}s!")
            print(f"[Sim] Ticks: {tick_number} | Conflicts avoided: {collisions_avoided}")
            return {
                "total_time": round(total_time, 2),
                "tasks_completed": len(tasks),
                "collisions_avoided": collisions_avoided,
                "ticks": tick_number,
                "mode": "benchmark" if benchmark_mode else "normal",
            }

        # ── 10. Benchmark timeout (prevent infinite loop) ──
        if benchmark_mode and time.time() - start_time > 300:  # 5 min max
            total_time = time.time() - start_time
            print(f"[Sim] Benchmark timeout after {total_time:.1f}s")
            return {
                "total_time": round(total_time, 2),
                "tasks_completed": tasks_completed_count,
                "collisions_avoided": collisions_avoided,
                "ticks": tick_number,
                "mode": "benchmark_timeout",
            }

        # ── 11. Sleep to maintain target FPS (adjusted by speed multiplier) ──
        elapsed = time.time() - tick_start
        target_sleep = (dt / _sim_speed_multiplier)
        sleep_time = max(0, target_sleep - elapsed)
        await asyncio.sleep(sleep_time)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def _create_robots(scenario, grid, resolver):
    """Helper to create fresh robot instances from a scenario config."""
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
    return robots


def _create_tasks(scenario):
    """Helper to create fresh task instances from a scenario config."""
    return [
        Task(
            task_id=t["task_id"],
            pickup=tuple(t["pickup"]),
            dropoff=tuple(t["dropoff"]),
            priority=t.get("priority", 1),
        )
        for t in scenario["tasks"]
    ]


async def main():
    parser = argparse.ArgumentParser(description="AMR Fleet Simulation")
    parser.add_argument("--scenario", choices=["easy", "medium", "hard"],
                        default="medium", help="Scenario difficulty")
    parser.add_argument("--benchmark", action="store_true",
                        help="Run benchmark mode (no UI, measure performance)")
    parser.add_argument("--fps", type=int, default=4, help="Simulation FPS")
    parser.add_argument("--dashboard-port", type=int, default=8080,
                        help="WebSocket port for dashboard")
    parser.add_argument("--continuous", action="store_true",
                        help="Run in continuous mode (auto-restart after completion)")
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

    # --- ML allocator ---
    allocator = TaskAllocator(mode="greedy")   # upgrade to "ml" on Day 2

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
        round_number = 0
        last_robot_positions = {}  # Persist positions across rounds
        while True:
            round_number += 1

            # --- Fresh robots and tasks each round ---
            resolver = ConflictResolver()
            robots = _create_robots(scenario, grid, resolver)
            tasks = _create_tasks(scenario)
            logger = DataLogger("data/sim_log.jsonl")

            # Override start positions with last known positions from previous round
            if last_robot_positions:
                for robot in robots:
                    if robot.robot_id in last_robot_positions:
                        robot.position = last_robot_positions[robot.robot_id]
                    print(f"[Sim] {robot.robot_id} resuming at {robot.position}")

            for robot in robots:
                print(f"[Sim] Created {robot}")

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

            # Save robot end positions for next round
            last_robot_positions = {r.robot_id: r.position for r in robots}

            logger.close()
            print(f"[Sim] Round {round_number} Done!")
            print(f"[Sim] Results: {json.dumps(result, indent=2)}")

            if args.benchmark:
                with open("benchmark_results.json", "w") as f:
                    json.dump(result, f, indent=2)
                print("[Sim] Saved benchmark_results.json")

            if not args.continuous:
                break

            # --- Cooldown: broadcast "round complete" for 5 seconds ---
            print(f"[Sim] Round {round_number} complete. Restarting in 5 seconds...")

            # Send a round_complete event to dashboard
            round_msg = json.dumps({
                "type": "event",
                "event_type": "round_complete",
                "robot_id": "SIM",
                "description": f"Round {round_number} complete — {result['tasks_completed']} tasks in {result['total_time']}s. Restarting...",
            })
            await broadcast_to_dashboard(round_msg)

            # Keep broadcasting idle state during cooldown so dashboard stays connected
            for i in range(50):  # 5 seconds at 10fps
                cooldown_state = {
                    "type": "fleet_update",
                    "robots": [json.loads(r.to_json()) for r in robots],
                    "grid": grid.to_dict(),
                    "dead_zones": network_model.get_dashboard_overlay(),
                    "network": [],
                    "tasks_remaining": 0,
                    "tasks_completed": result["tasks_completed"],
                    "conflicts_avoided": result["collisions_avoided"],
                    "tick": 0,
                }
                await broadcast_to_dashboard(json.dumps(cooldown_state))
                await asyncio.sleep(0.1)

            # Re-generate scenario for variety (but robot starts will be overridden)
            scenario = generate_scenario(
                num_robots=3,
                num_tasks=10,
                difficulty=args.scenario,
            )
            print(f"\n[Sim] === Starting Round {round_number + 1} ===")
            print(f"[Sim] Scenario '{args.scenario}': "
                  f"{len(scenario['robots'])} robots, {len(scenario['tasks'])} tasks")


if __name__ == "__main__":
    asyncio.run(main())
