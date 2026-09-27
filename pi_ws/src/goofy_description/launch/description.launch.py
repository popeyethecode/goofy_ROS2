"""
Publishes the robot's URDF as /robot_description and broadcasts the fixed
TF frames (base_footprint -> base_link -> lidar_link, base_link -> wheels).

Runs on the Pi, alongside every other node - the "everything on the Pi"
architecture. The PC/VM only ever runs RViz2 as a pure viewer; it never
runs robot_state_publisher itself, it just reads /robot_description and
/tf over the network.

NOTE: there is deliberately no joint_state_publisher here. The old split
architecture used one to fake zero-position wheel joints for TF; now that
goofy_motor_bridge (running on this same machine) computes real wheel
angles from encoder ticks and publishes them on /joint_states, a second
publisher of the same joints would just conflict with it.
"""
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.substitutions import Command
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    pkg_share = get_package_share_directory('goofy_description')
    xacro_file = os.path.join(pkg_share, 'urdf', 'goofy.urdf.xacro')

    # ParameterValue(..., value_type=str) forces this to be treated as a
    # raw string parameter. Without it, launch tries to YAML-parse the
    # xacro-expanded URDF text (which is not valid YAML) and fails with
    # "Unable to parse the value of parameter robot_description as yaml".
    robot_description = ParameterValue(
        Command(['xacro ', xacro_file]), value_type=str)

    return LaunchDescription([
        Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            name='robot_state_publisher',
            output='screen',
            parameters=[{'robot_description': robot_description, 'use_sim_time': False}],
        ),
    ])
