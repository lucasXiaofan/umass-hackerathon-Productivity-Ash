"""
Simple time-dependent tasks management
- Load top 10 most urgent tasks
- Auto-update tasks based on tag (hw/paper_review/meeting/office_hour/research)
- LLM interface for task creation
"""

import json
import os
from datetime import datetime, timedelta

# Task storage path
TASKS_FILE = "/Users/xiaofanlu/Documents/github_repos/hackathon-umass/memory/tasks.json"

def _load_all_tasks():
    """Load all tasks from JSON file"""
    if not os.path.exists(TASKS_FILE):
        os.makedirs(os.path.dirname(TASKS_FILE), exist_ok=True)
        return []

    try:
        with open(TASKS_FILE, 'r') as f:
            data = json.load(f)
            return data.get("tasks", [])
    except:
        return []

def _save_all_tasks(tasks):
    """Save all tasks to JSON file"""
    with open(TASKS_FILE, 'w') as f:
        json.dump({"tasks": tasks}, f, indent=2)

def _calculate_urgency(task):
    """Calculate urgency score - higher = more urgent"""
    if task.get("done"):
        return -1000  # Done tasks go to bottom

    # Calculate days until due
    due_date = datetime.fromisoformat(task["due_date"])
    now = datetime.now()
    days_until = (due_date - now).total_seconds() / 86400

    # Overdue tasks get highest priority
    if days_until < 0:
        urgency = 1000 + abs(days_until)
    else:
        urgency = 100 / (days_until + 1)  # Soon = higher score

    # Tag-based importance
    tag_weights = {
        "hw": 1.5,
        "paper_review": 1.3,
        "meeting": 1.2,
        "office_hour": 1.1,
        "research": 1.0
    }
    urgency *= tag_weights.get(task.get("tag", "other"), 1.0)

    return urgency

def load_top_tasks(count=10):
    """
    Load top N most urgent tasks, sorted by urgency

    Returns list of tasks with fields:
    - name: task name with date for uniqueness
    - tag: hw/paper_review/meeting/office_hour/research
    - due_date: YYYY-MM-DD format
    - done: True/False
    - notes: path to related notes file
    """
    tasks = _load_all_tasks()

    # Sort by urgency
    tasks_with_urgency = [(t, _calculate_urgency(t)) for t in tasks]
    tasks_with_urgency.sort(key=lambda x: x[1], reverse=True)

    # Return top N
    return [t for t, _ in tasks_with_urgency[:count]]

def auto_update_tasks():
    """
    Auto-update tasks based on tag:
    - hw: ignore if past due date
    - paper_review: move deadline 2 days later if not done
    - meeting/office_hour: recurrent, reset to next week if done/passed
    - research: no auto-update
    """
    tasks = _load_all_tasks()
    updated_tasks = []
    now = datetime.now()

    for task in tasks:
        due_date = datetime.fromisoformat(task["due_date"])
        is_past = due_date < now
        tag = task.get("tag", "other")

        # hw: skip if past due date
        if tag == "hw" and is_past and not task.get("done"):
            continue  # Don't add to updated_tasks (remove it)

        # paper_review: extend 2 days if past due and not done
        elif tag == "paper_review" and is_past and not task.get("done"):
            new_date = due_date + timedelta(days=2)
            task["due_date"] = new_date.strftime("%Y-%m-%d")
            updated_tasks.append(task)

        # meeting/office_hour: recurrent, move to next week
        elif tag in ["meeting", "office_hour"]:
            if is_past or task.get("done"):
                # Check if we've reached deadline (if specified)
                if task.get("deadline"):
                    deadline = datetime.fromisoformat(task["deadline"])
                    if due_date >= deadline:
                        continue  # Remove task

                # Move to next week
                next_date = due_date + timedelta(days=7)
                task["due_date"] = next_date.strftime("%Y-%m-%d")
                task["done"] = False
                updated_tasks.append(task)
            else:
                updated_tasks.append(task)

        else:
            # No auto-update, keep as-is
            updated_tasks.append(task)

    _save_all_tasks(updated_tasks)
    return {"updated": len(updated_tasks), "removed": len(tasks) - len(updated_tasks)}

# ============================================================================
# LLM Interface Functions
# ============================================================================

def create_task(name, tag, due_date, done=False, note_directory="", comments="", deadline=None):
    """
    Create a new task (LLM-callable)

    Args:
        name: Task description (will be combined with date for uniqueness)
        tag: hw, paper_review, meeting, office_hour, research
        due_date: YYYY-MM-DD format
        done: completion status (default False)
        note_directory: path to relevant notes file/directory
        comments: explanation of task importance, context, or details
        deadline: for recurrent tasks, final deadline (YYYY-MM-DD)

    Returns:
        dict with success status and task info
    """
    try:
        task = {
            "name": name,
            "tag": tag,
            "due_date": due_date,
            "done": done,
            "note_directory": note_directory,
            "comments": comments,
            "created_at": datetime.now().isoformat()
        }

        if deadline:
            task["deadline"] = deadline

        tasks = _load_all_tasks()
        tasks.append(task)
        _save_all_tasks(tasks)

        return {"success": True, "task": task}
    except Exception as e:
        return {"success": False, "error": str(e)}

def update_task(name, **updates):
    """
    Update a task by name (LLM-callable)

    Args:
        name: task name to find
        **updates: fields to update (done=True, due_date="2025-12-01", etc.)

    Returns:
        dict with success status
    """
    tasks = _load_all_tasks()

    for task in tasks:
        if task["name"] == name:
            task.update(updates)
            _save_all_tasks(tasks)
            return {"success": True, "updated": name}

    return {"success": False, "error": "Task not found"}

def mark_done(name):
    """Mark a task as done by name (LLM-callable)"""
    return update_task(name, done=True)

def get_tasks_summary():
    """Get formatted summary of top 10 tasks (LLM-callable)
    Auto-updates tasks before returning summary."""
    
    # Auto-update tasks
    auto_update_tasks()

    # Load tasks
    tasks = load_top_tasks(10)

    lines = []
    header = "TOP 10 MOST URGENT TASKS"
    lines.append(header)
    lines.append("=" * len(header))
    lines.append("")

    index = 1
    now = datetime.now()

    for task in tasks:
        if task.get("done"):
            continue

        due = datetime.fromisoformat(task["due_date"])
        days = (due - now).days

        if days < 0:
            due_status = "OVERDUE"
        elif days == 0:
            due_status = "DUE TODAY"
        else:
            due_status = f"{days} days left"

        # Task title
        lines.append(f"{index}. {task['name']}")
        index += 1

        # Details (aligned)
        lines.append(f"    Due Date : {task['due_date']} ({due_status})")
        lines.append(f"    Tag      : {task.get('tag', 'other')}")

        if task.get("note_directory"):
            lines.append(f"    Notes    : {task['note_directory']}")

        if task.get("comments"):
            lines.append(f"    Comments : {task['comments']}")

        lines.append("")  # blank line between tasks

    # If nothing to list
    if index == 1:
        lines.append("No pending tasks.")

    # Footer spacing
    lines.append("")

    return "\n".join(lines)

# Example usage
if __name__ == "__main__":
    # Create example tasks
    

    # Show top tasks
    print("\n" + get_tasks_summary())
