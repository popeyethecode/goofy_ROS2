"""
The ONLY thing that runs on the PC/VM: RViz2, as a pure viewer.

No robot_state_publisher, no xacro, no slam_toolbox, no URDF file - this
machine doesn't need any of them. It just subscribes over the network to
whatever the Pi is publishing:
    /robot_description  (Topic, transient-local - RobotModel display reads
                          the robot's shape straight from this, no local
                          URDF/xacro copy needed on the PC at all)
    /tf, /tf_static
    /scan
    /map
    /odom

Before this shows anything, the Pi must already be running:
    ros2 launch goofy_bringup bringup.launch.py

And `ros2 topic list` here on the PC must show /scan, /odom, /tf,
/tf_static, /map coming from the Pi - if it doesn't, it's a networking
problem (see the top-level README), not an RViz problem.

Run with:
    ros2 launch goofy_viz view.launch.py
"""
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    pkg_share = get_package_share_directory('goofy_viz')
    rviz_config = os.path.join(pkg_share, 'rviz', 'goofy_view.rviz')

    return LaunchDescription([
        Node(
            package='rviz2',
            executable='rviz2',
            name='rviz2',
            output='screen',
            arguments=['-d', rviz_config],
            parameters=[{'use_sim_time': False}],
        ),
    ])
