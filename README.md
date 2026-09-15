# ESP32 Omni-Wheel Robot Controller

Sistem kendali robot omni-wheel berbasis ESP32 dan Raspberry Pi. Sistem ini menggunakan game controller sebagai input, Python sebagai pengirim data melalui Bluetooth Classic SPP, dan ESP32 sebagai penerima data yang mengolah pergerakan robot menggunakan inverse kinematics.

## 1. System Overview

Sistem terdiri dari tiga komponen utama:

* **Game Controller:** Menghasilkan input analog joystick dan tombol.
* **Raspberry Pi:** Menjalankan program Python untuk membaca input controller, menampilkan GUI monitor, dan mengirim data melalui Bluetooth.
* **ESP32:** Menerima data Bluetooth, menghitung kecepatan masing-masing motor, dan mengendalikan empat motor omni-wheel.

### System Architecture

```text
+-------------------+
|  Game Controller  |
+-------------------+
          |
          | Pygame
          v
+---------------------------+
| Raspberry Pi              |
| Python Controller Monitor |
| Tkinter + PyGame          |
+---------------------------+
          |
          | Bluetooth Classic SPP
          | /dev/rfcomm0
          v
+---------------------------+
| ESP32                     |
| BluetoothSerial           |
| Packet Parser             |
| Inverse Kinematics        |
+---------------------------+
          |
          v
+---------------------------+
| 4 Motor Driver Channels   |
| M1 | M2 | M3 | M4         |
+---------------------------+
          |
          v
+---------------------------+
| Omni-Wheel Robot          |
+---------------------------+
```

## 2. Features

* Membaca input analog joystick dan tombol menggunakan Pygame.
* Menampilkan nilai axis dan button secara real-time.
* Menampilkan visualisasi posisi analog stick.
* Menghubungkan Raspberry Pi dengan ESP32 melalui Bluetooth SPP.
* Mengirim data kendali dalam format paket yang terstruktur.
* Mengolah pergerakan robot dengan inverse kinematics.
* Mengatur kecepatan global robot.
* Mendukung kalibrasi individual setiap motor.
* Menggunakan deadband untuk mengurangi pergerakan akibat noise joystick.

## 3. Hardware Requirements

| Komponen           | Keterangan                               |
| ------------------ | ---------------------------------------- |
| ESP32              | Pengendali utama robot dan Bluetooth SPP |
| Raspberry Pi       | Menjalankan program Python               |
| Game Controller    | Input pergerakan dan tombol              |
| Motor Driver       | Pengendali daya motor DC                 |
| 4 Motor Omni-wheel | Sistem penggerak robot                   |
| Power Supply       | Sumber daya motor dan sistem kontrol     |

> Pastikan motor driver mendukung sinyal PWM dari ESP32 dan sumber daya motor sesuai dengan spesifikasi motor yang digunakan.

## 4. Software Requirements

* Arduino IDE atau PlatformIO untuk program ESP32.
* Python 3.
* Raspberry Pi OS atau sistem Linux yang mendukung Bluetooth Classic.
* Library `BluetoothSerial` pada ESP32.
* Library Python:

  * `pygame`
  * `pyserial`
  * `tkinter`

## 5. Project Structure

Contoh struktur repository:

```text
omni-wheel-controller/
├── README.md
├── esp32/
│   └── omni_controller.ino
└── raspberry-pi/
    └── controller_monitor.py
```

Simpan program ESP32 sebagai `omni_controller.ino` dan program Python sebagai `controller_monitor.py`.

---

# Part A — ESP32 Setup

## 6. Upload Program to ESP32

1. Buka Arduino IDE.
2. Pilih board ESP32 yang sesuai.
3. Buka file `omni_controller.ino`.
4. Hubungkan ESP32 ke komputer melalui USB.
5. Pilih port ESP32.
6. Upload program.

Program menggunakan:

```cpp
#include <Arduino.h>
#include <math.h>
#include "BluetoothSerial.h"
```

ESP32 akan menggunakan Bluetooth Classic SPP dengan nama perangkat:

```text
OMNI-ESP32
```

Ketika ESP32 berhasil dijalankan, Serial Monitor akan menampilkan:

```text
ESP32 Omni Diamond Ready. Layout: 1=depan,2=kanan,3=kiri,4=belakang
Bluetooth SPP aktif, cari perangkat: OMNI-ESP32
```

Atur baud rate Serial Monitor ke `115200`.

## 7. Motor Pin Configuration

Konfigurasi pin PWM pada program ESP32 adalah sebagai berikut:

| Motor | Posisi   | PWM Right | PWM Left |
| ----- | -------- | --------: | -------: |
| M1    | Depan    |   GPIO 15 |   GPIO 2 |
| M2    | Kanan    |    GPIO 4 |  GPIO 16 |
| M3    | Kiri     |   GPIO 18 |  GPIO 19 |
| M4    | Belakang |   GPIO 17 |   GPIO 5 |

### Layout Motor

```text
                M1
              DEPAN
                ^
                |
     M3 <-------+-------> M2
    KIRI               KANAN
                |
                v
             M4
           BELAKANG
```

**Catatan:** Penamaan posisi motor mengikuti komentar dan konfigurasi pada program ESP32. Pastikan arah putaran motor sesuai dengan posisi dan mekanik robot.

## 8. Motor Speed Configuration

### Maximum PWM

```cpp
const int maxPWM = 255;
```

Nilai PWM dibatasi pada rentang `-255` hingga `255`.

* Nilai positif: Motor bergerak menggunakan output `PWM_R`.
* Nilai negatif: Motor bergerak menggunakan output `PWM_L`.
* Nilai nol: Motor berhenti.

### Global Speed Scale

```cpp
const double SPEED_SCALE = 0.40;
```

`SPEED_SCALE` mengatur skala kecepatan global robot. Nilai `0.40` berarti perintah kecepatan translasi dan rotasi dikalikan 40%.

### Motor Calibration

```cpp
double CAL1 = 1.00;
double CAL2 = 1.00;
double CAL3 = 1.00;
double CAL4 = 1.00;
```

Kalibrasi digunakan untuk mengompensasi perbedaan karakteristik motor.

Contoh:

```cpp
double CAL1 = 1.10;
```

Motor 1 akan mendapatkan faktor kalibrasi 1.10 sebelum proses normalisasi PWM. Sesuaikan nilai ini berdasarkan hasil pengujian masing-masing motor.

---

# Part B — Raspberry Pi and Python Setup

## 9. Install System Dependencies

Update package list:

```bash
sudo apt update
```

Install Python, Bluetooth tools, dan library yang diperlukan:

```bash
sudo apt install python3 python3-pip python3-tk \
  python3-pygame python3-serial \
  bluez bluetooth
```

Pastikan perintah Bluetooth tersedia:

```bash
which bluetoothctl
which rfcomm
```

## 10. Create Python Environment

Buat direktori project:

```bash
mkdir -p ~/controller-monitor
cd ~/controller-monitor
```

Buat virtual environment:

```bash
python3 -m venv venv
```

Aktifkan environment:

```bash
source venv/bin/activate
```

Install library Python:

```bash
pip install pygame pyserial
```

> Jika menggunakan library Pygame dan PySerial dari package system, virtual environment tidak wajib digunakan. Pastikan kedua library tersedia pada Python yang menjalankan program.

## 11. Pair ESP32 with Raspberry Pi

Pastikan ESP32 sudah menyala dan programnya telah di-upload.

Jalankan:

```bash
bluetoothctl
```

Kemudian:

```text
power on
agent on
default-agent
scan on
```

Cari perangkat bernama:

```text
OMNI-ESP32
```

Catat MAC address yang ditampilkan. Contoh:

```text
AA:BB:CC:DD:EE:FF
```

Pair perangkat:

```text
pair AA:BB:CC:DD:EE:FF
trust AA:BB:CC:DD:EE:FF
connect AA:BB:CC:DD:EE:FF
```

Ganti MAC address contoh dengan MAC address ESP32 milikmu.

Keluar dari `bluetoothctl`:

```text
quit
```

### Cek perangkat yang pernah dipairing

Jika lupa MAC address ESP32:

```bash
bluetoothctl devices
```

Contoh:

```text
Device AA:BB:CC:DD:EE:FF OMNI-ESP32
```

Perintah ini dapat menampilkan perangkat Bluetooth yang tersimpan pada Raspberry Pi.

## 12. Bind Bluetooth SPP to RFCOMM

Program Python menggunakan device serial:

```text
/dev/rfcomm0
```

Buat binding RFCOMM:

```bash
sudo rfcomm bind /dev/rfcomm0 AA:BB:CC:DD:EE:FF 1
```

Keterangan:

* `/dev/rfcomm0`: Device serial virtual pada Raspberry Pi.
* `AA:BB:CC:DD:EE:FF`: MAC address ESP32.
* `1`: Channel RFCOMM SPP.

Periksa binding:

```bash
rfcomm
```

Contoh output:

```text
rfcomm0: AA:BB:CC:DD:EE:FF channel 1 connected
```

Periksa device:

```bash
ls -l /dev/rfcomm*
```

Output yang diharapkan:

```text
/dev/rfcomm0
```

