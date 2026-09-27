from setuptools import find_packages, setup

package_name = 'goofy_motor_bridge'

setup(
    name=package_name,
    version='2.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/config', ['config/motor_bridge_params.yaml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Josephine',
    maintainer_email='josephinegangmei03@gmail.com',
    description='Serial bridge between ROS2 and the Arduino Nano/TB6612FNG motor MCU: cmd_vel in, odom + joint_states out.',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'serial_bridge_node = goofy_motor_bridge.serial_bridge_node:main',
        ],
    },
)
