import tkinter as tk
from tkinter import ttk, messagebox
from robot_config import servo_config
from ssc32u import SSC_32U

class RobotControllerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Robot Arm Controller")
        self.root.geometry("600x700")
        self.root.resizable(False, False)

        self.controller = SSC_32U()
        self.connected = False

        self.port_var = tk.StringVar(value="COM3")
        self.baud_var = tk.IntVar(value=9600)
        self.status_var = tk.StringVar(value="Not Connected")
        self.speed_var = tk.IntVar(value=300)
        self.command_var = tk.StringVar(value="")

        self.servo_values = {}
        self.servo_sliders = {}
        self.servo_angle_labels = {}
        self.servo_pwm_labels = {}

        self.build_ui()
        for servo_name in servo_config:
            self.update_servo_display(servo_name)
        self.update_command_preview()

    def build_ui(self):
        self.build_connection_frame()
        self.build_servo_frame()
        self.build_movement_frame()
        self.build_buttons()
        self.build_command_preview()

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

    def build_movement_frame(self):
        frame = ttk.LabelFrame(self.root, text="Movement Controls")
        frame.pack(fill="x", padx=10, pady=10)

        ttk.Label(frame, text="Speed:").grid(row=0, column=0)
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
            else:
                messagebox.showerror("Connection Error", f"Could not connect to {self.port_var.get()}")
        else:
            self.controller.disconnect()
            self.connected = False
            self.status_var.set("Not Connected")
            self.status_label.config(foreground="red")
            self.connect_btn.config(text="Connect")
            self.send_btn.config(state=tk.DISABLED)

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

if __name__ == "__main__":
    root = tk.Tk()
    app = RobotControllerApp(root)
    root.mainloop()