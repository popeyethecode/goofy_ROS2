#!/usr/bin/env bash
# Run this ON THE PI (over SSH or at its own terminal), not on the PC.
# Wipes every old ROS2 workspace/launch file this project might have left
# behind so the new build starts from a clean slate.
set -e

# If you're currently sitting inside one of the directories being wiped
# below, deleting it out from under the shell breaks getcwd() for every
# command after it (git especially - it hard-fails without a valid cwd).
cd ~

echo "Stopping anything from the old stack that might still be running..."
pkill -f "ros2 launch" 2>/dev/null || true
pkill -f "async_slam_toolbox_node" 2>/dev/null || true
pkill -f "slam_toolbox" 2>/dev/null || true
pkill -f "robot_state_publisher" 2>/dev/null || true
pkill -f "joint_state_publisher" 2>/dev/null || true
pkill -f "serial_bridge_node" 2>/dev/null || true
pkill -f "rplidar" 2>/dev/null || true
sleep 1

echo "Removing old workspace directories..."
rm -rf ~/pi5_ws ~/pc_ws ~/ros2_ws ~/robot_slam_workspace_1 ~/goofy_ws

echo "Removing old ROS2 sourcing lines from ~/.bashrc..."
sed -i '/pi5_ws\/install\/setup\.bash/d' ~/.bashrc
sed -i '/pc_ws\/install\/setup\.bash/d' ~/.bashrc
sed -i '/ros2_ws\/install\/setup\.bash/d' ~/.bashrc

echo "Done. The Pi has no ROS2 workspace left - run setup_pi.sh next."
