"""
scenario_generator.py — Generate Test Scenarios
[ENVIRONMENT PERSON] — Create robot start positions and task lists.

Provides three difficulty presets that create increasingly complex
path conflicts for testing collision avoidance.
"""

import random
from environment.warehouse_layout import get_pickup_zones, get_dropoff_zones, WAREHOUSE_CONFIG


def generate_scenario(
    num_robots: int = 3,
    num_tasks: int = 10,
    difficulty: str = "medium",
    seed: int = 42,
) -> dict:
    """
    Generate a complete simulation scenario.

    Args:
        num_robots:  Number of robots (default 3).
        num_tasks:   Number of tasks to assign.
        difficulty:  "easy" | "medium" | "hard"
        seed:        Random seed for reproducibility.

    Returns:
        {
          "robots": [{"robot_id": "R1", "start": [x, y]}, ...],
          "tasks":  [{"task_id": "T1", "pickup": [x,y], "dropoff": [x,y], "priority": int}, ...]
        }

    Difficulty descriptions:
        easy   — robots start far apart, tasks use different corridors (no conflicts expected)
        medium — some path overlaps, 1-2 choke points involved (expected 2-4 conflicts)
        hard   — all robots converge on same narrow corridor (stress test for deadlocks)
    """
    random.seed(seed)
    pickups = get_pickup_zones()
    dropoffs = get_dropoff_zones()

    if difficulty == "easy":
        robot_starts = [
            [0, 0],   # R1 top-left
            [19, 0],  # R2 top-right
            [0, 19],  # R3 bottom-left
        ]
        # Tasks use only separate halves of the warehouse
        task_list = _generate_tasks_easy(num_tasks, pickups, dropoffs, seed)

    elif difficulty == "medium":
        robot_starts = [
            [0, 9],   # R1 left middle
            [19, 9],  # R2 right middle
            [9, 0],   # R3 top center
        ]
        task_list = _generate_tasks_medium(num_tasks, pickups, dropoffs, seed)

    else:  # hard
        # All robots start at corners, all tasks route through center (9,9)
        robot_starts = [
            [0, 0],
            [19, 0],
            [19, 19],
        ]
        task_list = _generate_tasks_hard(num_tasks, seed)

    # Trim to num_robots
    robot_starts = robot_starts[:num_robots]
    robots = [
        {"robot_id": f"R{i+1}", "start": robot_starts[i]}
        for i in range(len(robot_starts))
    ]

    return {"robots": robots, "tasks": task_list, "difficulty": difficulty}


def _generate_tasks_easy(n, pickups, dropoffs, seed):
    random.seed(seed)
    tasks = []
    for i in range(n):
        pickup = random.choice(pickups)
        dropoff = random.choice([d for d in dropoffs if d != pickup])
        tasks.append({
            "task_id": f"T{i+1:02d}",
            "pickup": list(pickup),
            "dropoff": list(dropoff),
            "priority": 1,
        })
    return tasks


def _generate_tasks_medium(n, pickups, dropoffs, seed):
    random.seed(seed)
    tasks = []
    for i in range(n):
        pickup = random.choice(pickups)
        dropoff = random.choice(dropoffs)
        priority = random.randint(1, 3)
        tasks.append({
            "task_id": f"T{i+1:02d}",
            "pickup": list(pickup),
            "dropoff": list(dropoff),
            "priority": priority,
        })
    return tasks


def _generate_tasks_hard(n, seed):
    """Force all tasks to pass through the center corridor (choke point stress test)."""
    random.seed(seed)
    # Pickups on the top, dropoffs on the bottom — all paths go through center
    top_pickups = [(1, 1), (9, 0), (17, 1)]
    bottom_dropoffs = [(1, 18), (9, 19), (17, 18)]
    tasks = []
    for i in range(n):
        pickup = random.choice(top_pickups)
        dropoff = random.choice(bottom_dropoffs)
        tasks.append({
            "task_id": f"T{i+1:02d}",
            "pickup": list(pickup),
            "dropoff": list(dropoff),
            "priority": random.randint(1, 5),
        })
    return tasks
