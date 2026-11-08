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
port_map = {}  # Pemetaan label display -> nama port fisik (misal: "COM4 - Bluetooth..." -> "COM4")

# Baud rate serial (standar ESP32)
RFCOMM_BAUD = 115200


def get_available_ports():
    """
    Mengambil daftar port serial dan Bluetooth yang tersedia.
    Mendukung Windows (COM port Bluetooth SPP & USB) dan Linux (/dev/rfcomm*, /dev/ttyUSB*).
    """
    ports = []  # list of tuples: (device_name, display_label, is_bluetooth)
    system = platform.system()

    if system == "Windows":
        for p in serial.tools.list_ports.comports():
            desc = p.description or ""
            hwid = p.hwid or ""

            # Deteksi apakah port merupakan Bluetooth SPP (Serial Port Profile)
            is_bt = (
                "bluetooth" in desc.lower()
                or "bthenum" in hwid.lower()
                or "bth" in hwid.lower()
                or "{00001101" in hwid.lower()
            )
            tag = " [Bluetooth]" if is_bt else ""
            display_label = f"{p.device} - {desc}{tag}"
            ports.append((p.device, display_label, is_bt))

        # Urutkan: port Bluetooth di atas, lalu urutkan berdasarkan nama port
        ports.sort(key=lambda x: (not x[2], x[0]))

    else:
        # Linux / Raspberry Pi / macOS
        # 1. Cek device RFCOMM Bluetooth (/dev/rfcomm*)
        for dev in glob.glob('/dev/rfcomm*'):
            ports.append((dev, f"{dev} [Bluetooth RFCOMM]", True))

        # 2. Port serial lainnya (/dev/ttyUSB*, /dev/ttyACM*, dll)
        for p in serial.tools.list_ports.comports():
            if not any(p.device == item[0] for item in ports):
                desc = p.description or ""
                is_bt = "rfcomm" in p.device.lower() or "bluetooth" in desc.lower()
                tag = " [Bluetooth]" if is_bt else ""
                ports.append((p.device, f"{p.device} - {desc}{tag}", is_bt))

    return ports


def get_selected_port_name():
    """Mendapatkan nama device asli dari combobox (misal 'COM4' dari string display)."""
    raw = port_var.get().strip() if port_var else ""
    if not raw or raw in ["Pilih Port", "Tidak ada port"]:
        return None
    if raw in port_map:
        return port_map[raw]
    # Jika user mengetik nama port manual
    return raw.split(" - ")[0].split()[0].strip()


def connect_serial():
    """Menginisialisasi atau memutuskan koneksi serial / Bluetooth."""
    global ser

    if ser and getattr(ser, "is_open", False):
        # Jika sudah terhubung, lakukan Disconnect
        try:
            ser.close()
        except Exception:
            pass
        ser = None
        connect_button.config(text="Connect", state=tk.NORMAL)
        status_serial.set("Bluetooth: Disconnected")
        print("Koneksi Bluetooth ditutup.")
        return

    # Jika belum terhubung, lakukan Connect
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

    # Jalankan koneksi di background thread agar UI tidak 'Not Responding' saat menunggu handshake
    def _do_connect():
        global ser
        try:
            s = serial.Serial(selected_port, RFCOMM_BAUD, timeout=1)
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

            # 1. AXIS
            for lbl in axis_labels:
                lbl.destroy()
            axis_labels.clear()
            for i in range(joystick.get_numaxes()):
                lbl = tk.Label(axis_frame, text=f"Axis {i}: 0.000", width=15, anchor="w")
                lbl.pack(anchor="w")
                axis_labels.append(lbl)

            # 2. BUTTONS
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

            # 3. VISUALISASI
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

        if connected and joystick:
            # === BACA DATA JOYSTICK ===
            num_axes = joystick.get_numaxes()
            axes = [joystick.get_axis(i) for i in range(num_axes)]
            num_buttons = joystick.get_numbuttons()
            buttons = [joystick.get_button(i) for i in range(num_buttons)]

            # === UPDATE GUI ===
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

            # --- KIRIM SERIAL ---
            # Petakan axis (-1.0 -> 1.0) ke (0 -> 255)
            val_x = int((axes[0] + 1.0) * 127.5) if len(axes) > 0 else 127
            val_y = int((axes[1] + 1.0) * 127.5) if len(axes) > 1 else 127

            # Pastikan tombol ada sebelum mengakses indeks
            b6 = buttons[6] if len(buttons) > 6 else 0
            b7 = buttons[7] if len(buttons) > 7 else 0

            data_string = f"{val_x},{val_y},{b6},{b7}"
            final_packet = f"<{data_string}>\n"

            # Print ke terminal untuk debug
            print(final_packet.strip())

            # Kirim data ke ESP32 jika port terhubung
            if ser and getattr(ser, "is_open", False):
                try:
                    ser.write(final_packet.encode('utf-8'))
                except (serial.SerialException, OSError) as e:
                    print(f"Koneksi terputus: {e}")
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
root.title("Controller Monitor - ESP32 Bluetooth Omni Control")

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
tk.Label(root, textvariable=status_var, font=("Consolas", 10)).pack(pady=5, fill="x")

# 3. MAIN CONTENT FRAME
main_content_frame = tk.Frame(root)
main_content_frame.pack(fill="both", expand=True, padx=10, pady=10)

# AXIS FRAME
axis_frame = tk.Frame(main_content_frame, borderwidth=1, relief="sunken")
axis_frame.pack(side="left", fill="y", padx=5)
tk.Label(axis_frame, text="AXES", font=("Consolas", 10, "bold")).pack(anchor="w")

# BUTTON CONTAINER FRAME
button_container_frame = tk.Frame(main_content_frame, borderwidth=1, relief="sunken")
button_container_frame.pack(side="left", fill="y", padx=5)
tk.Label(button_container_frame, text="BUTTONS", font=("Consolas", 10, "bold")).pack(anchor="w")
button_frame_row1 = tk.Frame(button_container_frame)
button_frame_row1.pack(anchor="w")
button_frame_row2 = tk.Frame(button_container_frame)
button_frame_row2.pack(anchor="w")

# VISUALIZATION FRAME
viz_frame = tk.Frame(main_content_frame, borderwidth=1, relief="sunken")
viz_frame.pack(side="left", fill="both", expand=True, padx=5)
tk.Label(viz_frame, text="ANALOG STICKS", font=("Consolas", 10, "bold")).pack()
stick_canvas_frame = tk.Frame(viz_frame)
stick_canvas_frame.pack(pady=10)

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
    refresh_ports()
    check_connection()
    read_input()
    root.mainloop()
