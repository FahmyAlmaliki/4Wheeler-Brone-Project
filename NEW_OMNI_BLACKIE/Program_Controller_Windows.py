import tkinter as tk
from tkinter import ttk, messagebox
import pygame
import math
import serial
import serial.tools.list_ports
import time
import platform
import os
import threading
import glob

# --- init pygame ---
pygame.init()
pygame.joystick.init()

# --- Variabel Global ---
joystick = None
connected = False
axis_labels = []
button_labels = []

button_frame_row1 = None
button_frame_row2 = None

left_canvas = None
right_canvas = None
left_stick_dot = None
right_stick_dot = None

# --- Variabel Bluetooth / Serial ---
ser = None
port_var = None
port_map = {}  # Pemetaan label display -> nama port fisik
rx_buffer = "" # Buffer penampung data masuk dari ESP32

# Baud rate serial (standar ESP32)
RFCOMM_BAUD = 115200

# --- Variabel Odometri dari ESP32 ---
odom_x = 0.0
odom_y = 0.0
odom_theta = 0.0
odom_vx = 0.0
odom_vy = 0.0
odom_w = 0.0
odom_trail = []        # Menyimpan riwayat koordinat (x, y) untuk digambar
MAP_SCALE = 1.0        # 1 pixel = 1 cm
THETA_SCALE = 0.5      # Koreksi skala sudut (180 deg terbaca -> 90 deg aktual)


def get_available_ports():
    """
    Mengambil daftar port serial dan Bluetooth yang tersedia.
    Mendukung Windows (COM port Bluetooth SPP & USB) dan Linux (/dev/rfcomm*, /dev/ttyUSB*).
    """
    ports = []
    system = platform.system()

    if system == "Windows":
        for p in serial.tools.list_ports.comports():
            desc = p.description or ""
            hwid = p.hwid or ""

            is_bt = (
                "bluetooth" in desc.lower()
                or "bthenum" in hwid.lower()
                or "bth" in hwid.lower()
                or "{00001101" in hwid.lower()
            )
            tag = " [Bluetooth]" if is_bt else ""
            display_label = f"{p.device} - {desc}{tag}"
            ports.append((p.device, display_label, is_bt))

        ports.sort(key=lambda x: (not x[2], x[0]))

    else:
        for dev in glob.glob('/dev/rfcomm*'):
            ports.append((dev, f"{dev} [Bluetooth RFCOMM]", True))

        for p in serial.tools.list_ports.comports():
            if not any(p.device == item[0] for item in ports):
                desc = p.description or ""
                is_bt = "rfcomm" in p.device.lower() or "bluetooth" in desc.lower()
                tag = " [Bluetooth]" if is_bt else ""
                ports.append((p.device, f"{p.device} - {desc}{tag}", is_bt))

    return ports


def get_selected_port_name():
    """Mendapatkan nama device asli dari combobox."""
    raw = port_var.get().strip() if port_var else ""
    if not raw or raw in ["Pilih Port", "Tidak ada port"]:
        return None
    if raw in port_map:
        return port_map[raw]
    return raw.split(" - ")[0].split()[0].strip()


