import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from robot_config import servo_config, hand_config
from ssc32u import SSC_32U
from task_manager import TaskManager
import threading


class RobotControllerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Robot Arm Controller")
        self.root.geometry("800x800")  # Increased height to accommodate hand controls
        self.root.resizable(False, False)

        self.controller = SSC_32U()
        # Pass config to the controller for the task manager to use
        self.controller.servo_config = servo_config
        self.controller.hand_config = hand_config
        self.connected = False

        self.port_var = tk.StringVar(value="COM3")
        self.baud_var = tk.IntVar(value=9600)
        self.status_var = tk.StringVar(value="Not Connected")
        self.speed_var = tk.IntVar(value=300)
        self.command_var = tk.StringVar(value="")
        self.task_status_var = tk.StringVar(value="")

        self.servo_values = {}
        self.servo_sliders = {}
        self.servo_angle_labels = {}
        self.servo_pwm_labels = {}

        # Hand state variables
        self.finger_states = {}
        self.finger_buttons = {}
        for finger in hand_config:
            self.finger_states[finger] = False  # False = closed, True = open

        # Initialize task manager
        self.task_manager = TaskManager(self.controller)
        self.current_task_actions = []
        self.selected_task_var = tk.StringVar()

        # Task execution thread reference
        self.task_thread = None

        self.build_ui()
        for servo_name in servo_config:
            self.update_servo_display(servo_name)
        self.update_command_preview()
        self.update_task_list()

    def build_ui(self):
        self.build_connection_frame()
        self.build_servo_frame()
        self.build_hand_frame()  # New hand control frame
        self.build_movement_frame()
        self.build_buttons()
        self.build_command_preview()
        self.build_task_frame()

    def build_connection_frame(self):
        self.connection_frame = ttk.LabelFrame(self.root, text="Connection")
        self.connection_frame.pack(fill="x", padx=10, pady=10)

        ttk.Label(self.connection_frame, text="COM Port:").grid(row=0, column=0, padx=5, pady=5)
        ttk.Entry(self.connection_frame, textvariable=self.port_var, width=10).grid(row=0, column=1)

        ttk.Label(self.connection_frame, text="Baud Rate:").grid(row=0, column=2)
        ttk.Combobox(self.connection_frame, textvariable=self.baud_var, values=[9600, 115200], width=8).grid(row=0, column=3)

        self.connect_btn = ttk.Button(self.connection_frame, text="Connect", command=self.toggle_connection)
        self.connect_btn.grid(row=0, column=4, padx=10)

        self.status_label = ttk.Label(self.connection_frame, textvariable=self.status_var, foreground="red")
        self.status_label.grid(row=0, column=5)

    def build_servo_frame(self):
        frame = ttk.LabelFrame(self.root, text="Servo Controls")
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        for i, (name, config) in enumerate(servo_config.items()):
            ttk.Label(frame, text=f"{name.capitalize()}:").grid(row=i, column=0, sticky="w")
            var = tk.IntVar(value=0)
            self.servo_values[name] = var

            slider = ttk.Scale(
                frame, from_=config["min_angle"], to=config["max_angle"], length=300, variable=var,
                command=lambda val, n=name: self.update_servo_display(n)
            )
            slider.grid(row=i, column=1)
            self.servo_sliders[name] = slider

            angle_var = tk.StringVar(value="0°")
            self.servo_angle_labels[name] = angle_var
            ttk.Label(frame, textvariable=angle_var, width=6).grid(row=i, column=2)

            pwm_var = tk.StringVar(value=str(config["rest"]))
            self.servo_pwm_labels[name] = pwm_var
            ttk.Label(frame, textvariable=pwm_var, width=8).grid(row=i, column=3)

    def build_hand_frame(self):
        """Build the hand control frame with buttons for each finger."""
        frame = ttk.LabelFrame(self.root, text="Hand Controls")
        frame.pack(fill="x", padx=10, pady=10)

        # Create a row of buttons for each finger
        button_frame = ttk.Frame(frame)
        button_frame.pack(pady=10)

        # Add a label to explain the controls
        ttk.Label(button_frame, text="Finger Controls:").grid(row=0, column=0, padx=5, pady=5)

        # Create buttons for each finger
        for i, finger in enumerate(hand_config.keys()):
            # Create a toggle button for each finger
            self.finger_buttons[finger] = ttk.Button(
                button_frame,
                text=f"{finger.capitalize()}: Closed",
                command=lambda f=finger: self.toggle_finger(f)
            )
            self.finger_buttons[finger].grid(row=0, column=i+1, padx=10)

        # Add all fingers control
        ttk.Button(
            button_frame,
            text="Open All",
            command=self.open_all_fingers
        ).grid(row=1, column=1, padx=10, pady=10)

        ttk.Button(
            button_frame,
            text="Close All",
            command=self.close_all_fingers
        ).grid(row=1, column=2, padx=10, pady=10)

        # Add to task button
        ttk.Button(
            button_frame,
            text="Add Hand Position to Task",
            command=self.add_hand_position_to_task
        ).grid(row=1, column=3, padx=10, pady=10)

    def build_movement_frame(self):
        frame = ttk.LabelFrame(self.root, text="Movement Controls")
        frame.pack(fill="x", padx=10, pady=10)

        ttk.Label(frame, text="Speed (applies to all movements):").grid(row=0, column=0)
        ttk.Scale(frame, from_=100, to=1000, orient="horizontal", length=300, variable=self.speed_var).grid(row=0, column=1)
        ttk.Label(frame, textvariable=self.speed_var, width=6).grid(row=0, column=2)

    def build_buttons(self):
        frame = ttk.Frame(self.root)
        frame.pack(fill="x", padx=10, pady=10)

        self.send_btn = ttk.Button(frame, text="Send to Robot", command=self.send_command, state=tk.DISABLED)
        self.send_btn.pack(side="left", padx=10)
        ttk.Button(frame, text="Reset to Zero", command=self.reset_position).pack(side="left", padx=10)
        ttk.Button(frame, text="Home Position", command=self.home_position).pack(side="left", padx=10)

    def build_command_preview(self):
        frame = ttk.LabelFrame(self.root, text="Command")
        frame.pack(fill="x", padx=10, pady=10)
        ttk.Entry(frame, textvariable=self.command_var, width=60, state="readonly").pack(padx=10, pady=10, fill="x")

    def build_task_frame(self):
        frame = ttk.LabelFrame(self.root, text="Task Management")
        frame.pack(fill="both", padx=10, pady=10)

        # Top section - Task list and controls
        top_frame = ttk.Frame(frame)
        top_frame.pack(fill="x", padx=5, pady=5)

        # Task selection combo box
        ttk.Label(top_frame, text="Task:").grid(row=0, column=0, padx=5, pady=5)
        self.task_combo = ttk.Combobox(top_frame, textvariable=self.selected_task_var, state="readonly", width=20)
        self.task_combo.grid(row=0, column=1, padx=5, pady=5)
        self.task_combo.bind("<<ComboboxSelected>>", self.on_task_selected)

        # Task buttons
        buttons_frame = ttk.Frame(top_frame)
        buttons_frame.grid(row=0, column=2, padx=5, pady=5)

        self.run_task_btn = ttk.Button(buttons_frame, text="Run Task", command=self.run_task, state=tk.DISABLED)
        self.run_task_btn.pack(side="left", padx=2)

        # Add Stop Task button
        self.stop_task_btn = ttk.Button(buttons_frame, text="Stop Task", command=self.stop_task, state=tk.DISABLED)
        self.stop_task_btn.pack(side="left", padx=2)

        ttk.Button(buttons_frame, text="New Task", command=self.new_task).pack(side="left", padx=2)
        self.delete_task_btn = ttk.Button(buttons_frame, text="Delete Task", command=self.delete_task, state=tk.DISABLED)
        self.delete_task_btn.pack(side="left", padx=2)

        # Task status
        ttk.Label(top_frame, textvariable=self.task_status_var).grid(row=0, column=3, padx=10)

        # Middle section - Action buttons
        middle_frame = ttk.Frame(frame)
        middle_frame.pack(fill="x", padx=5, pady=5)

        ttk.Button(middle_frame, text="Add Current Position", command=self.add_position).pack(side="left", padx=5)
        ttk.Label(middle_frame, text="Delay (ms):").pack(side="left", padx=5)
        self.delay_var = tk.IntVar(value=1000)
        ttk.Entry(middle_frame, textvariable=self.delay_var, width=6).pack(side="left")
        ttk.Button(middle_frame, text="Save Task", command=self.save_task).pack(side="left", padx=5)

        # Bottom section - Actions list
        bottom_frame = ttk.Frame(frame)
        bottom_frame.pack(fill="both", expand=True, padx=5, pady=5)

        # Scrollable treeview for actions
        columns = ('index', 'positions', 'delay')
        self.actions_tree = ttk.Treeview(bottom_frame, columns=columns, show='headings', height=5)
        self.actions_tree.heading('index', text='#')
        self.actions_tree.heading('positions', text='Positions')
        self.actions_tree.heading('delay', text='Delay (ms)')

        self.actions_tree.column('index', width=30, anchor='center')
        self.actions_tree.column('positions', width=500)
        self.actions_tree.column('delay', width=80, anchor='center')

        self.actions_tree.pack(side="left", fill="both", expand=True)

        # Scrollbar for treeview
        scrollbar = ttk.Scrollbar(bottom_frame, orient="vertical", command=self.actions_tree.yview)
        scrollbar.pack(side="right", fill="y")
        self.actions_tree.configure(yscrollcommand=scrollbar.set)

        # Right-click menu for actions
        self.action_menu = tk.Menu(self.root, tearoff=0)
        self.action_menu.add_command(label="Delete", command=self.delete_action)
        self.action_menu.add_command(label="Move Up", command=lambda: self.move_action(-1))
        self.action_menu.add_command(label="Move Down", command=lambda: self.move_action(1))

        self.actions_tree.bind("<Button-3>", self.show_action_menu)

    # Hand control methods
    def toggle_finger(self, finger):
        """Toggle a finger's state between open and closed."""
        if not self.connected:
            messagebox.showerror("Error", "Not connected to robot")
            return

        # Toggle the state
        self.finger_states[finger] = not self.finger_states[finger]

        # Update button text
        state_text = "Open" if self.finger_states[finger] else "Closed"
        self.finger_buttons[finger].config(text=f"{finger.capitalize()}: {state_text}")

        # Send command to the servo
        config = hand_config[finger]
        pwm = config["open"] if self.finger_states[finger] else config["close"]

        success = self.controller.move_servo(config["pin"], pwm, speed=self.speed_var.get())
        if not success:
            messagebox.showerror("Error", f"Failed to move {finger} finger")
            # Revert state if failed
            self.finger_states[finger] = not self.finger_states[finger]
            state_text = "Open" if self.finger_states[finger] else "Closed"
            self.finger_buttons[finger].config(text=f"{finger.capitalize()}: {state_text}")

    def open_all_fingers(self):
        """Open all fingers."""
        if not self.connected:
            messagebox.showerror("Error", "Not connected to robot")
            return

        commands = []
        for finger, config in hand_config.items():
            self.finger_states[finger] = True
            self.finger_buttons[finger].config(text=f"{finger.capitalize()}: Open")
            commands.append((config["pin"], config["open"]))

        success = self.controller.move_multiple_servos(commands, speed=self.speed_var.get())
        if not success:
            messagebox.showerror("Error", "Failed to open all fingers")
            # Don't attempt to revert state, as it would be complicated to determine which ones failed

    def close_all_fingers(self):
        """Close all fingers."""
        if not self.connected:
            messagebox.showerror("Error", "Not connected to robot")
            return

        commands = []
        for finger, config in hand_config.items():
            self.finger_states[finger] = False
            self.finger_buttons[finger].config(text=f"{finger.capitalize()}: Closed")
            commands.append((config["pin"], config["close"]))

        success = self.controller.move_multiple_servos(commands, speed=self.speed_var.get())
        if not success:
            messagebox.showerror("Error", "Failed to close all fingers")

    def add_hand_position_to_task(self):
        """Add current hand position as a new action."""
        positions = {}
        for finger, is_open in self.finger_states.items():
            config = hand_config[finger]
            pwm = config["open"] if is_open else config["close"]
            positions[f"hand_{finger}"] = pwm

        # Check if there are any positions to add
        if not positions:
            messagebox.showinfo("Info", "No hand positions to add")
            return

        action = {
            "positions": positions,
            "delay": self.delay_var.get()
        }
        self.current_task_actions.append(action)
        self.update_actions_display()

    def toggle_connection(self):
        if not self.connected:
            self.controller.port = self.port_var.get()
            self.controller.baud_rate = self.baud_var.get()
            if self.controller.connect():
                self.connected = True
                self.status_var.set("Connected")
                self.status_label.config(foreground="green")
                self.connect_btn.config(text="Disconnect")
                self.send_btn.config(state=tk.NORMAL)
                self.run_task_btn.config(state=tk.NORMAL if self.selected_task_var.get() else tk.DISABLED)
                # Update task manager with controller
                self.task_manager.set_controller(self.controller)
            else:
                messagebox.showerror("Connection Error", f"Could not connect to {self.port_var.get()}")
        else:
            self.controller.disconnect()
            self.connected = False
            self.status_var.set("Not Connected")
            self.status_label.config(foreground="red")
            self.connect_btn.config(text="Connect")
            self.send_btn.config(state=tk.DISABLED)
            self.run_task_btn.config(state=tk.DISABLED)
            self.stop_task_btn.config(state=tk.DISABLED)

    def update_servo_display(self, name):
        angle = self.servo_values[name].get()
        self.servo_angle_labels[name].set(f"{angle}°")
        pwm = self.controller.calculate_pwm_for_servo(name, angle)
        self.servo_pwm_labels[name].set(f"{pwm} μs")
        self.update_command_preview()

    def update_command_preview(self):
        command = "".join(
            f"#{servo_config[n]['pin']}P{self.controller.calculate_pwm_for_servo(n, v.get())}"
            for n, v in self.servo_values.items()
        ) + f"S{self.speed_var.get()}"
        self.command_var.set(command)

    def send_command(self):
        if not self.connected:
            messagebox.showerror("Error", "Not connected to robot")
            return
        positions = [(servo_config[n]["pin"], v.get()) for n, v in self.servo_values.items()]
        success = self.controller.move_multiple_servos(positions, speed=self.speed_var.get(), angle=True)
        if success:
            print("Command sent successfully")
        else:
            messagebox.showerror("Error", "Failed to send command")

    def reset_position(self):
        for name in self.servo_values:
            self.servo_values[name].set(0)
            self.update_servo_display(name)

    def home_position(self):
        for name, slider in self.servo_sliders.items():
            config = servo_config[name]
            pwm = config["rest"]
            pos = (pwm - config["min"]) / (config["max"] - config["min"])
            if name in ["shoulder", "elbow"]:
                pos = 1.0 - pos
            angle = round(config["min_angle"] + pos * (config["max_angle"] - config["min_angle"]))
            slider.set(angle)
            self.update_servo_display(name)

    # Task Management Methods
    def update_task_list(self):
        """Update the task dropdown with available tasks."""
        task_names = self.task_manager.get_task_names()
        self.task_combo['values'] = task_names

        # Enable/disable run and delete buttons based on selection
        has_selection = bool(self.selected_task_var.get() in task_names)
        self.delete_task_btn['state'] = tk.NORMAL if has_selection else tk.DISABLED
        self.run_task_btn['state'] = tk.NORMAL if has_selection and self.connected else tk.DISABLED

        # Update Stop button state based on task running status
        self.update_stop_button_state()

    def update_stop_button_state(self):
        """Update the state of the stop button based on whether a task is running."""
        if self.task_manager.is_task_running() and self.connected:
            self.stop_task_btn.config(state=tk.NORMAL)
        else:
            self.stop_task_btn.config(state=tk.DISABLED)

    def update_actions_display(self):
        """Update the actions treeview with current actions."""
        # Clear current items
        for item in self.actions_tree.get_children():
            self.actions_tree.delete(item)

        # Add actions
        for i, action in enumerate(self.current_task_actions):
            # Display both PWM and approximate angle for better readability
            position_details = []
            for name, pwm in action["positions"].items():
                # Check if it's a hand position
                if name.startswith("hand_"):
                    finger = name.split("_")[1]
                    if finger in hand_config:
                        config = hand_config[finger]
                        state = "Open" if pwm == config["open"] else "Closed"
                        position_details.append(f"{finger}: {state} ({pwm}μs)")
                # Or a servo position
                elif name in servo_config:
                    config = servo_config[name]
                    # Approximate angle from PWM (reverse of calculate_pwm_for_servo)
                    percent = (pwm - config["min"]) / (config["max"] - config["min"])
                    if name in ["shoulder", "elbow"]:  # Account for reversed servos
                        percent = 1.0 - percent
                    approx_angle = round(config["min_angle"] + percent * (config["max_angle"] - config["min_angle"]))
                    position_details.append(f"{name}: {pwm}μs (~{approx_angle}°)")
                else:
                    position_details.append(f"{name}: {pwm}μs")

            positions_str = ", ".join(position_details)
            self.actions_tree.insert('', 'end', values=(i+1, positions_str, action["delay"]))

    def add_position(self):
        """Add current servo positions as a new action (using PWM values)."""
        positions = {}
        for name, var in self.servo_values.items():
            # Store PWM value instead of angle
            angle = var.get()
            pwm = self.controller.calculate_pwm_for_servo(name, angle)
            positions[name] = pwm

        action = {
            "positions": positions,
            "delay": self.delay_var.get()
            # Speed removed from individual actions
        }
        self.current_task_actions.append(action)
        self.update_actions_display()

    def new_task(self):
        """Create a new task."""
        task_name = simpledialog.askstring("New Task", "Enter task name:")
        if task_name:
            self.selected_task_var.set(task_name)
            self.current_task_actions = []
            self.update_actions_display()
            self.update_task_list()

    def save_task(self):
        """Save the current task."""
        task_name = self.selected_task_var.get()
        if not task_name:
            messagebox.showerror("Error", "No task selected")
            return

        if not self.current_task_actions:
            messagebox.showerror("Error", "No actions to save")
            return

        success = self.task_manager.save_task(task_name, self.current_task_actions)
        if success:
            messagebox.showinfo("Success", f"Task '{task_name}' saved successfully")
            self.update_task_list()
        else:
            messagebox.showerror("Error", "Failed to save task")

    def delete_task(self):
        """Delete the selected task."""
        task_name = self.selected_task_var.get()
        if not task_name:
            return

        if messagebox.askyesno("Confirm Delete", f"Delete task '{task_name}'?"):
            success = self.task_manager.delete_task(task_name)
            if success:
                self.selected_task_var.set("")
                self.current_task_actions = []
                self.update_actions_display()
                self.update_task_list()

    def on_task_selected(self, event):
        """Handle task selection change."""
        task_name = self.selected_task_var.get()
        if task_name:
            task = self.task_manager.get_task(task_name)
            self.current_task_actions = task.get("actions", [])
            self.update_actions_display()
            self.update_task_list()

    def run_task(self):
        """Run the selected task."""
        if not self.connected:
            messagebox.showerror("Error", "Not connected to robot")
            return

        task_name = self.selected_task_var.get()
        if not task_name:
            return

        # Disable Run button and enable Stop button
        self.run_task_btn.config(state=tk.DISABLED)
        self.stop_task_btn.config(state=tk.NORMAL)

        # Create a thread to run the task to avoid freezing UI
        def run_task_thread():
            self.task_status_var.set("Running task...")
            # Pass the current speed setting to the task execution
            speed = self.speed_var.get()
            success = self.task_manager.execute_task(task_name, speed=speed, callback=self.update_task_progress)

            # Update UI when task completes (either successfully or due to stopping)
            status = "Task completed" if success else "Task stopped" if self.task_manager.stop_flag.is_set() else "Task failed"
            self.task_status_var.set(status)

            # Reset button states
            self.root.after(0, self.update_stop_button_state)
            self.root.after(0, lambda: self.run_task_btn.config(state=tk.NORMAL if self.connected else tk.DISABLED))

            # Clear status after a delay
            self.root.after(3000, lambda: self.task_status_var.set(""))

        self.task_thread = threading.Thread(target=run_task_thread)
        self.task_thread.daemon = True  # Make thread exit when main program exits
        self.task_thread.start()

    def stop_task(self):
        """Stop the currently running task."""
        if self.task_manager.is_task_running():
            self.task_status_var.set("Stopping task...")
            self.task_manager.stop_running_task()
            # Button states will be updated when the task thread exits

    def update_task_progress(self, current_action, total_actions):
        """Update task progress in UI."""
        self.task_status_var.set(f"Running action {current_action + 1}/{total_actions}")

    def show_action_menu(self, event):
        """Show context menu for actions."""
        item = self.actions_tree.identify_row(event.y)
        if item:
            self.actions_tree.selection_set(item)
            self.action_menu.post(event.x_root, event.y_root)

    def delete_action(self):
        """Delete the selected action."""
        selected = self.actions_tree.selection()
        if selected:
            index = int(self.actions_tree.item(selected[0])['values'][0]) - 1
            if 0 <= index < len(self.current_task_actions):
                del self.current_task_actions[index]
                self.update_actions_display()

    def move_action(self, direction):
        """Move an action up or down in the list."""
        selected = self.actions_tree.selection()
        if not selected:
            return

        index = int(self.actions_tree.item(selected[0])['values'][0]) - 1
        new_index = index + direction

        if 0 <= new_index < len(self.current_task_actions):
            self.current_task_actions[index], self.current_task_actions[new_index] = \
                self.current_task_actions[new_index], self.current_task_actions[index]
            self.update_actions_display()
            # Select the moved item
            for item in self.actions_tree.get_children():
                if int(self.actions_tree.item(item)['values'][0]) == new_index + 1:
                    self.actions_tree.selection_set(item)
                    break

if __name__ == "__main__":
    root = tk.Tk()
    app = RobotControllerApp(root)
    root.mainloop()
