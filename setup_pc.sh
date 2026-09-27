#!/usr/bin/env bash
# Run this ON THE PC/VM, after wipe_pc.sh and after copying this whole
# goofy_rebuild/ folder onto the VM (see the README for the scp command).
set -e

# Running via `ssh host "bash script.sh"` gives a non-interactive shell,
# which does NOT source ~/.bashrc - so ROS2's own environment has to be
# sourced explicitly here, or colcon can't even find ament_cmake.
if [ -f /opt/ros/jazzy/setup.bash ]; then
  source /opt/ros/jazzy/setup.bash
else
  echo "ERROR: /opt/ros/jazzy/setup.bash not found - is ROS2 Jazzy actually installed?" >&2
  exit 1
fi

sudo apt update
sudo apt install -y \
  ros-jazzy-rviz2 \
  ros-jazzy-rmw-cyclonedds-cpp \
  ros-jazzy-teleop-twist-keyboard \
  python3-colcon-common-extensions

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

mkdir -p ~/ros2_ws/src
cp -r "$SRC_DIR/pc_ws/src/." ~/ros2_ws/src/

cd ~/ros2_ws
rm -rf build install log
colcon build --symlink-install

if ! grep -q "ros2_ws/install/setup.bash" ~/.bashrc; then
  echo 'source ~/ros2_ws/install/setup.bash' >> ~/.bashrc
fi
source ~/ros2_ws/install/setup.bash

echo ""
echo "PC/VM viz-only workspace built at ~/ros2_ws."
echo "Next: set up networking (README section 4), then:"
echo "    ros2 launch goofy_viz view.launch.py"