def connect_serial():
    """Menginisialisasi atau memutuskan koneksi serial / Bluetooth."""
    global ser, rx_buffer

    if ser and getattr(ser, "is_open", False):
        try:
            ser.close()
        except Exception:
            pass
        ser = None
        rx_buffer = ""
        connect_button.config(text="Connect", state=tk.NORMAL)
        status_serial.set("Bluetooth: Disconnected")
        print("Koneksi Bluetooth ditutup.")
        return

    selected_port = get_selected_port_name()

    if not selected_port:
        if platform.system() == "Windows":
            status_serial.set("Pilih COM port Bluetooth ESP32 terlebih dahulu!")
            messagebox.showwarning(
                "Pilih Port",
                "Silakan pilih COM Port Bluetooth ESP32 terlebih dahulu.\n\n"
                "Langkah menghubungkan di Windows:\n"
                "1. Nyalakan ESP32.\n"
                "2. Buka Settings > Bluetooth di Windows, lalu 'Add device'.\n"
                "3. Klik 'Refresh' di aplikasi ini dan pilih COM Port Bluetooth (Outgoing).\n"
                "4. Klik 'Connect'."
            )
        else:
            status_serial.set("rfcomm belum ada. Jalankan:\nsudo rfcomm bind /dev/rfcomm0 <MAC_ESP32> 1")
        return

    connect_button.config(state=tk.DISABLED)
    status_serial.set(f"Bluetooth: Menghubungkan ke {selected_port}...")
    root.update_idletasks()

    def _do_connect():
        global ser, rx_buffer
        try:
            s = serial.Serial(selected_port, RFCOMM_BAUD, timeout=0.05)
            rx_buffer = ""
            ser = s
            root.after(0, lambda: _on_connect_success(selected_port))
        except Exception as e:
            root.after(0, lambda: _on_connect_fail(selected_port, str(e)))

    threading.Thread(target=_do_connect, daemon=True).start()


def _on_connect_success(selected_port):
    connect_button.config(text="Disconnect", state=tk.NORMAL)
    status_serial.set(f"Bluetooth: Connected to {selected_port}")
    print(f"Berhasil terhubung ke {selected_port}")


def _on_connect_fail(selected_port, err_msg):
    global ser
    ser = None
    connect_button.config(text="Connect", state=tk.NORMAL)
    hint = ""
    if platform.system() == "Windows":
        hint = " (Jika ada 2 port Bluetooth, coba gunakan port Outgoing)"
    status_serial.set(f"Bluetooth: FAILED!{hint}")
    print(f"Gagal terhubung ke {selected_port}: {err_msg}")


def refresh_ports():
    """Memperbarui daftar device Bluetooth/Serial."""
    global port_map
    port_map.clear()

    ports = get_available_ports()
    display_names = []
    default_selection = None

    for dev, display_label, is_bt in ports:
        port_map[display_label] = dev
        display_names.append(display_label)
        if is_bt and default_selection is None:
            default_selection = display_label

    port_combobox['values'] = display_names

    if display_names:
        if default_selection:
            port_var.set(default_selection)
            status_serial.set(f"Bluetooth: Ditemukan {port_map[default_selection]}. Siap.")
        else:
            port_var.set(display_names[0])
            status_serial.set(f"Port: Terdeteksi {port_map[display_names[0]]}. Siap.")
    else:
        port_var.set("Pilih Port")
        if platform.system() == "Windows":
            status_serial.set("Bluetooth/COM belum ada. Sambungkan/Pair ESP32 lalu klik Refresh.")
        else:
            status_serial.set("rfcomm belum ada.\nPastikan ESP32 aktif, lalu:\nsudo rfcomm bind /dev/rfcomm0 <MAC_ESP32> 1")


def open_bt_settings():
    """Membuka pengaturan Bluetooth Windows / sistem."""
    try:
        sys_name = platform.system()
        if sys_name == "Windows":
            os.startfile("ms-settings:bluetooth")
        elif sys_name == "Linux":
            os.system("blueman-manager &")
    except Exception as e:
        messagebox.showerror("Error", f"Gagal membuka Bluetooth Settings: {e}")


# --- Fungsi Reset Odometri & Peta ---
def send_reset_odom():
    """Mengirim perintah <RESET> ke ESP32 dan membersihkan peta lokal."""
    global ser, odom_x, odom_y, odom_theta, odom_vx, odom_vy, odom_w, odom_trail
    odom_x = 0.0
    odom_y = 0.0
    odom_theta = 0.0
    odom_vx = 0.0
    odom_vy = 0.0
    odom_w = 0.0
    odom_trail.clear()
    update_odom_gui()

    if ser and getattr(ser, "is_open", False):
        try:
            ser.write(b"<RESET>\n")
            print("Perintah <RESET> dikirim ke ESP32.")
        except Exception as e:
            print(f"Gagal mengirim <RESET>: {e}")


def clear_odom_trail():
    """Menghapus garis jejak pada mini-map tanpa me-reset posisi ESP32."""
    global odom_trail
    odom_trail.clear()
    update_odom_gui()


