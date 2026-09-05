import tkinter as tk
from tkinter import ttk  # Digunakan untuk Combobox
import pygame
import math
import serial
import serial.tools.list_ports # <-- Diperlukan untuk memindai port
import time

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

# --- Variabel Bluetooth (SPP via /dev/rfcomm0) ---
ser = None
# Variabel yang akan dihubungkan ke GUI (StringVar/IntVar)
port_var = None

# Baud tidak berpengaruh pada koneksi Bluetooth; hanya argumen pyserial.
RFCOMM_BAUD = 115200

def get_available_ports():
    """Mengambil daftar device Bluetooth SPP (/dev/rfcomm*)."""
    import glob
    devices = []
    # /dev/rfcomm0 dibuat setelah RPi di-bind:
    #   sudo rfcomm bind rfcomm0 <MAC_ESP32> 1
    for dev in glob.glob('/dev/rfcomm*'):
        if dev not in devices:
            devices.append(dev)
    # Tambahan dari pyserial (bila rfcomm ikut terdeteksi di sana)
    for p in serial.tools.list_ports.comports():
        if 'rfcomm' in p.device and p.device not in devices:
            devices.append(p.device)
    return devices


def connect_serial():
    """Menginisialisasi atau memutuskan koneksi serial."""
    global ser

    if ser and ser.is_open:
        # Jika sudah terhubung, lakukan Disconnect
        try:
            ser.close()
            connect_button.config(text="Connect", state=tk.NORMAL)
            status_serial.set("Bluetooth: Disconnected")
            print("Koneksi Bluetooth ditutup.")
        except Exception as e:
            status_serial.set(f"Bluetooth: Error Disconnect ({e})")
    else:
        # Jika belum terhubung, lakukan Connect
        selected_port = port_var.get()

        if not selected_port or selected_port == "Pilih Port":
            status_serial.set("Bluetooth: rfcomm belum ada. Jalankan:\nsudo rfcomm bind /dev/rfcomm0 <MAC_ESP32> 1")
            return

        connect_button.config(state=tk.DISABLED) # Nonaktifkan tombol saat mencoba
        status_serial.set(f"Bluetooth: Connecting to {selected_port}...")
        root.update_idletasks()

        try:
            ser = serial.Serial(selected_port, RFCOMM_BAUD, timeout=1)
            connect_button.config(text="Disconnect", state=tk.NORMAL)
            status_serial.set(f"Bluetooth: Connected to {selected_port}")
            print(f"Berhasil terhubung ke {selected_port}")
        except serial.SerialException as e:
            connect_button.config(text="Connect", state=tk.NORMAL)
            status_serial.set(f"Bluetooth: FAILED! ({e})")
            ser = None # Pastikan ser kembali None jika gagal
            print(f"Gagal terhubung ke {selected_port}: {e}")

def refresh_ports():
    """Memperbarui daftar device Bluetooth SPP (/dev/rfcomm*)."""
    ports = get_available_ports()
    port_combobox['values'] = ports

    if ports:
        # Pilih device pertama sebagai default jika ada
        port_var.set(ports[0])
        status_serial.set(f"Bluetooth: Found {ports[0]}. Ready.")
    else:
        port_var.set("Pilih Port")
        status_serial.set("Bluetooth: rfcomm belum ada.\nPastikan ESP32 aktif, lalu:\nsudo rfcomm bind /dev/rfcomm0 <MAC_ESP32> 1")

# --- fungsi untuk update data joystick ---
# ... (Fungsi update_joystick TIDAK BERUBAH dari sebelumnya) ...
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
    pygame.event.pump()

    if connected and joystick:
        try:
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
                x_l = 50 + (axes[0] * 40); y_l = 50 + (axes[1] * 40)
                left_canvas.coords(left_stick_dot, x_l-5, y_l-5, x_l+5, y_l+5)
            if num_axes >= 4 and right_stick_dot:
                x_r = 50 + (axes[2] * 40); y_r = 50 + (axes[3] * 40)
                right_canvas.coords(right_stick_dot, x_r-5, y_r-5, x_r+5, y_r+5)
            for i, val in enumerate(buttons):
                 if i < len(button_labels):
                    button_labels[i].config(text=f"B{i}: {val}")

            # --- KIRIM SERIAL ---
            # Petakan axis (-1.0 -> 1.0) ke (0 -> 255)
            # Left Stick is usually axes[0] (X) and axes[1] (Y)
            val_x = int((axes[0] + 1.0) * 127.5)
            val_y = int((axes[1] + 1.0) * 127.5)

            # Pastikan tombol ada sebelum mengakses indeks
            b6 = buttons[6] if len(buttons) > 6 else 0
            b7 = buttons[7] if len(buttons) > 7 else 0

            data_string = f"{val_x},{val_y},{b6},{b7}"
            final_packet = f"<{data_string}>\n"  # <-- tambahkan \n di akhir


            # print ke terminal untuk debug
            print(final_packet)

            if ser and ser.is_open:
                try:
                    ser.write(final_packet.encode('utf-8'))
                except serial.SerialException:
                    status_serial.set("Bluetooth: Lost connection!")
                    connect_serial() # Coba disconnect

        except pygame.error:
            pass

    root.after(50, read_input)


# --- GUI setup ---
root = tk.Tk()
root.title("Controller Monitor (Bluetooth Control)")

# 1. BLUETOOTH CONTROL FRAME
serial_control_frame = tk.Frame(root)
serial_control_frame.pack(fill="x", padx=10, pady=5)

# Label & Combobox BT DEVICE
tk.Label(serial_control_frame, text="BT DEVICE:").pack(side="left", padx=(0, 5))
port_var = tk.StringVar(root, value="Pilih Port")
port_combobox = ttk.Combobox(serial_control_frame, textvariable=port_var, width=18, state="readonly")
port_combobox.pack(side="left", padx=(0, 15))

# Tombol Refresh
refresh_button = tk.Button(serial_control_frame, text="Refresh", command=refresh_ports)
refresh_button.pack(side="left", padx=5)

# Tombol Connect/Disconnect
connect_button = tk.Button(serial_control_frame, text="Connect", command=connect_serial)
connect_button.pack(side="left", padx=5)

# Status Bluetooth
status_serial = tk.StringVar(root, value="Bluetooth: Ready")
tk.Label(serial_control_frame, textvariable=status_serial, fg="blue").pack(side="left", padx=(15, 0))


# 2. STATUS JOYSTICK FRAME
status_var = tk.StringVar()
status_var.set("Waiting for controller...")
tk.Label(root, textvariable=status_var, font=("Consolas", 10)).pack(pady=5, fill="x")

# 3. MAIN CONTENT FRAME (Sama seperti sebelumnya)
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


# --- loop untuk cek koneksi tiap 2 detik ---
def check_connection():
    update_joystick()
    root.after(2000, check_connection)

# --- Mulai Loop ---
refresh_ports() # Pindai port saat aplikasi dimulai
check_connection()
read_input()

root.mainloop()

# --- Cleanup ---
print("Menutup aplikasi...")
if ser and ser.is_open:
    ser.close()
    print("Port serial ditutup.")
pygame.quit()
