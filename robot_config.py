"""
Robot configuration parameters for the inverse kinematics module.
This module defines the parameters for the robot's base and arm lengths,
and servo limits with corrected angle ranges to match real hardware behavior.

Author: Attahiru Jibril (Modified)
Date: 2025-04-20
"""

robot_params = {
    "base": 100,   # Height of the base
    "arm1": 204,   # Length of arm1 (shoulder to elbow)
    "arm2": 165    # Length of arm2 (elbow to wrist)
}


# Servo configuration parameters for the robot's joints.
servo_config = {
    "base": {
        "pin"         : 11,
        "rest"        : 1500,
        "min"         : 600,
        "max"         : 2400,
        "min_angle"   : -90,
        "max_angle"   : 90,
    },
    "shoulder": {
        "pin"         : 10,
        "rest"        : 1750,
        "min"         : 1000,
        "max"         : 1750,
        "min_angle"   : -75,
        "max_angle"   : -50,
    },
    "elbow": {
        "pin"         : 7,
        "rest"        : 800,
        "min"         : 800,
        "max"         : 1650,
        "min_angle"   : -75,
        "max_angle"   : 75,
    },
    "wrist": {
        "pin"         : 6,
        "rest"        : 600,
        "min"         : 600,       # close
        "max"         : 2400,       # open
        "min_angle"   : -90,
        "max_angle"   : 90,
    },
    "gripper": {
        "pin"         : 0,
        "rest"        : 1000,
        "min"         : 1000,       # close
        "max"         : 2100,       # open
        "min_angle"   : -90,
        "max_angle"   : 90,
    }
}
