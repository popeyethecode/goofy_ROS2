"""
The ONE launch file for the whole robot - everything runs on the Pi:
  - goofy_description  (robot_state_publisher, from the URDF)
  - goofy_motor_bridge  (serial link to the Arduino Nano -> /odom, /joint_states)
  - rplidar_ros         (RPLIDAR A1 driver -> /scan)
  - slam_toolbox        (online async mapping -> /map, map->odom TF)

The PC/VM runs nothing from this repo except RViz2 as a pure viewer -
see pc_ws/src/goofy_viz. It reads /robot_description, /tf, /scan and /map
over the network; it never publishes any of them itself.    ros2 launch goofy_bringup bringup.launch.py
"""
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    motor_serial_port_arg = DeclareLaunchArgument(
        'motor_serial_port', default_value='/dev/motor_mcu',
        description='Serial port for the Arduino Nano / TB6612FNG motor MCU '
                    '(stable udev symlink - see README)')
    lidar_serial_port_arg = DeclareLaunchArgument(
        'lidar_serial_port', default_value='/dev/rplidar',
        description='Serial port for the RPLIDAR A1 '
                    '(stable udev symlink - see README)')
    enable_slam_arg = DeclareLaunchArgument(
        'enable_slam', default_value='true',
        description='Run slam_toolbox. Set false to just stream /scan and /odom.')

    description_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(
                get_package_share_directory('goofy_description'),
                'launch', 'description.launch.py')),
    )

    motor_bridge_params = os.path.join(
        get_package_share_directory('goofy_motor_bridge'),
        'config', 'motor_bridge_params.yaml')

    motor_bridge_node = Node(
        package='goofy_motor_bridge',
        executable='serial_bridge_node',
        name='serial_bridge_node',
        output='screen',
        parameters=[
            motor_bridge_params,
            {'serial_port': LaunchConfiguration('motor_serial_port')},
        ],
    )
    rplidar_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(
                get_package_share_directory('rplidar_ros'),
                'launch', 'rplidar_a1_launch.py')),
        launch_arguments={
            'serial_port': LaunchConfiguration('lidar_serial_port'),
            'frame_id': 'lidar_link',
            'angle_compensate': 'true',
        }.items(),
    )

    # ---- SLAM (map->odom TF, /map) - now runs on the Pi, not the PC ----
    slam_params_file = os.path.join(
        get_package_share_directory('goofy_bringup'),
        'config', 'slam_toolbox_params.yaml')

    slam_toolbox_node = Node(
        package='slam_toolbox',
        executable='async_slam_toolbox_node',
        name='slam_toolbox',
        output='screen',
        parameters=[slam_params_file, {'use_sim_time': False}],
        condition=IfCondition(LaunchConfiguration('enable_slam')),
    )

    # slam_toolbox is a lifecycle node - it stays in the "unconfigured" state
    # (no params loaded, no /scan subscription, no /map or map->odom TF)
    # until something drives it through configure -> activate. This manager
    # does that automatically on every launch so you never have to run
    # `ros2 lifecycle set /slam_toolbox configure/activate` by hand.
    slam_lifecycle_manager = Node(
        package='nav2_lifecycle_manager',
        executable='lifecycle_manager',
        name='lifecycle_manager_slam',
        output='screen',
        parameters=[{
            'use_sim_time': False,
            'autostart': True,
            'node_names': ['slam_toolbox'],
        }],
        condition=IfCondition(LaunchConfiguration('enable_slam')),
    )

    return LaunchDescription([
        motor_serial_port_arg,
        lidar_serial_port_arg,
        enable_slam_arg,
        description_launch,
        motor_bridge_node,
        rplidar_launch,
        slam_toolbox_node,
        slam_lifecycle_manager,
    ])
