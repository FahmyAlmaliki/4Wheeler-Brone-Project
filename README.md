# OMNI ESP32 Controller & Monitor

Sistem ini terdiri dari dua bagian utama:

1. **ESP32** sebagai pengendali motor melalui Bluetooth.
2. **Python Controller Monitor** sebagai aplikasi untuk membaca joystick dan mengirimkan perintah ke ESP32.

Komunikasi antara komputer/Raspberry Pi dan ESP32 menggunakan **Bluetooth RFCOMM** melalui port `/dev/rfcomm0`.

---

## 1. Arsitektur Sistem

```text
Joystick
   │
   ▼
Python Controller Monitor
   │
   │ Bluetooth RFCOMM
   ▼
/dev/rfcomm0
   │
   ▼
ESP32
   │
   ▼
Motor Driver
   │
   ▼
Motor M1, M2, M3, M4
```

---

## 2. Komponen Sistem

### Perangkat Keras

* ESP32
* Motor driver
* Empat motor
* Joystick/controller
* Komputer atau Raspberry Pi
* Kabel USB untuk pemrograman ESP32
* Modul Bluetooth bawaan ESP32

### Perangkat Lunak

* Arduino IDE
* Python 3
* Tkinter
* Pygame
* PySerial
* Bluetooth RFCOMM

---

## 3. Konfigurasi Bluetooth ESP32

ESP32 menggunakan Bluetooth Classic dengan nama perangkat:

```text
OMNI-ESP32
```

Alamat Bluetooth ESP32:

```text
8C:94:DF:4C:D2:EA
```

Channel RFCOMM:

```text
1
```

Port yang digunakan pada komputer atau Raspberry Pi:

```text
/dev/rfcomm0
```

---

## 4. Konfigurasi Pin Motor ESP32

| Motor | PWM Right | PWM Left | Posisi   |
| ----- | --------: | -------: | -------- |
| M1    |   GPIO 15 |   GPIO 2 | Depan    |
| M2    |    GPIO 4 |  GPIO 16 | Kanan    |
| M3    |   GPIO 18 |  GPIO 19 | Kiri     |
| M4    |   GPIO 17 |   GPIO 5 | Belakang |

Konfigurasi tambahan:

```cpp
const int maxPWM = 255;
const float SPEED_SCALE = 0.40;
```

Nilai `SPEED_SCALE` digunakan untuk membatasi kecepatan motor agar tidak langsung bekerja pada daya maksimum.

---

## 5. Format Data Komunikasi

Python mengirimkan data ke ESP32 dalam format berikut:

```text
<x,y,b6,b7>
```

Contoh:

```text
<127,127,0,0>
```

Keterangan:

| Data | Fungsi                 |
| ---- | ---------------------- |
| `x`  | Nilai sumbu X joystick |
| `y`  | Nilai sumbu Y joystick |
| `b6` | Status tombol 6        |
| `b7` | Status tombol 7        |

Nilai joystick berada pada rentang:

```text
0–255
```

ESP32 kemudian mengubah nilai tersebut menjadi perintah gerakan:

* `Vx` untuk gerakan lateral
* `Vy` untuk gerakan maju atau mundur
* `W` untuk rotasi

---

## 6. Kontrol Gerakan

ESP32 menggunakan metode inverse kinematics untuk mengatur empat motor.

Rumus yang digunakan:

```text
M1 = Vy + R × W
M2 = Vx + R × W
M3 = -Vx + R × W
M4 = -Vy + R × W
```

Dengan:

```text
R = 7.6
```

Keterangan:

* `Vx` merupakan gerakan ke kanan atau kiri.
* `Vy` merupakan gerakan maju atau mundur.
* `W` merupakan gerakan rotasi.
* `M1`, `M2`, `M3`, dan `M4` merupakan kecepatan masing-masing motor.

ESP32 juga menggunakan deadband untuk menghindari gerakan kecil akibat noise joystick.

```text
Deadband = 20
```

---

## 7. Instalasi Program ESP32

### 7.1 Membuka Program

1. Buka **Arduino IDE**.
2. Masukkan program ESP32.
3. Pilih board ESP32 yang sesuai.
4. Pilih port USB ESP32.
5. Klik **Upload**.

### 7.2 Memastikan Bluetooth Aktif

Setelah program berhasil di-upload:

1. Nyalakan ESP32.
2. Buka Serial Monitor jika diperlukan.
3. Pastikan Bluetooth ESP32 aktif dengan nama:

```text
OMNI-ESP32
```

ESP32 akan menunggu koneksi Bluetooth dari komputer atau Raspberry Pi.

