#!/usr/bin/env bash
# Run this ON THE PI, after wipe_pi.sh and after copying this whole
# goofy_rebuild/ folder onto the Pi (see the README for the scp command).
set -e

sudo apt update
sudo apt install -y \
  ros-jazzy-slam-toolbox \
  ros-jazzy-robot-state-publisher \
  ros-jazzy-xacro \
  ros-jazzy-rmw-cyclonedds-cpp \
  ros-jazzy-teleop-twist-keyboard \
  python3-serial \
  python3-colcon-common-extensions \
  build-essential git

sudo usermod -aG dialout "$USER"
echo ">> You must log out and back in (or reboot) for the dialout group"
echo ">> change to take effect, or serial ports will need sudo."

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

mkdir -p ~/ros2_ws/src
cp -r "$SRC_DIR/pi_ws/src/." ~/ros2_ws/src/

# Vendor the official RPLIDAR ROS2 driver from source (matches the
# previously confirmed-working setup rather than relying on an apt
# package that may not exist for Jazzy).
if [ ! -d ~/ros2_ws/src/rplidar_ros ]; then
  git clone -b ros2 https://github.com/Slamtec/rplidar_ros.git ~/ros2_ws/src/rplidar_ros
fi

cd ~/ros2_ws
rm -rf build install log
colcon build --symlink-install

if ! grep -q "ros2_ws/install/setup.bash" ~/.bashrc; then
  echo 'source ~/ros2_ws/install/setup.bash' >> ~/.bashrc
fi
source ~/ros2_ws/install/setup.bash

echo ""
echo "Pi workspace built at ~/ros2_ws."
echo "Next: flash the Nano firmware (README section 2) if it isn't already,"
echo "then set up networking (README section 4) before launching anything."
