#!/usr/bin/env python3

import math
import time

import rclpy
from rclpy.node import Node

import serial

from geometry_msgs.msg import Quaternion, TransformStamped, Twist
from nav_msgs.msg import Odometry
from sensor_msgs.msg import JointState
from tf2_ros import TransformBroadcaster


def yaw_to_quaternion(yaw: float) -> Quaternion:
    q = Quaternion()
    q.z = math.sin(yaw / 2.0)
    q.w = math.cos(yaw / 2.0)
    return q


class SerialBridgeNode(Node):

    def __init__(self):
        super().__init__('serial_bridge_node')

        self.declare_parameter('serial_port', '/dev/ttyUSB0')
        self.declare_parameter('baud_rate', 115200)
        self.declare_parameter('wheel_radius', 0.04)
        self.declare_parameter('wheel_separation', 0.17)
        self.declare_parameter('ticks_per_revolution', 700)
        self.declare_parameter('max_linear_speed', 0.25)
        self.declare_parameter('min_pwm_to_move', 40)
        self.declare_parameter('cmd_vel_timeout', 0.5)
        self.declare_parameter('odom_frame_id', 'odom')
        self.declare_parameter('base_frame_id', 'base_footprint')
        self.declare_parameter('left_wheel_joint', 'base_left_wheel_joint')
        self.declare_parameter('right_wheel_joint', 'base_right_wheel_joint')
        self.declare_parameter('publish_tf', True)
        self.declare_parameter('loop_rate_hz', 50.0)

        self.wheel_radius = self.get_parameter('wheel_radius').value
        self.wheel_separation = self.get_parameter('wheel_separation').value
        self.ticks_per_rev = self.get_parameter('ticks_per_revolution').value
        self.max_linear_speed = self.get_parameter('max_linear_speed').value
        self.min_pwm_to_move = self.get_parameter('min_pwm_to_move').value
        self.cmd_vel_timeout = self.get_parameter('cmd_vel_timeout').value
        self.odom_frame_id = self.get_parameter('odom_frame_id').value
        self.base_frame_id = self.get_parameter('base_frame_id').value
        self.left_wheel_joint = self.get_parameter('left_wheel_joint').value
        self.right_wheel_joint = self.get_parameter('right_wheel_joint').value
        self.publish_tf = self.get_parameter('publish_tf').value
        loop_rate_hz = self.get_parameter('loop_rate_hz').value

        self.meters_per_tick = (2.0 * math.pi * self.wheel_radius) / float(self.ticks_per_rev)
        self.radians_per_tick = (2.0 * math.pi) / float(self.ticks_per_rev)

        port = self.get_parameter('serial_port').value
        baud = self.get_parameter('baud_rate').value
        try:
            self.ser = serial.Serial(port, baud, timeout=0)
        except serial.SerialException as exc:
            self.get_logger().error(
                f"Could not open serial port '{port}' @ {baud}: {exc}. "
                "Check `ls /dev/tty*`, that the board is plugged in, and "
                "that your user is in the 'dialout' group (then log out/in)."
            )
            raise

        self.get_logger().info('Waiting for the microcontroller to finish (re)booting...')
        time.sleep(2.0)
        self.ser.reset_input_buffer()
        self.get_logger().info('Microcontroller ready, starting control loop.')

        self._rx_buf = b''

        # Odometry state
        self.x = 0.0
        self.y = 0.0
        self.theta = 0.0
        self.v = 0.0
        self.w = 0.0

        # Wheel joint state (radians, continuous - never wrapped)
        self.left_wheel_angle = 0.0
        self.right_wheel_angle = 0.0
        self.left_wheel_velocity = 0.0
        self.right_wheel_velocity = 0.0

        self.last_cmd_vel = Twist()
        self.last_cmd_vel_time = self.get_clock().now()

        self.odom_pub = self.create_publisher(Odometry, 'odom', 10)
        self.joint_state_pub = self.create_publisher(JointState, 'joint_states', 10)
        self.tf_broadcaster = TransformBroadcaster(self)

        self.cmd_vel_sub = self.create_subscription(
            Twist, 'cmd_vel', self._cmd_vel_cb, 10)

        self.timer = self.create_timer(1.0 / loop_rate_hz, self._tick)

        self.get_logger().info(
            f"serial_bridge_node up on {port} @ {baud}, "
            f"wheel_radius={self.wheel_radius} wheel_separation={self.wheel_separation} "
            f"ticks_per_rev={self.ticks_per_rev}"
        )

    def _cmd_vel_cb(self, msg: Twist):
        self.last_cmd_vel = msg
        self.last_cmd_vel_time = self.get_clock().now()

    def _speed_to_pwm(self, speed_mps: float) -> int:
        if self.max_linear_speed <= 0.0:
            return 0
        pwm = int(round((speed_mps / self.max_linear_speed) * 255.0))
        pwm = max(-255, min(255, pwm))
        if 0 < abs(pwm) < self.min_pwm_to_move:
            pwm = self.min_pwm_to_move if pwm > 0 else -self.min_pwm_to_move
        return pwm

    def _send_motor_command(self):
        now = self.get_clock().now()
        age = (now - self.last_cmd_vel_time).nanoseconds / 1e9
        if age > self.cmd_vel_timeout:
            v_left = 0.0
            v_right = 0.0
        else:
            v = self.last_cmd_vel.linear.x
            w = self.last_cmd_vel.angular.z
            v_left = v - (w * self.wheel_separation / 2.0)
            v_right = v + (w * self.wheel_separation / 2.0)

        pwm_left = self._speed_to_pwm(v_left)
        pwm_right = self._speed_to_pwm(v_right)

        try:
            self.ser.write(f"M {pwm_left} {pwm_right}\n".encode('ascii'))
        except serial.SerialException as exc:
            self.get_logger().warning(f'Serial write failed: {exc}')

    def _read_serial(self):
        try:
            n = self.ser.in_waiting
            if n:
                self._rx_buf += self.ser.read(n)
        except serial.SerialException as exc:
            self.get_logger().warning(f'Serial read failed: {exc}')
            return

        while b'\n' in self._rx_buf:
            line, self._rx_buf = self._rx_buf.split(b'\n', 1)
            self._handle_line(line.decode('ascii', errors='ignore').strip())

    def _handle_line(self, line: str):
        if not line:
            return
        parts = line.split()
        if len(parts) == 4 and parts[0] == 'E':
            try:
                d_left_ticks = int(parts[1])
                d_right_ticks = int(parts[2])
                dt_ms = float(parts[3])
            except ValueError:
                self.get_logger().debug(f'Malformed encoder line: {line!r}')
                return
            self._integrate(d_left_ticks, d_right_ticks, dt_ms / 1000.0)
        else:
            self.get_logger().debug(f'Unrecognized serial line: {line!r}')

    def _integrate(self, d_left_ticks: int, d_right_ticks: int, dt: float):
        if dt <= 0.0:
            return

        self.left_wheel_angle += d_left_ticks * self.radians_per_tick
        self.right_wheel_angle += d_right_ticks * self.radians_per_tick

        d_left = d_left_ticks * self.meters_per_tick
        d_right = d_right_ticks * self.meters_per_tick

       
        # velocity.
        self.left_wheel_velocity = (d_left / dt) / self.wheel_radius if self.wheel_radius > 0 else 0.0
        self.right_wheel_velocity = (d_right / dt) / self.wheel_radius if self.wheel_radius > 0 else 0.0

        d_center = (d_left + d_right) / 2.0
        d_theta = (d_right - d_left) / self.wheel_separation

        #For the same tick rate
        self.x += d_center * math.cos(self.theta + d_theta / 2.0)
        self.y += d_center * math.sin(self.theta + d_theta / 2.0)
        self.theta = math.atan2(
            math.sin(self.theta + d_theta), math.cos(self.theta + d_theta))

        self.v = d_center / dt
        self.w = d_theta / dt

        self._publish_odometry()
        self._publish_joint_states()

    def _publish_odometry(self):
        now = self.get_clock().now().to_msg()

        odom = Odometry()
        odom.header.stamp = now
        odom.header.frame_id = self.odom_frame_id
        odom.child_frame_id = self.base_frame_id
        odom.pose.pose.position.x = self.x
        odom.pose.pose.position.y = self.y
        odom.pose.pose.orientation = yaw_to_quaternion(self.theta)
        odom.twist.twist.linear.x = self.v
        odom.twist.twist.angular.z = self.w

     #Covariances
        odom.pose.covariance[0] = 0.05
        odom.pose.covariance[7] = 0.05
        odom.pose.covariance[35] = 0.1
        odom.twist.covariance[0] = 0.05
        odom.twist.covariance[35] = 0.1

        self.odom_pub.publish(odom)

        if self.publish_tf:
            t = TransformStamped()
            t.header.stamp = now
            t.header.frame_id = self.odom_frame_id
            t.child_frame_id = self.base_frame_id
            t.transform.translation.x = self.x
            t.transform.translation.y = self.y
            t.transform.translation.z = 0.0
            t.transform.rotation = yaw_to_quaternion(self.theta)
            self.tf_broadcaster.sendTransform(t)

    def _publish_joint_states(self):
        js = JointState()
        js.header.stamp = self.get_clock().now().to_msg()
        js.name = [self.left_wheel_joint, self.right_wheel_joint]
        js.position = [self.left_wheel_angle, self.right_wheel_angle]
        js.velocity = [self.left_wheel_velocity, self.right_wheel_velocity]
        self.joint_state_pub.publish(js)

    def _tick(self):
        self._read_serial()
        self._send_motor_command()

    def destroy_node(self):
        try:
            self.ser.write(b'M 0 0\n')
            time.sleep(0.05)
            self.ser.close()
        except Exception:
            pass
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = SerialBridgeNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