---

## 8. Instalasi Python Controller Monitor

Masuk ke folder program Python:

```bash
cd ~/controller-monitor
```

Buat virtual environment:

```bash
python3 -m venv venv
```

Aktifkan virtual environment:

```bash
source venv/bin/activate
```

Install library yang diperlukan:

```bash
pip install pyserial pygame
```

Tkinter biasanya sudah tersedia pada sistem Linux. Jika belum tersedia, install dengan:

```bash
sudo apt install python3-tk
```

---

## 9. Menyiapkan Bluetooth RFCOMM

Pastikan perangkat Bluetooth ESP32 sudah pernah dipasangkan dengan komputer atau Raspberry Pi.

Cek perangkat RFCOMM dengan perintah:

```bash
rfcomm
```

Jika muncul:

```text
rfcomm0: 8C:94:DF:4C:D2:EA channel 1 closed
```

artinya konfigurasi RFCOMM untuk ESP32 sudah terdaftar, tetapi koneksi Bluetooth belum sedang aktif. Kondisi ini masih dapat digunakan karena koneksi akan dicoba ketika program Python membuka port `/dev/rfcomm0`.

Port yang digunakan adalah:

```text
/dev/rfcomm0
```

---

## 10. Jika `/dev/rfcomm0` Belum Terdaftar

Jika perintah `rfcomm` tidak menampilkan `rfcomm0`, buat binding secara manual:

```bash
sudo rfcomm bind /dev/rfcomm0 8C:94:DF:4C:D2:EA 1
```

Kemudian periksa kembali:

```bash
rfcomm
```

Jika berhasil, akan muncul perangkat dengan alamat:

```text
8C:94:DF:4C:D2:EA
```

dan channel:

```text
1
```

---

## 11. Jika Binding RFCOMM Bermasalah

Jika muncul pesan bahwa `/dev/rfcomm0` sudah digunakan atau binding mengalami masalah, lepaskan binding terlebih dahulu:

```bash
sudo rfcomm release /dev/rfcomm0
```

Kemudian buat binding kembali:

```bash
sudo rfcomm bind /dev/rfcomm0 8C:94:DF:4C:D2:EA 1
```

Periksa hasilnya:

```bash
rfcomm
```

---

## 12. Menjalankan Sistem

Setelah ESP32 dinyalakan, lakukan langkah berikut.

### Langkah 1 — Nyalakan ESP32

Nyalakan ESP32 dan pastikan Bluetooth dengan nama `OMNI-ESP32` aktif.

### Langkah 2 — Periksa RFCOMM

```bash
rfcomm
```

Jika muncul:

```text
rfcomm0: 8C:94:DF:4C:D2:EA channel 1 closed
```

lanjutkan ke langkah berikutnya.

Jika `rfcomm0` belum muncul, jalankan:

```bash
sudo rfcomm bind /dev/rfcomm0 8C:94:DF:4C:D2:EA 1
```

### Langkah 3 — Aktifkan Virtual Environment

```bash
cd ~/controller-monitor
source venv/bin/activate
```

### Langkah 4 — Jalankan Program Python

```bash
python3 controller_monitor.py
```

### Langkah 5 — Hubungkan Port pada GUI

Pada aplikasi Python:

1. Klik **Refresh**.
2. Pilih port:

```text
/dev/rfcomm0
```

3. Klik **Connect**.
4. Nyalakan atau hubungkan joystick.
5. Gerakkan joystick untuk mengendalikan motor.

---

## 13. Alur Penggunaan Normal

Pada penggunaan berikutnya, alurnya cukup:

```text
1. Nyalakan ESP32
2. Jalankan rfcomm
3. Jalankan program Python
4. Klik Refresh pada GUI
5. Pilih /dev/rfcomm0
6. Klik Connect
```

Jika `rfcomm0` belum tersedia, jalankan:

```bash
sudo rfcomm bind /dev/rfcomm0 8C:94:DF:4C:D2:EA 1
```

---

## 14. Menjalankan Program Secara Singkat

Jika RFCOMM sudah terdaftar, gunakan:

```bash
cd ~/controller-monitor
source venv/bin/activate
python3 controller_monitor.py
```

Jika RFCOMM belum terdaftar, gunakan:

```bash
sudo rfcomm bind /dev/rfcomm0 8C:94:DF:4C:D2:EA 1
```

kemudian jalankan program Python.

---

## 15. Fitur Python Controller Monitor

Program Python memiliki beberapa fungsi utama:

* Membaca input joystick.
* Menampilkan nilai sumbu X dan Y.
* Membaca status tombol joystick.
* Mengirimkan data melalui Bluetooth.
* Menampilkan port serial yang tersedia.
* Melakukan refresh daftar port.
* Menghubungkan dan memutuskan koneksi serial.
* Menampilkan status koneksi.
* Mengirimkan data secara berkala ke ESP32.

Data yang dikirimkan memiliki format:

```text
<x,y,b6,b7>
```

Contoh data ketika joystick berada di posisi tengah:

```text
<127,127,0,0>
```

---

## 16. Troubleshooting

### 16.1 Port `/dev/rfcomm0` Tidak Muncul

Jalankan:

```bash
rfcomm
```

Jika belum muncul, jalankan:

```bash
sudo rfcomm bind /dev/rfcomm0 8C:94:DF:4C:D2:EA 1
```

---

### 16.2 Muncul Pesan `channel 1 closed`

Contoh:

```text
rfcomm0: 8C:94:DF:4C:D2:EA channel 1 closed
```

Pesan tersebut menunjukkan bahwa binding RFCOMM sudah ada, tetapi sesi koneksi belum aktif.

Coba langsung jalankan program Python dan hubungkan port `/dev/rfcomm0` melalui GUI.

---

### 16.3 Python Tidak Menemukan Port

Pastikan port tersedia:

```bash
ls /dev/rfcomm*
```

Periksa juga:

```bash
python3 -m serial.tools.list_ports
```

Jika port belum tersedia, buat binding:

```bash
sudo rfcomm bind /dev/rfcomm0 8C:94:DF:4C:D2:EA 1
```

---

### 16.4 Tidak Bisa Terhubung ke ESP32

Pastikan:

* ESP32 dalam keadaan menyala.
* Bluetooth ESP32 aktif.
* Alamat Bluetooth benar.
* Channel RFCOMM menggunakan channel `1`.
* Port yang dipilih adalah `/dev/rfcomm0`.
* Tidak ada program lain yang sedang menggunakan port tersebut.

Jika masih gagal, lepaskan binding:

```bash
sudo rfcomm release /dev/rfcomm0
```

Kemudian buat ulang:

```bash
sudo rfcomm bind /dev/rfcomm0 8C:94:DF:4C:D2:EA 1
```

---

### 16.5 Motor Tidak Bergerak

Periksa:

* Catu daya motor.
* Koneksi motor driver.
* Pin GPIO ESP32.
* Program ESP32 sudah berhasil di-upload.
* Format data yang dikirim Python.
* Status koneksi Bluetooth.
* Nilai joystick.
* Nilai deadband.

Pastikan ESP32 menerima data dengan format yang benar:

```text
<127,127,0,0>
```

---

### 16.6 Motor Bergerak Tidak Sesuai Arah

Periksa:

* Urutan motor M1 sampai M4.
* Kabel motor.
* Konfigurasi PWM Right dan PWM Left.
* Nilai `CAL1`, `CAL2`, `CAL3`, dan `CAL4`.
* Rumus inverse kinematics.
* Arah sumbu joystick.

---

## 17. Perintah Penting

### Melihat perangkat RFCOMM

```bash
rfcomm
```

### Melihat port serial

```bash
python3 -m serial.tools.list_ports
```

### Melihat perangkat RFCOMM

```bash
ls /dev/rfcomm*
```

### Membuat binding RFCOMM

```bash
sudo rfcomm bind /dev/rfcomm0 8C:94:DF:4C:D2:EA 1
```

### Melepaskan binding RFCOMM

```bash
sudo rfcomm release /dev/rfcomm0
```

### Mengaktifkan virtual environment

```bash
source venv/bin/activate
```

### Menjalankan program Python

```bash
python3 controller_monitor.py
```

---

## 18. Ringkasan

Sistem dijalankan dengan alur berikut:

```text
Nyalakan ESP32
      │
      ▼
Periksa rfcomm
      │
      ├── rfcomm0 tersedia
      │       │
      │       ▼
      │   Jalankan Python
      │
      └── rfcomm0 belum tersedia
              │
              ▼
      sudo rfcomm bind /dev/rfcomm0 8C:94:DF:4C:D2:EA 1
              │
              ▼
        Jalankan Python
              │
              ▼
      Refresh dan Connect
              │
              ▼
       Kendalikan motor
```

Dengan konfigurasi yang sudah tersimpan, pengguna tidak perlu melakukan pairing ulang setiap kali menggunakan sistem. Cukup nyalakan ESP32, pastikan `/dev/rfcomm0` tersedia, lalu jalankan program Python.