> **Penting:** Jalankan binding RFCOMM sebelum menekan tombol `Refresh` pada aplikasi Python.

Jika ingin melepas binding:

```bash
sudo rfcomm release /dev/rfcomm0
```

---

# Part C — Running the System

## 13. Run the Python Controller Monitor

Masuk ke direktori project:

```bash
cd ~/controller-monitor
```

Aktifkan virtual environment:

```bash
source venv/bin/activate
```

Jalankan program:

```bash
python3 controller_monitor.py
```

Aplikasi akan menampilkan GUI dengan beberapa bagian:

* Bluetooth device selection.
* Tombol `Refresh`.
* Tombol `Connect` atau `Disconnect`.
* Status Bluetooth.
* Status game controller.
* Daftar axis.
* Daftar button.
* Visualisasi left dan right analog sticks.

## 14. Connect the Game Controller

1. Hubungkan game controller ke Raspberry Pi.
2. Jalankan aplikasi Python.
3. Pastikan status berubah menjadi nama controller yang terdeteksi.
4. Gerakkan analog stick.
5. Tekan tombol controller.
6. Pastikan nilai axis dan button berubah pada GUI.

Program memeriksa koneksi controller secara berkala setiap 2 detik.

## 15. Connect Python to ESP32

1. Pastikan ESP32 menyala.
2. Pastikan Bluetooth ESP32 bernama `OMNI-ESP32` aktif.
3. Pastikan Raspberry Pi telah melakukan pairing.
4. Jalankan binding RFCOMM.
5. Buka aplikasi Python.
6. Klik **Refresh**.
7. Pilih `/dev/rfcomm0`.
8. Klik **Connect**.
9. Pastikan status menunjukkan koneksi Bluetooth berhasil.

Setelah terhubung, program Python akan mengirim data joystick secara berkala.

---

# Part D — Communication Protocol

## 16. Data Flow

```text
Joystick Input
      |
      v
Pygame reads axes and buttons
      |
      v
Convert joystick values
      |
      v
Create data packet
      |
      v
Bluetooth SPP / RFCOMM
      |
      v
ESP32 receives packet
      |
      v
Parse X, Y, B6, B7
      |
      v
Convert to Vx, Vy, W
      |
      v
Inverse Kinematics
      |
      v
Motor PWM Output
```

## 17. Packet Format

Python mengirim data dalam format:

```text
<val_x,val_y,b6,b7>
```

Setiap paket diakhiri dengan karakter newline (`\n`).

Contoh:

```text
<128,128,0,0>
```

Format data:

| Field   | Keterangan                        |
| ------- | --------------------------------- |
| `val_x` | Nilai left joystick X-axis, 0–255 |
| `val_y` | Nilai left joystick Y-axis, 0–255 |
| `b6`    | Status button index 6, 0 atau 1   |
| `b7`    | Status button index 7, 0 atau 1   |

### Contoh Paket

```text
<255,127,0,0>
```

Interpretasi:

* `val_x = 255`
* `val_y = 127`
* `b6 = 0`
* `b7 = 0`

ESP32 membaca paket berdasarkan delimiter `<` dan `>` menggunakan parser karakter.

## 18. Joystick Mapping

Pada program Python:

```python
val_x = int((axes[0] + 1.0) * 127.5)
val_y = int((axes[1] + 1.0) * 127.5)
```

Axis joystick memiliki rentang sekitar `-1.0` hingga `1.0`, kemudian dikonversi ke rentang `0` hingga `255`.

Pada ESP32:

```cpp
double Vy = (double)(rawX - 127) * 2.0;
double Vx = (double)(rawY - 127) * 2.0;
```

Mapping yang digunakan:

| Input                | Variabel ESP32 | Fungsi                 |
| -------------------- | -------------- | ---------------------- |
| Left joystick X-axis | `Vy`           | Pergerakan kanan-kiri  |
| Left joystick Y-axis | `Vx`           | Pergerakan maju-mundur |
| Button 6             | `W = -5.0`     | Rotasi satu arah       |
| Button 7             | `W = 5.0`      | Rotasi arah berlawanan |

> Arah fisik pergerakan bergantung pada orientasi joystick, wiring motor, dan arah putaran motor. Lakukan pengujian arah sebelum mengoperasikan robot pada kecepatan tinggi.

## 19. Deadband

Program ESP32 menggunakan deadband:

```cpp
if (fabs(Vx) < 20) Vx = 0;
if (fabs(Vy) < 20) Vy = 0;
```

Jika nilai kecepatan translasi berada di bawah 20, nilainya diatur menjadi nol. Hal ini membantu mengurangi gerakan kecil akibat noise atau ketidakstabilan input joystick.

