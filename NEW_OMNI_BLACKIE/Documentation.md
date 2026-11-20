# Dokumentasi Teknis Lengkap: Sistem Kendali & Odometri Robot Omni-Wheel 4 Roda

Dokumen ini berisi penjelasan mendalam mengenai arsitektur perangkat lunak, logika pemrograman, perumusan kinematika, dan antarmuka perangkat keras untuk dua program utama:
1. **`Program_Controller_Windows.py`**: Aplikasi desktop berbasis Python untuk pembacaan *gamepad*, komunikasi Bluetooth Serial, dan visualisasi odometri *real-time*.
2. **`Program_ESP.ino`**: Firmware mikrokontroler ESP32 untuk kontrol motor DC, akuisisi data 4 *rotary encoder*, dan kalkulasi kinematika maju/balik (*Forward & Inverse Kinematics*).

---

## 📑 Daftar Isi
1. [Gambaran Umum & Alur Data Sistem](#1-gambaran-umum--alur-data-sistem)
2. [Bedah Kode: `Program_Controller_Windows.py`](#2-bedah-kode-program_controller_windowspy)
   - [Arsitektur Threading & Event Loop](#21-arsitektur-threading--event-loop)
   - [Manajemen Koneksi Bluetooth/Serial](#22-manajemen-koneksi-bluetoothserial)
   - [Akuisisi & Pemetaan Input Gamepad](#23-akuisisi--pemetaan-input-gamepad)
   - [Parser Telemetri & Visualisasi Mini-Map 2D](#24-parser-telemetri--visualisasi-mini-map-2d)
3. [Bedah Kode: `Program_ESP.ino`](#3-bedah-kode-program_espino)
   - [Konfigurasi Pin & Perangkat Keras](#31-konfigurasi-pin--perangkat-keras)
   - [Akuisisi Encoder Berbasis Hardware PCNT](#32-akuisisi-encoder-berbasis-hardware-pcnt)
   - [Inverse Kinematics (Kontrol Gerak Robot)](#33-inverse-kinematics-kontrol-gerak-robot)
   - [Forward Kinematics (Kalkulasi Odometri)](#34-forward-kinematics-kalkulasi-odometri)
   - [State-Machine Packet Parser](#35-state-machine-packet-parser)
4. [Spesifikasi Protokol Komunikasi](#4-spesifikasi-protokol-komunikasi)
5. [Panduan Troubleshooting & Kalibrasi](#5-panduan-troubleshooting--kalibrasi)

---

## 1. Gambaran Umum & Alur Data Sistem

Sistem ini bekerja secara **asinkron dua arah (*full-duplex*)** melalui jalur komunikasi serial nirkabel **Bluetooth SPP (Serial Port Profile)** pada kecepatan **115.200 bps**:

1. **Siklus Kontrol (PC $\rightarrow$ ESP32 | 20 Hz / setiap 50 ms):**
   - Python membaca posisi tuas analog dan status tombol pada *gamepad* melalui pustaka `pygame`.
   - Data dikonversi ke rentang integer `0–255` dan dikirim dalam paket berbingkai `<val_x,val_y,b4,b5>\n`.
   - ESP32 mem-parsing paket tersebut, melakukan transformasi rotasi $45^\circ$, menghitung *Inverse Kinematics*, dan mengeluarkan sinyal PWM ke 4 driver motor.

2. **Siklus Telemetri (ESP32 $\rightarrow$ PC | 20 Hz / setiap 50 ms):**
   - Modul *Pulse Counter* (PCNT) pada ESP32 menghitung pulsa dari 4 *rotary encoder* secara independen di level *hardware*.
   - Setiap 50 ms, ESP32 menghitung perubahan jarak masing-masing roda, mengintegrasikannya menjadi posisi global $(X, Y, \theta)$ melalui *Forward Kinematics*, dan mengirimkannya dalam format `<ODOM,X,Y,Theta,Vx,Vy,W>\n`.
   - Python menangkap aliran data tersebut, menyimpannya ke dalam buffer, dan memperbarui indikator angka serta kanvas peta 2D.

---

## 2. Bedah Kode: `Program_Controller_Windows.py`

Aplikasi desktop ini dibangun menggunakan **Tkinter** (GUI), **Pygame** (antarmuka *joystick*), dan **PySerial** (komunikasi port COM).

### 2.1 Arsitektur Threading & Event Loop
Karena Tkinter bersifat *single-threaded*, operasi yang memblokir (*blocking*) dapat membuat jendela aplikasi *hang*. Program mengatasi hal ini dengan tiga mekanisme:
* **Background Thread (`_do_connect`):** Proses pembukaan koneksi serial (`serial.Serial(...)`) dijalankan di dalam *daemon thread* terpisah agar antarmuka tetap responsif saat menunggu *handshake* Bluetooth.
* **Loop Pembacaan & Pengiriman (`read_input`):** Dijalankan secara periodik setiap **50 ms** menggunakan `root.after(50, read_input)` untuk membaca buffer masuk dari ESP32 sekaligus mengirimkan status terbaru *gamepad*.
* **Loop Deteksi Perangkat (`check_connection`):** Berjalan setiap **2000 ms** (2 detik) untuk mendeteksi jika *gamepad* baru dicolokkan (*hot-plug*) atau terputus di tengah penggunaan.

### 2.2 Manajemen Koneksi Bluetooth/Serial
* **`get_available_ports()`**: Mendeteksi seluruh port serial aktif secara lintas platform:
  * **Windows:** Memindai `serial.tools.list_ports.comports()` dan mengidentifikasi port Bluetooth menggunakan kata kunci `"bluetooth"`, `"bthenum"`, `"bth"`, atau UUID SPP `{00001101` pada *Hardware ID*, lalu mengurutkannya di bagian paling atas *dropdown*.
  * **Linux:** Memindai perangkat `/dev/rfcomm*` dan `/dev/ttyUSB*`.
* **`open_bt_settings()`**: Menyediakan pintasan satu klik untuk membuka `ms-settings:bluetooth` (Windows) atau `blueman-manager` (Linux) guna mempermudah proses *pairing* awal.

### 2.3 Akuisisi & Pemetaan Input Gamepad
Pada fungsi `read_input()`:
* **Sumbu Analog Kiri (`axes[0]` & `axes[1]`):** Nilai *floating-point* dari Pygame berada pada rentang `-1.0` hingga `+1.0`. Nilai ini dinormalisasi menjadi bilangan bulat `0` hingga `255` menggunakan rumus:
  $$\text{val} = \text{int}((\text{axis} + 1.0) \times 127.5)$$
  Nilai tengah (netral) berada pada `127`.
* **Tombol Rotasi (`buttons[4]` & `buttons[5]`):** Membaca tombol bahu kiri (`B4` / L1) untuk berputar berlawanan arah jarum jam dan tombol bahu kanan (`B5` / R1) untuk berputar searah jarum jam.
* **Visualisasi Analog:** Menggambar lingkaran indikator pada `left_canvas` dan `right_canvas` dengan memetakan koordinat `-1.0..1.0` ke radius `40 px` dari titik pusat kanvas `(50, 50)`.

### 2.4 Parser Telemetri & Visualisasi Mini-Map 2D
* **`parse_incoming_packets(raw_text)`**: Mengakumulasi potongan string serial yang masuk ke variabel global `rx_buffer`. Parser mencari karakter pembuka `<` dan penutup `>` secara berurutan agar data tetap utuh meskipun terpotong oleh latensi transmisi Bluetooth (*packet fragmentation*).
* **Koreksi Skala Sudut (`THETA_SCALE = 0.5`)**: Nilai `Theta` dan kecepatan sudut `W` dari ESP32 dikalikan `0.5` sebagai faktor kalibrasi empiris (mengoreksi pembacaan $180^\circ$ menjadi $90^\circ$ aktual).
* **`update_odom_gui()`**:
  * **Konversi Koordinat Layar:** Sistem koordinat robot menggunakan $+X$ sebagai arah maju (atas pada layar) dan $+Y$ sebagai arah geser kanan (kanan pada layar). Konversi ke piksel kanvas berukuran `240x240` (pusat di `cx=120, cy=120`) dilakukan dengan:
    $$px = 120 + (Y \times \text{MAP\_SCALE})$$
    $$py = 120 - (X \times \text{MAP\_SCALE})$$
  * **Jejak Lintasan (*Trail*):** Menyimpan maksimal `500` titik koordinat terakhir (jika robot berpindah lebih dari `0.5 cm`) untuk menggambar garis lintasan biru (`#4da6ff`), titik posisi robot, serta vektor panah merah untuk orientasi hadap ($\theta$).

---

## 3. Bedah Kode: `Program_ESP.ino`

Firmware ini dirancang untuk mikrokontroler **ESP32** menggunakan kerangka kerja Arduino dengan pembagian tugas *real-time* non-blocking berbasis `millis()`.

### 3.1 Konfigurasi Pin & Perangkat Keras
* **Driver Motor (4 Kanal Dual-PWM, misal TB6612FNG / BTS7960):**
  Setiap motor dikendalikan oleh dua pin PWM (`PWM_R` untuk putaran maju/kanan dan `PWM_L` untuk putaran mundur/kiri):
  * **Motor 1 (Kanan):** `GPIO 15` (R), `GPIO 2` (L)
  * **Motor 2 (Depan):** `GPIO 4` (R), `GPIO 16` (L)
  * **Motor 3 (Belakang):** `GPIO 18` (R), `GPIO 19` (L)
  * **Motor 4 (Kiri):** `GPIO 17` (R), `GPIO 5` (L)
* **4 Rotary Encoder (`YT06-OP`, 600 PPR):**
  Ditempatkan pada pin input yang mendukung interupsi/PCNT tanpa konflik dengan pin motor:
  * **Encoder 0 (Kanan):** `GPIO 27` (A), `GPIO 14` (B)
  * **Encoder 1 (Depan):** `GPIO 25` (A), `GPIO 26` (B)
  * **Encoder 2 (Kiri):** `GPIO 32` (A), `GPIO 33` (B)
  * **Encoder 3 (Belakang):** `GPIO 34` (A), `GPIO 35` (B) *(Pin khusus input)*

### 3.2 Akuisisi Encoder Berbasis Hardware PCNT
* Menggunakan pustaka `ESP32Encoder` dengan mode `attachFullQuad()`, yang membaca *rising* dan *falling edge* pada kedua kanal A dan B (*4x Quadrature Decoding*).
* Resolusi efektif per putaran menjadi:
  $$\text{COUNTS\_PER\_REV} = 600 \times 4 = 2400 \text{ pulsa/putaran}$$
* **Mekanika Coupled Wheel:** Roda encoder berdiameter **48 mm** (`4.8 cm`) menempel pada permukaan luar roda omni **150 mm**. Karena kecepatan tangensial pada titik kontak sama, jarak tempuh linear dihitung langsung dari keliling roda encoder:
  $$\text{CM\_PER\_COUNT} = \frac{\pi \times 4.8}{2400} \approx 0.006283 \text{ cm/pulsa}$$
* Array `ENC_DIR[4] = {-1.0, -1.0, -1.0, -1.0}` membalik tanda pembacaan karena roda encoder bersinggungan dari luar sehingga berputar berlawanan arah dengan roda utama.

### 3.3 Inverse Kinematics (Kontrol Gerak Robot)
Robot menggunakan konfigurasi **4 roda Omni-Wheel berbentuk Diamond** (Depan, Belakang, Kiri, Kanan), namun orientasi depan robot diputar sebesar **$45^\circ$** (sehingga arah maju robot berada di antara Roda Depan dan Roda Kanan).

1. **Transformasi Input Analog (`processPacket`):**
   - Input `rawX` dan `rawY` (`0–255`) digeser ke titik tengah `127` dan dikalikan `2.0` untuk mendapatkan rentang kecepatan `[-254, +256]`.
   - Diterapkan matriks rotasi $45^\circ$ ($\cos 45^\circ \approx 0.7071$, $\sin 45^\circ \approx -0.7071$):
     $$V_{x,\text{rot}} = V_x \cos 45^\circ - V_y \sin 45^\circ$$
     $$V_{y,\text{rot}} = V_x \sin 45^\circ + V_y \cos 45^\circ$$
   - **Deadband:** Nilai $|V_x| < 20$ atau $|V_y| < 20$ dianggap `0` untuk mencegah motor berdengung akibat *drift* tuas analog.
   - **Skala Translasi:** Dikalikan `TRANSLATE_SCALE = 0.2` sebagai pembatas kecepatan maksimal agar pergerakan tetap terkendali.

2. **Persamaan Kinematika Roda (`Inverse_Kinematics`):**
   Dengan radius pusat robot ke titik kontak roda $R = 7.6\text{ cm}$ dan kecepatan sudut $W \in \{-5.0, 0, +5.0\}$:
   $$M_1 = V_y + R \cdot W$$
   $$M_2 = V_x + R \cdot W$$
   $$M_3 = -V_x + R \cdot W$$
   $$M_4 = -V_y + R \cdot W$$
   Jika nilai salah satu motor melebihi `maxPWM` (`255`), seluruh nilai motor diskalakan secara proporsional agar arah vektor gerak robot tidak berubah (*vector normalization*).

### 3.4 Forward Kinematics (Kalkulasi Odometri)
Pada fungsi `updateOdometry(double dt_sec)`:
1. **Perpindahan Kerangka Diamond:**
   $$\Delta x_{\text{diamond}} = \frac{d_0 - d_2}{2}, \quad \Delta y_{\text{diamond}} = \frac{d_1 - d_3}{2}$$
   $$\Delta \theta = \frac{d_0 + d_1 + d_2 + d_3}{4 R}$$
   *(di mana $d_0=\text{Kanan}, d_1=\text{Depan}, d_2=\text{Kiri}, d_3=\text{Belakang}$)*.

2. **Proyeksi ke Sumbu Robot (Rotasi Balik $-45^\circ$):**
   $$\Delta x_{\text{robot}} = \Delta x_{\text{diamond}} \cos 45^\circ + \Delta y_{\text{diamond}} \sin 45^\circ$$
   $$\Delta y_{\text{robot}} = \Delta x_{\text{diamond}} \sin 45^\circ - \Delta y_{\text{diamond}} \cos 45^\circ$$

3. **Integrasi Odometri Runge-Kutta Orde-2 (*Midpoint Integration*):**
   Untuk meminimalkan galat integrasi saat robot bergerak melengkung (*arc*), digunakan sudut tengah $\theta_{\text{mid}} = \theta + \frac{\Delta \theta}{2}$:
   $$X_{\text{global}} \leftarrow X_{\text{global}} + \Delta x_{\text{robot}} \cos(\theta_{\text{mid}}) - \Delta y_{\text{robot}} \sin(\theta_{\text{mid}})$$
   $$Y_{\text{global}} \leftarrow Y_{\text{global}} + \Delta x_{\text{robot}} \sin(\theta_{\text{mid}}) + \Delta y_{\text{robot}} \cos(\theta_{\text{mid}})$$
   $$\theta \leftarrow \theta + \Delta \theta$$

### 3.5 State-Machine Packet Parser
Struktur `PacketParser` membaca aliran karakter satu per satu (`char-by-char`) baik dari `SerialBT` (Bluetooth utama) maupun `Serial` (USB Serial cadangan untuk *debugging*):
* Karakter `<` mengaktifkan flag `inPacket = true` dan mengosongkan buffer string.
* Karakter di antara `<` dan `>` ditambahkan ke `inputString`.
* Karakter `>` memicu eksekusi `processPacket(inputString)` dan mereset *state*.
* Jika paket berisi string `"RESET"`, fungsi `resetOdometry()` dipanggil untuk mengosongkan register *hardware counter* ESP32 dan mengembalikan koordinat ke `(0, 0, 0)`.

---

## 4. Spesifikasi Protokol Komunikasi

| Arah Transmisi | Format Paket | Contoh Payload | Keterangan Parameter |
| :--- | :--- | :--- | :--- |
| **PC $\rightarrow$ ESP32** | `<val_x,val_y,b4,b5>\n` | `<127,255,0,1>\n` | `val_x`, `val_y`: `0–255` (`127` = diam)<br>`b4`: `1` = putar kiri, `b5`: `1` = putar kanan |
| **PC $\rightarrow$ ESP32** | `<RESET>\n` | `<RESET>\n` | Me-reset koordinat odometri & counter encoder ke `0` |
| **ESP32 $\rightarrow$ PC** | `<ODOM,X,Y,Theta,Vx,Vy,W>\n` | `<ODOM,15.40,-3.20,45.00,12.50,0.00,0.000>\n` | `X, Y`: Posisi global (`cm`)<br>`Theta`: Sudut hadap (`deg`)<br>`Vx, Vy`: Kecepatan (`cm/s`), `W`: (`rad/s`) |

---

## 5. Panduan Troubleshooting & Kalibrasi

1. **Arah Gerak Robot Terbalik Saat Didorong Manual:**
   - Buka aplikasi GUI Python, dorong robot maju lurus ke depan sejauh 100 cm.
   - Jika nilai `X` pada GUI bernilai negatif (`-100 cm`), ubah tanda elemen pada array `ENC_DIR[4]` di `Program_ESP.ino` dari `-1.0` menjadi `1.0` pada roda yang bersangkutan.
2. **Kecepatan Motor Tidak Seimbang (Robot Berbelok Saat Maju Lurus):**
   - Sesuaikan konstanta pengali PWM `CAL1` hingga `CAL4` (rentang `0.80` – `1.00`) pada `Program_ESP.ino` untuk mengompensasi perbedaan karakteristik fisik antar motor DC.
3. **Port Bluetooth Tidak Merespons di Windows:**
   - Windows secara otomatis membuat **dua** COM Port saat melakukan *pairing* perangkat Bluetooth SPP (*Incoming* dan *Outgoing*). Pastikan memilih port **Outgoing** (biasanya bernomor COM lebih kecil atau terdeteksi otomatis oleh tombol `Refresh`).