def parse_incoming_packets(raw_text):
    """Mem-parsing paket <ODOM,X,Y,Theta,Vx,Vy,W> yang masuk dari ESP32."""
    global rx_buffer, odom_x, odom_y, odom_theta, odom_vx, odom_vy, odom_w, odom_trail
    rx_buffer += raw_text

    updated = False
    while "<" in rx_buffer and ">" in rx_buffer:
        start_idx = rx_buffer.find("<")
        end_idx = rx_buffer.find(">", start_idx)
        if end_idx == -1:
            break

        packet = rx_buffer[start_idx + 1:end_idx].strip()
        rx_buffer = rx_buffer[end_idx + 1:]

        parts = packet.split(",")
        if len(parts) >= 4 and parts[0].upper() == "ODOM":
            try:
                odom_x = float(parts[1])
                odom_y = float(parts[2])
                odom_theta = float(parts[3]) * THETA_SCALE
                if len(parts) >= 7:
                    odom_vx = float(parts[4])
                    odom_vy = float(parts[5])
                    odom_w = float(parts[6]) * THETA_SCALE

                if not odom_trail or math.hypot(odom_x - odom_trail[-1][0], odom_y - odom_trail[-1][1]) > 0.5:
                    odom_trail.append((odom_x, odom_y))
                    if len(odom_trail) > 500:
                        odom_trail.pop(0)

                updated = True
            except ValueError:
                pass

    if len(rx_buffer) > 1024:
        rx_buffer = rx_buffer[-256:]

    if updated:
        update_odom_gui()


def update_odom_gui():
    """Memperbarui label angka X, Y, Theta dan menggambar posisi robot di kanvas 2D."""
    var_x.set(f"X     : {odom_x:+8.2f} cm")
    var_y.set(f"Y     : {odom_y:+8.2f} cm")
    var_theta.set(f"Theta : {odom_theta:+8.2f} deg")
    var_vel.set(f"Vel   : Vx={odom_vx:+.1f} | Vy={odom_vy:+.1f} cm/s | W={odom_w:+.2f} rad/s")

    if odom_canvas:
        odom_canvas.delete("all")
        cx, cy = 120, 120

        # Grid sumbu koordinat (+X maju ke atas, +Y kanan ke kanan)
        odom_canvas.create_line(0, cy, 240, cy, fill="#e0e0e0", dash=(3, 3))
        odom_canvas.create_line(cx, 0, cx, 240, fill="#e0e0e0", dash=(3, 3))
        odom_canvas.create_text(cx + 30, 10, text="+X (Maju)", fill="gray", font=("Consolas", 8))
        odom_canvas.create_text(205, cy - 10, text="+Y (Kanan)", fill="gray", font=("Consolas", 8))

        # Konversi koordinat robot (X=maju/atas, Y=kanan/kanan layar) ke piksel canvas
        def to_canvas(rx, ry):
            px = cx + (ry * MAP_SCALE)
            py = cy - (rx * MAP_SCALE)
            return px, py

        # Gambar garis jejak lintasan (trail)
        if len(odom_trail) >= 2:
            pts = []
            for tx, ty in odom_trail:
                px, py = to_canvas(tx, ty)
                pts.extend([px, py])
            odom_canvas.create_line(*pts, fill="#4da6ff", width=2)

        # Gambar posisi robot (titik biru)
        rx_px, ry_px = to_canvas(odom_x, odom_y)
        r_dot = 7
        odom_canvas.create_oval(rx_px - r_dot, ry_px - r_dot, rx_px + r_dot, ry_px + r_dot,
                                fill="#0066cc", outline="black", width=1.5)

        # Gambar panah arah hadap robot (Theta: + = putar kanan, - = putar kiri)
        rad = math.radians(odom_theta)
        head_x = odom_x + 18.0 * math.cos(rad)
        head_y = odom_y + 18.0 * math.sin(rad)
        hx_px, hy_px = to_canvas(head_x, head_y)
        odom_canvas.create_line(rx_px, ry_px, hx_px, hy_px, fill="red", width=2.5, arrow=tk.LAST)


