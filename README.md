# goofy — full rebuild: everything on the Pi, PC/VM is viewer-only

This replaces the old split architecture (Pi = sensors only, PC = robot
model + SLAM). **The Pi now runs the entire stack.** The PC/VM's ROS2
install only ever runs RViz2, subscribed to the Pi over the network.

```
Pi (ROS2 Jazzy, Ubuntu 24.04)                    PC/VM (ROS2 Jazzy, Ubuntu 24.04)
──────────────────────────────                   ─────────────────────────────
goofy_description                                goofy_viz
  robot_state_publisher (URDF, static TF)          RViz2 only - reads
goofy_motor_bridge                    ── LAN ──▶   /robot_description, /tf,
  serial -> Arduino Nano -> TB6612FNG               /scan, /map, /odom over
  publishes /odom, /joint_states,                   the network. Nothing runs
  odom->base_footprint TF                           here except the viewer.
rplidar_ros
  publishes /scan @ lidar_link
slam_toolbox
  publishes map->odom, /map
```

TF tree (all published by the Pi now — the PC publishes nothing):
```
map              <- slam_toolbox
 └─ odom         <- goofy_motor_bridge
     └─ base_footprint
         └─ base_link   <- robot_state_publisher
             ├─ lidar_link
             ├─ left_wheel / right_wheel   (real angles, from encoder ticks)
             └─ caster_wheel
```

Contents of this folder:
- `pi_ws/src/` — everything that builds and runs on the Pi:
  `goofy_description`, `goofy_motor_bridge`, `goofy_bringup`
  (`rplidar_ros` is fetched from source during setup — see `setup_pi.sh`)
- `pc_ws/src/goofy_viz/` — the *only* thing that builds and runs on the
  PC/VM: an RViz2 launch file + config
- `firmware/tb6612_encoder_bridge/` — the Arduino Nano sketch (unchanged
  from your working copy — the wiring/protocol didn't need to change,
  only where the ROS2 side runs)
- `wipe_pi.sh` / `wipe_pc.sh` — remove every old workspace/launch file
- `setup_pi.sh` / `setup_pc.sh` — install deps, build the new workspace
- `cyclonedds.xml` — static peer list for DDS discovery across the LAN

**Once this is done, it's one command per machine:**
```bash
# Pi:
ros2 launch goofy_bringup bringup.launch.py
# PC:
ros2 launch goofy_viz view.launch.py
```

---

## What "improve it a bit" changed in the URDF

- Introduced `caster_x` / `caster_z` properties and removed a redundant
  double-offset (the caster's position used to be set partly in its own
  link origin and partly in the joint origin — same final position,
  consolidated into one place so it's actually measurable/adjustable).
- Fixed the naming inconsistency `caster_wheel` link / `castor_wheel`
  joint → both now say `caster`.
- Added `<dynamics damping=".." friction=".."/>` to the two wheel joints
  — harmless for the real robot (the motor bridge drives PWM directly,
  it never reads this), but means the model won't have silently-zero
  physical properties if you ever plug it into `ros2_control` or Gazebo.
- `base_joint`'s height is now `${wheel_radius}` instead of a repeated
  hardcoded `0.04` — one source of truth.
- Consistent quoting/indentation throughout (the original had stray
  spaces like `xyz= "0 0 0.03"` scattered around).
- Wiring note: `goofy_motor_bridge` now integrates encoder ticks into
  real per-wheel joint angles and publishes them on `/joint_states`
  (see below) — the URDF's continuous joint *names*
  (`base_left_wheel_joint`, `base_right_wheel_joint`) are what tie that
  together, and they're unchanged from your original file.

## What changed in the ROS2 side (beyond just moving packages to the Pi)

- **`joint_state_publisher` is gone.** It used to fake zero-position
  wheels just so TF for the wheel visuals would resolve. Now that
  `goofy_motor_bridge` already has the encoder ticks (it needs them for
  odometry anyway), it also publishes real wheel angles as
  `sensor_msgs/JointState` — so in RViz the wheels actually spin instead
  of sitting frozen. One less package, more accurate.
- `slam_toolbox` moved from the PC into `goofy_bringup` on the Pi.
- Package names changed from `motor_bridge` / `robot_bringup` /
  `robot_description` / `slam_bringup` to `goofy_motor_bridge` /
  `goofy_bringup` / `goofy_description` / `goofy_viz`, so there's no
  ambiguity with anything left over from the old workspaces.

---

## 0. Get this folder onto the Pi and the PC/VM

I built all of this in a cloud sandbox, not on your machines directly (a
Windows update broke my remote-shell access to "rei" as of this session —
that's also why you're running these scripts yourself rather than me
running them for you). I've placed the whole `goofy_rebuild/` folder at:

```
D:\SLAM\Goofy the rbot\goofy_rebuild\
```

Copy it to both machines. From a PowerShell/cmd window on the Windows PC
(Windows 10/11 ship an SSH client, so this should work as-is once you fill
in the real usernames):

```powershell
scp -r "D:\SLAM\Goofy the rbot\goofy_rebuild" <PI_USER>@10.19.133.93:~/goofy_rebuild
scp -r "D:\SLAM\Goofy the rbot\goofy_rebuild" <VM_USER>@10.19.133.109:~/goofy_rebuild
```

(Pi password: the one you gave me. Replace `<PI_USER>` — likely `ubuntu`
if this is a stock Ubuntu Server 24.04 image — and `<VM_USER>` with your
actual VM login.)

If `scp` from Windows gives you trouble, doing the same `scp -r` command
**from inside the VM's terminal instead** (VM → Pi, and copy the folder to
the VM itself via VMware shared folders or the VM's own network share of
`D:\SLAM\...`) works the same way — whichever machine has a working shell
is fine, it's just a file copy.

