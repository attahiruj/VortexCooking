import json
import os
import time
from typing import List, Dict, Any

class TaskManager:
    """
    Manages saving, loading, and executing robot task sequences.
    A task consists of multiple actions, where each action is a set of servo positions (in PWM values)
    with a delay to the next action.
    """
    def __init__(self, controller=None):
        self.tasks_file = "tasks.json"
        self.controller = controller
        self.tasks = self._load_tasks()
    
    def _load_tasks(self) -> Dict[str, Any]:
        """Load tasks from the JSON file."""
        if os.path.exists(self.tasks_file):
            try:
                with open(self.tasks_file, "r") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                print(f"Error loading {self.tasks_file}, file may be corrupted")
                return {}
        return {}
    
    def _save_tasks(self) -> bool:
        """Save tasks to the JSON file."""
        try:
            with open(self.tasks_file, "w") as f:
                json.dump(self.tasks, f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving tasks: {e}")
            return False
    
    def get_task_names(self) -> List[str]:
        """Get a list of all task names."""
        return list(self.tasks.keys())
    
    def save_task(self, task_name: str, actions: List[Dict[str, Any]]) -> bool:
        """
        Save a task with given name and actions.
        
        Args:
            task_name: Name of the task
            actions: List of action dictionaries, each containing:
                - positions: Dictionary mapping servo names to angles
                - delay: Time in milliseconds to wait after executing the action
        
        Returns:
            bool: True if the task was saved successfully
        """
        if not task_name:
            return False
            
        self.tasks[task_name] = {"actions": actions}
        return self._save_tasks()
    
    def delete_task(self, task_name: str) -> bool:
        """Delete a task by name."""
        if task_name in self.tasks:
            del self.tasks[task_name]
            return self._save_tasks()
        return False
    
    def get_task(self, task_name: str) -> Dict[str, Any]:
        """Get a task's details by name."""
        return self.tasks.get(task_name, {})
    
    def execute_task(self, task_name: str, speed: int = 300, callback=None) -> bool:
        """
        Execute all actions in a task with specified delays.
        
        Args:
            task_name: Name of the task to execute
            speed: Speed value to use for all movements (default: 300)
            callback: Optional callback function to update UI
        
        Returns:
            bool: True if the task executed successfully
        """
        if not self.controller:
            print("No controller connected")
            return False
            
        task = self.get_task(task_name)
        if not task or "actions" not in task:
            return False
            
        for i, action in enumerate(task["actions"]):
            if callback:
                callback(i, len(task["actions"]))
                
            # Convert action positions into controller-friendly format
            servo_positions = []
            for servo_name, pwm in action["positions"].items():
                # Extract pin number from servo config (to be passed from main app)
                if hasattr(self.controller, "servo_config") and servo_name in self.controller.servo_config:
                    pin = self.controller.servo_config[servo_name]["pin"]
                    servo_positions.append((pin, pwm))
            
            # Execute the movement
            if servo_positions:
                success = self.controller.move_multiple_servos(
                    servo_positions, 
                    speed=speed,  # Use the provided speed parameter
                    angle=False  # Using PWM values directly
                )
                
                if not success:
                    return False
            
            # Wait for the specified delay before the next action
            if i < len(task["actions"]) - 1:  # Don't delay after the last action
                delay_ms = action.get("delay", 1000)
                time.sleep(delay_ms / 1000)  # Convert milliseconds to seconds
                
        return True
    
    def set_controller(self, controller):
        """Set the controller instance for executing tasks."""
        self.controller = controller