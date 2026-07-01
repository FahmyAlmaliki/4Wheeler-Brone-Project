# ESP32 Mecanum Wheel Serial Controller

ESP32 firmware for controlling a **4-wheel mecanum robot** using **inverse kinematics** via serial communication.

The controller receives joystick data from an external device (such as a Raspberry Pi connected to a PS3/PS4 controller), converts the motion commands into individual wheel speeds, and drives four DC motors using PWM.

---

## Features

* 🚗 4-wheel mecanum drive
* 🎮 Serial joystick control
* ⚙️ Inverse kinematics calculation
* 🔄 Omnidirectional movement
* ↩️ Clockwise & Counter-Clockwise rotation
* 🛑 Built-in joystick deadband
* 📡 Simple serial packet protocol

---

## Hardware

### Microcontroller

* ESP32

### Motor Driver

Supports any H-Bridge motor driver that accepts:

* PWM Forward
* PWM Reverse

### Pin Configuration

| Motor   | Forward PWM | Reverse PWM |
| ------- | ----------: | ----------: |
| Motor 1 |     GPIO 16 |      GPIO 4 |
| Motor 2 |     GPIO 18 |     GPIO 19 |
| Motor 3 |      GPIO 5 |     GPIO 17 |
| Motor 4 |     GPIO 15 |      GPIO 2 |

---

## Serial Configuration

Baud Rate

```
115200
```

Packet format

```
<x,y,b6,b7>
```

Example

```
<127,127,0,0>
```

where

| Field | Description                       |
| ----- | --------------------------------- |
| x     | Left Stick X (0-255)              |
| y     | Left Stick Y (0-255)              |
| b6    | Rotate Counter-Clockwise (0 or 1) |
| b7    | Rotate Clockwise (0 or 1)         |

---

## Joystick Mapping

The firmware converts joystick values into robot velocities.

```
rawX -> Vy (Left / Right)

rawY -> Vx (Forward / Backward)
```

Joystick range

```
0 ~ 255
```

Converted to

```
-127 ~ +128
```

A deadband of **±10** is applied to eliminate joystick noise.

---

## Rotation Control

Rotation is controlled using two buttons.

| Button | Action            |
| ------ | ----------------- |
| b6     | Counter-Clockwise |
| b7     | Clockwise         |

Angular velocity values

```
b6 = 1 → W = -5

b7 = 1 → W = +5
```

---

## Inverse Kinematics

Wheel speeds are calculated using the standard mecanum inverse kinematics equation.

```
M1 =  sin(45°)Vx + cos(45°)Vy - RW
M2 =  sin(135°)Vx + cos(135°)Vy + RW
M3 =  sin(225°)Vx + cos(225°)Vy - RW
M4 =  sin(315°)Vx + cos(315°)Vy + RW
```

where

* `Vx` = Forward / Backward velocity
* `Vy` = Left / Right velocity
* `W` = Angular velocity
* `R = 7.6`

Motor outputs are automatically normalized to the maximum PWM value.

---

## PWM

Maximum PWM

```
255
```

Positive values

```
Forward
```

Negative values

```
Reverse
```

---

## Example Commands

Stop

```
<127,127,0,0>
```

Forward

```
<127,255,0,0>
```

Backward

```
<127,0,0,0>
```

Move Left

```
<0,127,0,0>
```

Move Right

```
<255,127,0,0>
```

Rotate Left

```
<127,127,1,0>
```

Rotate Right

```
<127,127,0,1>
```

Move Forward + Rotate Right

```
<127,255,0,1>
```

---

## Project Structure

```
.
├── src
│   └── main.cpp
└── README.md
```

---

## Usage

1. Upload the firmware to the ESP32.
2. Connect the motor driver according to the pin configuration.
3. Open the serial port at **115200 baud**.
4. Send joystick packets using the specified protocol.
5. The ESP32 computes inverse kinematics and drives all four motors.

---

## Typical System Architecture

```
Game Controller
        │
        ▼
 Raspberry Pi
 (Python Program)
        │
   USB Serial
        │
        ▼
      ESP32
        │
Inverse Kinematics
        │
        ▼
 Motor Driver
        │
        ▼
4 Mecanum Motors
```

---

## License

This project is released under the MIT License.
# 4Wheeler-Brone-Project