# --- fungsi untuk update data joystick ---
def update_joystick():
    global connected, joystick, axis_labels, button_labels
    global left_stick_dot, right_stick_dot

    if pygame.joystick.get_count() > 0:
        if not connected:
            joystick = pygame.joystick.Joystick(0)
            joystick.init()
            connected = True
            status_var.set(f"Controller connected: {joystick.get_name()}")

            for lbl in axis_labels:
                lbl.destroy()
            axis_labels.clear()
            for i in range(joystick.get_numaxes()):
                lbl = tk.Label(axis_frame, text=f"Axis {i}: 0.000", width=15, anchor="w")
                lbl.pack(anchor="w")
                axis_labels.append(lbl)

            for lbl in button_labels:
                lbl.destroy()
            button_labels.clear()
            num_buttons = joystick.get_numbuttons()
            split_point = math.ceil(num_buttons / 2.0)
            for i in range(num_buttons):
                parent_frame = button_frame_row1 if i < split_point else button_frame_row2
                lbl = tk.Label(parent_frame, text=f"B{i}: 0", width=8, anchor="w")
                lbl.pack(side="left")
                button_labels.append(lbl)

            left_canvas.delete("all")
            right_canvas.delete("all")
            left_canvas.create_oval(10, 10, 90, 90, outline='grey', width=2)
            right_canvas.create_oval(10, 10, 90, 90, outline='grey', width=2)
            left_stick_dot = left_canvas.create_oval(45, 45, 55, 55, fill='blue', outline='blue')
            right_stick_dot = right_canvas.create_oval(45, 45, 55, 55, fill='blue', outline='blue')

    else:
        if connected:
            connected = False
            joystick = None
            status_var.set("Controller disconnected")
            for lbl in axis_labels:
                lbl.destroy()
            axis_labels.clear()
            for lbl in button_labels:
                lbl.destroy()
            button_labels.clear()
            if left_canvas:
                left_canvas.delete("all")
            if right_canvas:
                right_canvas.delete("all")
            left_stick_dot = None
            right_stick_dot = None


def read_input():
    global ser
    try:
        pygame.event.pump()

        # 1. BACA DATA ODOMETRI YANG MASUK DARI ESP32
        if ser and getattr(ser, "is_open", False):
            try:
                waiting = ser.in_waiting
                if waiting > 0:
                    raw_bytes = ser.read(waiting)
                    decoded = raw_bytes.decode("utf-8", errors="ignore")
                    parse_incoming_packets(decoded)
            except (serial.SerialException, OSError) as e:
                print(f"Koneksi terputus saat membaca: {e}")
                status_serial.set("Bluetooth: Lost connection!")
                try:
                    ser.close()
                except Exception:
                    pass
                ser = None
                connect_button.config(text="Connect", state=tk.NORMAL)

        # 2. BACA & KIRIM DATA JOYSTICK KE ESP32
        if connected and joystick:
            num_axes = joystick.get_numaxes()
            axes = [joystick.get_axis(i) for i in range(num_axes)]
            num_buttons = joystick.get_numbuttons()
            buttons = [joystick.get_button(i) for i in range(num_buttons)]

            for i, val in enumerate(axes):
                if i < len(axis_labels):
                    axis_labels[i].config(text=f"Axis {i}: {val:+.3f}")
            if num_axes >= 2 and left_stick_dot:
                x_l = 50 + (axes[0] * 40)
                y_l = 50 + (axes[1] * 40)
                left_canvas.coords(left_stick_dot, x_l - 5, y_l - 5, x_l + 5, y_l + 5)
            if num_axes >= 4 and right_stick_dot:
                x_r = 50 + (axes[2] * 40)
                y_r = 50 + (axes[3] * 40)
                right_canvas.coords(right_stick_dot, x_r - 5, y_r - 5, x_r + 5, y_r + 5)
            for i, val in enumerate(buttons):
                if i < len(button_labels):
                    button_labels[i].config(text=f"B{i}: {val}")

            val_x = int((axes[0] + 1.0) * 127.5) if len(axes) > 0 else 127
            val_y = int((axes[1] + 1.0) * 127.5) if len(axes) > 1 else 127

            # Menggunakan B4 (putar kiri) dan B5 (putar kanan)
            b4 = buttons[4] if len(buttons) > 4 else 0
            b5 = buttons[5] if len(buttons) > 5 else 0

            data_string = f"{val_x},{val_y},{b4},{b5}"
            final_packet = f"<{data_string}>\n"

            if ser and getattr(ser, "is_open", False):
                try:
                    ser.write(final_packet.encode('utf-8'))
                except (serial.SerialException, OSError) as e:
                    print(f"Koneksi terputus saat menulis: {e}")
                    status_serial.set("Bluetooth: Lost connection!")
                    try:
                        ser.close()
                    except Exception:
                        pass
                    ser = None
                    connect_button.config(text="Connect", state=tk.NORMAL)

    except pygame.error:
        pass
    except Exception as e:
        print(f"Error pada loop input: {e}")
    finally:
        root.after(50, read_input)