## 1. Wipe both machines

```bash
# on the Pi:
bash ~/goofy_rebuild/wipe_pi.sh
# on the PC/VM:
bash ~/goofy_rebuild/wipe_pc.sh
```

## 2. Build

```bash
# on the Pi:
bash ~/goofy_rebuild/setup_pi.sh
# on the PC/VM:
bash ~/goofy_rebuild/setup_pc.sh
```

## 3. Flash the Nano (only if you haven't already / rewired anything)

Your Nano should already be running this exact firmware — nothing about
it changed. Skip this section if `arduino-cli monitor` already shows
`READY` and responds to `M 150 150` with wheels turning. Otherwise, with
the Nano plugged into the Pi:

```bash
curl -fsSL https://raw.githubusercontent.com/arduino/arduino-cli/master/install.sh | sh
export PATH="$HOME/bin:$PATH"
echo 'export PATH="$HOME/bin:$PATH"' >> ~/.bashrc

arduino-cli core update-index
arduino-cli core install arduino:avr
arduino-cli board list   # confirm the port, usually /dev/ttyUSB0

arduino-cli compile --fqbn arduino:avr:nano ~/goofy_rebuild/firmware/tb6612_encoder_bridge
arduino-cli upload -p /dev/ttyUSB0 --fqbn arduino:avr:nano ~/goofy_rebuild/firmware/tb6612_encoder_bridge
```

## 4. Networking — do this on BOTH machines

Same three lines in both machines' `~/.bashrc`:

```bash
export ROS_DOMAIN_ID=42
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export CYCLONEDDS_URI=file://$HOME/cyclonedds.xml
```

Copy `cyclonedds.xml` from this folder to `~/cyclonedds.xml` **on both
machines** — it already has your two current IPs (`10.19.133.93` Pi,
`10.19.133.109` PC/VM). If either machine's IP changes later (new
network, DHCP renewal), update both copies.

If the PC is the VMware VM: set its network adapter to **Bridged** (VM
settings → Network Adapter → Bridged), not NAT, so it gets a real LAN IP
in the Pi's subnet instead of hiding behind NAT — DDS discovery generally
won't cross a NAT boundary.

**Clock sync** — both machines' clocks need to agree within ~0.1s or
slam_toolbox will silently never produce a map (no error, just nothing).
Check with `timedatectl status` on both (want "System clock
synchronized: yes"); if not, `sudo apt install -y systemd-timesyncd &&
sudo timedatectl set-ntp true`. VMs drift after suspend/resume especially.

**Verify discovery before starting the robot stack at all:**
```bash
# Pi:
ros2 topic pub /test std_msgs/String "data: hi"
# PC:
ros2 topic list
```
If `/test` doesn't show up on the PC, stop here and fix networking —
nothing above the transport layer is worth debugging yet.

## 5. Run it

```bash
# Pi:
ros2 launch goofy_bringup bringup.launch.py
# PC:
ros2 launch goofy_viz view.launch.py
```
If the motor MCU or lidar aren't on their default ports:
```bash
ros2 launch goofy_bringup bringup.launch.py \
  motor_serial_port:=/dev/ttyUSB1 lidar_serial_port:=/dev/ttyUSB0
```
(Two USB-serial devices can swap `/dev/ttyUSB0`/`ttyUSB1` across reboots —
add a udev rule keyed on `idVendor`/`idProduct`/serial if this bites you
repeatedly; ask me and I'll write the exact rule.)

Drive it, from the PC:
```bash
ros2 run teleop_twist_keyboard teleop_twist_keyboard
```

Save the finished map (run on whichever machine has `nav2-map-server`
installed — install with `sudo apt install ros-jazzy-nav2-map-server` if
needed):
```bash
ros2 run nav2_map_server map_saver_cli -f ~/my_map
```

## 6. If RViz shows nothing — check top-down

1. `ros2 topic list` on the PC shows `/scan /odom /tf /tf_static /map`
   from the Pi. If not → step 4 (networking).
2. `ros2 topic hz /scan` on the PC shows ~7–8 Hz. If topics list but
   nothing publishes → check the Pi's console for the rplidar node;
   wrong `lidar_serial_port` is the usual cause.
3. `ros2 run tf2_ros tf2_echo odom base_footprint` streams values → the
   Pi's odometry is alive. If not, `goofy_motor_bridge` isn't getting
   `E ...` lines from the Nano (check the serial port / wiring).
4. `ros2 run tf2_ros tf2_echo map odom` resolves → slam_toolbox is
   mapping. If 1–3 pass but this doesn't, read slam_toolbox's own
   console output, and re-check clock sync (step 4) — that produces
   exactly this symptom with zero error messages anywhere.
5. RViz's **Global Status** panel — a red entry names the exact problem
   (missing frame, missing topic, QoS mismatch) instead of a blank view
   with no explanation.
6. **Map display QoS must stay Transient Local** and **Fixed Frame must
   be `map`** — both already set correctly in `goofy_view.rviz`, but
   worth knowing if you ever rebuild the RViz config from scratch.

---

## If something in setup_pi.sh / setup_pc.sh fails

Paste me the exact error output and I'll fix the script — I built this
without being able to run it against your actual hardware this session
(remote access to your PC is temporarily broken on Anthropic's side after
a recent Windows update), so anything hardware- or network-specific
(exact serial port, exact package name for your Jazzy sync date, etc.)
may need one round of back-and-forth.