## 20. Inverse Kinematics

Sistem menggunakan layout motor berbentuk diamond:

```text
              M1 (Depan)

M3 (Kiri)                 M2 (Kanan)

             M4 (Belakang)
```

Rumus pada program:

```cpp
double M1 =  Vy + R * W;
double M2 =  Vx + R * W;
double M3 = -Vx + R * W;
double M4 = -Vy + R * W;
```

Dengan:

```cpp
double R = 7.6;
```

Keterangan:

* `Vx`: Komponen gerak maju-mundur.
* `Vy`: Komponen gerak kanan-kiri.
* `W`: Komponen rotasi.
* `R`: Parameter jarak/konstanta rotasi pada model inverse kinematics.

Setelah nilai motor dihitung, program menerapkan kalibrasi dan normalisasi agar nilai PWM tidak melebihi batas `255`.

## 21. Motor Control

Fungsi `setMotor()` menentukan arah motor berdasarkan tanda kecepatan:

```cpp
void setMotor(int motor, int speed)
```

* `speed > 0`: Mengaktifkan PWM kanan.
* `speed < 0`: Mengaktifkan PWM kiri.
* `speed == 0`: Tidak memberikan PWM pada kedua arah.

Fungsi `stopAll()` digunakan untuk menghentikan seluruh motor.

---

# Part E — Debugging and Troubleshooting

## 22. ESP32 Bluetooth Not Found

Pastikan:

* ESP32 telah di-upload program yang benar.
* ESP32 menyala.
* Bluetooth Classic aktif.
* Nama perangkat `OMNI-ESP32` muncul pada hasil scanning.

Pada Raspberry Pi:

```bash
bluetoothctl devices
```

Jika belum ditemukan, jalankan:

```text
scan on
```

di dalam `bluetoothctl`.

## 23. `/dev/rfcomm0` Does Not Exist

Periksa binding:

```bash
rfcomm
```

Jika belum ada, jalankan:

```bash
sudo rfcomm bind /dev/rfcomm0 AA:BB:CC:DD:EE:FF 1
```

Kemudian klik `Refresh` pada aplikasi Python.

## 24. Python Cannot Connect to Serial Device

Pastikan:

* Device `/dev/rfcomm0` tersedia.
* MAC address ESP32 benar.
* ESP32 telah dipairing.
* Tidak ada program lain yang sedang menggunakan device tersebut.

Periksa permission:

```bash
ls -l /dev/rfcomm0
```

Jika diperlukan untuk pengaturan akses serial, periksa grup pengguna:

```bash
groups
```

## 25. ESP32 Does Not Receive Data

Periksa:

1. Status Bluetooth pada GUI Python.
2. Output terminal Python untuk melihat paket yang dikirim.
3. Serial Monitor ESP32 untuk melihat pesan `[RAW]` dan `[PARSED]`.
4. Format paket `<X,Y,B6,B7>`.
5. Apakah Bluetooth SPP ESP32 menggunakan channel yang benar.

Contoh log ESP32:

```text
[RAW] "128,128,0,0"
[PARSED] X:[128] Y:[128] B6:[0] B7:[0]
```

## 26. Motor Does Not Move Correctly

Periksa:

* Wiring PWM motor driver.
* Posisi motor M1–M4.
* Arah putaran motor.
* Nilai `SPEED_SCALE`.
* Nilai kalibrasi `CAL1` hingga `CAL4`.
* Nilai deadband.
* Kesesuaian arah gerakan dengan layout robot.

Lakukan pengujian dengan robot dalam kondisi roda tidak menyentuh lantai atau menggunakan dudukan pengujian yang aman.

---

# Part F — Shutdown

## 27. Disconnect the System

1. Tekan **Disconnect** pada aplikasi Python.
2. Hentikan program Python dengan `Ctrl + C`.
3. Jika diperlukan, lepaskan binding RFCOMM:

```bash
sudo rfcomm release /dev/rfcomm0
```

4. Matikan daya motor dan ESP32 setelah sistem berhenti.

## 28. Future Improvements

Beberapa pengembangan yang dapat ditambahkan:

* Kontrol kecepatan menggunakan trigger atau tombol tambahan.
* Pengiriman data dengan checksum untuk validasi paket.
* Watchdog komunikasi untuk menghentikan motor jika koneksi terputus.
* Kalibrasi otomatis motor.
* Penyimpanan konfigurasi kalibrasi.
* Pengaturan arah motor melalui GUI.
* Penggunaan encoder untuk closed-loop speed control.

## License

This project is intended for educational and robotics development purposes.

Add your project author and license information here.