# --- GUI setup ---
root = tk.Tk()
root.title("Controller & Odometry Monitor - ESP32 Bluetooth Omni Control")

# 1. BLUETOOTH / SERIAL CONTROL FRAME
serial_control_frame = tk.LabelFrame(root, text="Koneksi Bluetooth / Serial ESP32", padx=10, pady=8)
serial_control_frame.pack(fill="x", padx=10, pady=5)

control_row1 = tk.Frame(serial_control_frame)
control_row1.pack(fill="x")

tk.Label(control_row1, text="PORT / BT:").pack(side="left", padx=(0, 5))
port_var = tk.StringVar(root, value="Pilih Port")
port_combobox = ttk.Combobox(control_row1, textvariable=port_var, width=35, state="normal")
port_combobox.pack(side="left", padx=(0, 8), fill="x", expand=True)

refresh_button = tk.Button(control_row1, text="Refresh", command=refresh_ports, padx=6)
refresh_button.pack(side="left", padx=3)

connect_button = tk.Button(control_row1, text="Connect", command=connect_serial, padx=8)
connect_button.pack(side="left", padx=3)

if platform.system() == "Windows":
    bt_settings_button = tk.Button(control_row1, text="⚙ BT Settings", command=open_bt_settings, padx=6)
    bt_settings_button.pack(side="left", padx=3)

control_row2 = tk.Frame(serial_control_frame)
control_row2.pack(fill="x", pady=(5, 0))

status_serial = tk.StringVar(root, value="Bluetooth: Ready")
status_serial_label = tk.Label(control_row2, textvariable=status_serial, fg="blue", anchor="w", justify="left")
status_serial_label.pack(side="left", fill="x")


# 2. STATUS JOYSTICK FRAME
status_var = tk.StringVar()
status_var.set("Waiting for controller...")
tk.Label(root, textvariable=status_var, font=("Consolas", 10)).pack(pady=3, fill="x")

# 3. MAIN CONTENT FRAME (JOYSTICK)
main_content_frame = tk.Frame(root)
main_content_frame.pack(fill="both", expand=True, padx=10, pady=5)

axis_frame = tk.Frame(main_content_frame, borderwidth=1, relief="sunken", padx=5, pady=5)
axis_frame.pack(side="left", fill="y", padx=5)
tk.Label(axis_frame, text="AXES", font=("Consolas", 10, "bold")).pack(anchor="w")

button_container_frame = tk.Frame(main_content_frame, borderwidth=1, relief="sunken", padx=5, pady=5)
button_container_frame.pack(side="left", fill="y", padx=5)
tk.Label(button_container_frame, text="BUTTONS (B4:Kiri, B5:Kanan)", font=("Consolas", 10, "bold")).pack(anchor="w")
button_frame_row1 = tk.Frame(button_container_frame)
button_frame_row1.pack(anchor="w")
button_frame_row2 = tk.Frame(button_container_frame)
button_frame_row2.pack(anchor="w")

