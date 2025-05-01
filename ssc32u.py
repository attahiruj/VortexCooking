"""
SSC_32U Controller for controlling servos using SSC-32U board.
This module provides methods to connect to the SSC-32U,
send commands to move servos, and manage multiple servos simultaneously.

The critical correction is to properly handle the inverted relationship
between angles and PWM values for the shoulder and elbow servos.
"""

import serial
import time
import sys
from robot_config import servo_config


class SSC_32U:
    def __init__(self, port="COM3", baud_rate=9600, timeout=1):
        """Initialize SSC_32U controller with specified port and baud rate."""
        self.port = port
        self.baud_rate = baud_rate
        self.timeout = timeout
        self.serial = None
        self.connected = False
        self.last_command = None
        self.last_command_time = 0
        self.default_speed = 300
        self.servo_config = servo_config

        # Set default min/max PWM from the global config (used as fallback)
        self.min_pwm = 600   # default is 500, but servo makes noise at 500
        self.max_pwm = 2400  # default is 2500, but servo makes noise at 2500

    def connect(self):
        """Connect to SSC_32U."""
        try:
            self.serial = serial.Serial(
                self.port,
                self.baud_rate,
                timeout=self.timeout
            )
            time.sleep(2)  # Allow time for connection to establish
            print(f"Connected to SSC_32U on {self.port}")
            self.connected = True

            return True
        except Exception as e:
            print(f"Warning: Could not connect to SSC_32U: {e}", file=sys.stderr)
            print("Continuing without SSC_32U control...", file=sys.stderr)
            self.serial = None
            self.connected = False

            return False

    def disconnect(self):
        """Disconnect from SSC_32U."""
        if self.serial:
            self.serial.close()
            self.serial = None
            self.connected = False
            print("Disconnected from SSC_32U")

    def send_command(self, command):
        """
        Send command to SSC_32U.
        For most servo commands, no response is expected.
        """
        if not self.serial:
            return False

        try:
            # Ensure command ends with carriage return
            if not command.endswith('\r'):
                command += '\r'

            self.serial.write(command.encode())
            print(f"Sent command: {command.strip()}")
            self.last_command = command
            self.last_command_time = time.time()
            return True
        except Exception as e:
            print(f"Error sending command: {e}", file=sys.stderr)
            return False

    def move_servo(self, channel, position, speed=None, time=None):
        """
        Move a servo to a specific position.
        # <ch> P <pw> S <spd> T <time> <cr>

        Args:
            channel (int): Servo channel (0-31)
            position (int): Pulse width in microseconds (500-2500)
            speed (int, optional): Speed in microseconds per second
            time (int, optional): Time to complete move in milliseconds

        Returns:
            bool: True if command was sent successfully
        """
        if channel < 0 or channel > 31:
            print(f"Error: Channel must be between 0 and 31, got {channel}", file=sys.stderr)
            return False

        # Find servo config by channel/pin
        servo = None
        servo_name = None
        for name, config in self.servo_config.items():
            if config["pin"] == channel:
                servo = config
                servo_name = name
                break

        # Use servo-specific limits if available, otherwise use defaults
        if servo:
            min_pwm = servo["min"]
            max_pwm = servo["max"]
            print(f"Using limits for servo '{servo_name}': min={min_pwm}, max={max_pwm}")
        else:
            min_pwm = self.min_pwm
            max_pwm = self.max_pwm
            print(f"Using default servo limits: min={min_pwm}, max={max_pwm}")

        if position < min_pwm or position > max_pwm:
            print(f"Warning: Position must be between {min_pwm} & {max_pwm} ms, got {position}", file=sys.stderr)
            # Clamp the position to valid range instead of failing
            position = max(min(position, max_pwm), min_pwm)
            print(f"Clamping to {position}")

        command = f"#{channel}P{position}"

        if speed is not None:
            command += f"S{speed}"

        if time is not None:
            command += f"T{time}"

        return self.send_command(command)

    def move_multiple_servos(self, positions, speed=300, time=None, angle=False):
        """
        Move multiple servos to specific positions.
        # <ch> P <pw> S <spd> ... # <ch> P <pw> S <spd> T <time> <cr>

        Args:
            positions (list): List of tuples (channel, position)
            speed (int, optional): Speed in microseconds per second
            time (int, optional): Time to complete move in milliseconds
            angle (bool, optional): If True, position is interpreted as an angle

        Returns:
            bool: True if command was sent successfully
        """
        if len(positions) > 32:
            print(f"Error: Cannot control more than 32 servos at once, got {len(positions)}", file=sys.stderr)
            # Truncate to 32 instead of failing
            positions = positions[:32]

        command = ""
        for channel, position in positions:
            if channel < 0 or channel > 31:
                print(f"Error: Channel {channel} must be between 0 and 31", file=sys.stderr)
                continue  # Skip this channel instead of failing

            # Find servo config by channel/pin
            servo = None
            servo_name = None
            for name, config in self.servo_config.items():
                if config["pin"] == channel:
                    servo = config
                    servo_name = name
                    break

            # Use servo-specific limits if available, otherwise use defaults
            if servo:
                min_pwm = servo["min"]
                max_pwm = servo["max"]
                min_angle = servo["min_angle"]
                max_angle = servo["max_angle"]
            else:
                min_pwm = self.min_pwm
                max_pwm = self.max_pwm
                min_angle = -90
                max_angle = 90

            original_position = position  # Store original position for logging

            if angle:
                # Check if angle is within the servo's angle range
                if position < min_angle or position > max_angle:
                    print(f"Warning: Angle {position}° for channel {channel} is outside range [{min_angle}, {max_angle}]",
                        file=sys.stderr)
                    position = max(min(position, max_angle), min_angle)
                    print(f"Clamping angle to {position}°")

                # Convert angle to PWM value
                pwm_value = self.calculate_pwm_for_servo(servo_name, position)
                print(f"Channel {channel} ({servo_name if servo_name else 'unknown'}): Angle {position}° -> PWM {pwm_value}")
                position = pwm_value  # Use the calculated PWM value

            if position < min_pwm or position > max_pwm:
                print(f"Warning: Position {position} for channel {channel} must be between {min_pwm} & {max_pwm}",
                    file=sys.stderr)
                # Clamp the position to valid range instead of failing
                position = max(min(position, max_pwm), min_pwm)
                print(f"Clamping to {position}")

            # Add servo command to the command string WITH speed parameter for each servo
            command += f"#{channel}P{position}"
            
            # Apply speed to each individual servo command
            if speed is not None:
                command += f"S{speed}"
            else:
                # Default speed if not specified
                command += f"S{self.default_speed}"

        if not command:
            print("Error: No valid servo positions to command", file=sys.stderr)
            return False

        # Add time parameter only once at the end (applies to all servos)
        if time is not None:
            command += f"T{time}"

        print(f"Command to send: {command}")

        return self.send_command(command)
    def query_command(self, command, wait_for_response=True):
        """
        Send a query command and wait for response.
        Returns the response string or None if no response.
        """
        if not self.serial:
            return None

        try:
            # Ensure command ends with carriage return
            if not command.endswith('\r'):
                command += '\r'

            self.serial.write(command.encode())
            print(f"Sent query: {command.strip()}")

            if wait_for_response:
                return self.read_response()
            return None
        except Exception as e:
            print(f"Error sending query: {e}", file=sys.stderr)
            return None

    def read_response(self, timeout=1.0):
        """
        Read response from SSC_32U with timeout.
        Returns the response string or None if timeout or error.
        """
        if not self.serial:
            return None

        start_time = time.time()
        response_buffer = bytearray()

        while (time.time() - start_time) < timeout:
            if self.serial.in_waiting > 0:
                try:
                    byte_data = self.serial.read(1)
                    response_buffer.extend(byte_data)

                    # Check if we've received a complete response (usually ends with CR)
                    if byte_data == b'\r' or len(response_buffer) > 0 and time.time() - start_time > 0.1:
                        try:
                            response = response_buffer.decode('utf-8').strip()
                            print(f"SSC_32U response: {response}")
                            return response
                        except UnicodeDecodeError:
                            print("Error: Unable to decode SSC_32U response", file=sys.stderr)
                            return None
                except Exception as e:
                    print(f"Error reading from SSC_32U: {e}", file=sys.stderr)
                    return None
            time.sleep(0.01)  # Small delay to prevent CPU hogging

        if len(response_buffer) > 0:
            try:
                response = response_buffer.decode('utf-8').strip()
                print(f"SSC_32U response (timeout reached): {response}")
                return response
            except:
                pass

        print("No response from SSC_32U", file=sys.stderr)
        return None

    def query_movement_status(self):
        """
        Query if servos are still moving.

        Returns:
            str: "." if movement complete, "+" if in progress, None if error
        """
        return self.query_command("Q")

    def is_ready(self):
        """
        Check if SSC_32U is ready to receive commands.

        Returns:
            bool: True if ready, False otherwise
        """
        return self.query_movement_status() == "."

    def calculate_pwm_for_servo(self, servo_name, angle):
        """
        Calculate the proper PWM value for a given servo and angle.
        This function handles the special cases for each servo type.

        Args:
            servo_name (str): Name of the servo ('base', 'shoulder', 'elbow', 'wrist')
            angle (float): Angle in degrees

        Returns:
            int: PWM value for the servo
        """
        try:
            # Get servo configuration
            if servo_name not in self.servo_config:
                print(f"Warning: Unknown servo '{servo_name}', using default mapping", file=sys.stderr)
                return self.map_deg_to_pwm(angle)

            config = self.servo_config[servo_name]
            min_pwm = config["min"]
            max_pwm = config["max"]
            min_angle = config["min_angle"]
            max_angle = config["max_angle"]

            # Special handling for each servo type based on real-world behavior
            if servo_name == "base":
                # Base: Standard mapping where higher angle = higher PWM
                return self.map_angle_to_pwm(angle, min_angle, max_angle, min_pwm, max_pwm, False)

            elif servo_name == "shoulder":
                # Shoulder: INVERTED mapping where higher angle = lower PWM
                # This is due to the mechanical design of your specific robot
                return self.map_angle_to_pwm(angle, min_angle, max_angle, min_pwm, max_pwm, True)

            elif servo_name == "elbow":
                # Elbow: INVERTED mapping where higher angle = lower PWM
                # This is due to the mechanical design of your specific robot
                return self.map_angle_to_pwm(angle, min_angle, max_angle, min_pwm, max_pwm, True)

            elif servo_name == "wrist":
                # Wrist: Standard mapping
                return self.map_angle_to_pwm(angle, min_angle, max_angle, min_pwm, max_pwm, False)

            else:
                # Default case - standard mapping
                return self.map_angle_to_pwm(angle, min_angle, max_angle, min_pwm, max_pwm, False)

        except Exception as e:
            print(f"Error calculating PWM for servo {servo_name}: {e}", file=sys.stderr)
            if servo_name in self.servo_config:
                # Return the middle value as a safe default
                return (self.servo_config[servo_name]["min"] + self.servo_config[servo_name]["max"]) // 2
            else:
                return (self.min_pwm + self.max_pwm) // 2

    def map_deg_to_pwm(self, angle):
        """
        Legacy method for backward compatibility.
        Maps a degree angle to PWM value using the default range.

        Args:
            angle (float): Angle in degrees

        Returns:
            int: Corresponding PWM value
        """
        try:
            # Map the angle to the PWM range (600-2400)
            pwm = int((angle + 90) * (self.max_pwm - self.min_pwm) / 180 + self.min_pwm)
            return pwm
        except Exception as e:
            print(f"Error mapping angle to PWM: {e}", file=sys.stderr)
            # Return a safe middle value
            return (self.max_pwm + self.min_pwm) // 2

    def map_angle_to_pwm(self, angle, min_angle, max_angle, min_pwm, max_pwm, is_inverted=False):
        """
        Map an angle to a PWM value using the specified angle and PWM ranges.
        Improved to handle the physical constraints of the servos.

        Args:
            angle (float): Angle in degrees
            min_angle (float): Minimum angle in degrees
            max_angle (float): Maximum angle in degrees
            min_pwm (int): Minimum PWM value
            max_pwm (int): Maximum PWM value
            is_inverted (bool): If True, the mapping is inverted (higher angle = lower PWM)

        Returns:
            int: Corresponding PWM value
        """
        try:
            # Ensure angle is within the allowed range
            constrained_angle = max(min(angle, max_angle), min_angle)
            if constrained_angle != angle:
                print(f"Angle {angle:.1f}° constrained to {constrained_angle:.1f}° (range: {min_angle}° to {max_angle}°)")
                angle = constrained_angle

            # Handle special case where min_angle == max_angle
            if min_angle == max_angle:
                return min_pwm if is_inverted else max_pwm

            # Calculate the position within the angle range (0.0 to 1.0)
            angle_range = max_angle - min_angle
            position = (angle - min_angle) / angle_range

            # For inverted servos, higher angle means lower PWM
            if is_inverted:
                position = 1.0 - position

            # Map this position to the PWM range, ensuring a linear relationship
            pwm = int(min_pwm + position * (max_pwm - min_pwm))

            # Ensure the result is within range
            pwm = max(min(pwm, max_pwm), min_pwm)

            print(f"Mapped angle {angle:.1f}° to PWM {pwm} (range: {min_pwm}-{max_pwm}, inverted: {is_inverted})")
            return pwm

        except Exception as e:
            print(f"Error mapping angle to PWM: {e}", file=sys.stderr)
            # Return a safe middle value
            return (max_pwm + min_pwm) // 2