viz_frame = tk.Frame(main_content_frame, borderwidth=1, relief="sunken", padx=5, pady=5)
viz_frame.pack(side="left", fill="both", expand=True, padx=5)
tk.Label(viz_frame, text="ANALOG STICKS", font=("Consolas", 10, "bold")).pack()
stick_canvas_frame = tk.Frame(viz_frame)
stick_canvas_frame.pack(pady=5)

left_stick_frame = tk.Frame(stick_canvas_frame)
left_stick_frame.pack(side="left", padx=10, anchor="n")
tk.Label(left_stick_frame, text="Left").pack()
left_canvas = tk.Canvas(left_stick_frame, width=100, height=100, bg='white')
left_canvas.pack()

right_stick_frame = tk.Frame(stick_canvas_frame)
right_stick_frame.pack(side="left", padx=10, anchor="n")
tk.Label(right_stick_frame, text="Right").pack()
right_canvas = tk.Canvas(right_stick_frame, width=100, height=100, bg='white')
right_canvas.pack()

# 4. ODOMETRY & MINI-MAP FRAME (DATA X, Y, THETA DARI ESP32)
odom_frame = tk.LabelFrame(root, text="Odometry & Telemetry (Data dari ESP32)", padx=10, pady=8)
odom_frame.pack(fill="both", expand=True, padx=10, pady=(5, 10))

odom_left_col = tk.Frame(odom_frame)
odom_left_col.pack(side="left", fill="both", expand=True, padx=(0, 10))

var_x = tk.StringVar(value="X     :    +0.00 cm")
var_y = tk.StringVar(value="Y     :    +0.00 cm")
var_theta = tk.StringVar(value="Theta :    +0.00 deg")
var_vel = tk.StringVar(value="Vel   : Vx=+0.0 | Vy=+0.0 cm/s | W=+0.00 rad/s")

tk.Label(odom_left_col, textvariable=var_x, font=("Consolas", 13, "bold"), fg="#004d99", anchor="w").pack(fill="x", pady=2)
tk.Label(odom_left_col, textvariable=var_y, font=("Consolas", 13, "bold"), fg="#006633", anchor="w").pack(fill="x", pady=2)
tk.Label(odom_left_col, textvariable=var_theta, font=("Consolas", 13, "bold"), fg="#993300", anchor="w").pack(fill="x", pady=2)
tk.Label(odom_left_col, textvariable=var_vel, font=("Consolas", 9), fg="#333333", anchor="w").pack(fill="x", pady=(6, 10))

odom_btn_row = tk.Frame(odom_left_col)
odom_btn_row.pack(anchor="w", pady=5)
tk.Button(odom_btn_row, text="Reset Odom (<RESET>)", command=send_reset_odom, bg="#ffe6e6", padx=8, pady=3).pack(side="left", padx=(0, 8))
tk.Button(odom_btn_row, text="Clear Trail", command=clear_odom_trail, padx=8, pady=3).pack(side="left")

odom_right_col = tk.Frame(odom_frame)
odom_right_col.pack(side="right")
tk.Label(odom_right_col, text="Peta Posisi Robot (1 px = 1 cm)", font=("Consolas", 9, "bold")).pack()
odom_canvas = tk.Canvas(odom_right_col, width=240, height=240, bg="white", borderwidth=1, relief="sunken")
odom_canvas.pack()


# --- Loop untuk cek koneksi joystick tiap 2 detik ---
def check_connection():
    try:
        update_joystick()
    finally:
        root.after(2000, check_connection)


# --- Cleanup saat jendela ditutup ---
def on_closing():
    global ser
    print("Menutup aplikasi...")
    if ser and getattr(ser, "is_open", False):
        try:
            ser.close()
            print("Port serial ditutup.")
        except Exception:
            pass
    try:
        pygame.quit()
    except Exception:
        pass
    root.destroy()


root.protocol("WM_DELETE_WINDOW", on_closing)

# --- Mulai Loop Aplikasi ---
if __name__ == "__main__":
    update_odom_gui()
    refresh_ports()
    check_connection()
    read_input()
    root.mainloop()
