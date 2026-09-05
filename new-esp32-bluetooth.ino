#include <Arduino.h>
#include <math.h>
#include "BluetoothSerial.h"

// ==============================
// BLUETOOTH (SPP)
// ESP32 menjadi Bluetooth slave (Classic SPP).
// RPi terhubung ke device ini lalu bind ke /dev/rfcomm0.
// ==============================
BluetoothSerial SerialBT;

// ==============================
// PIN DEFINITION
// ==============================
#define M2_PWM_R 4   // Depan       Motor 2
#define M2_PWM_L 16

#define M1_PWM_R 15  // Kanan       Motor 1
#define M1_PWM_L 2

#define M4_PWM_R 17    // Kiri      BENAR MOTOR 4
#define M4_PWM_L 5

#define M3_PWM_R 18   // Belakang   MOTOR 3
#define M3_PWM_L 19

const int maxPWM = 255;

// Skala kecepatan global. 0.40 => kecepatan 40% dari semula
// (berlaku untuk translasi Vx/Vy DAN rotasi W).
const double SPEED_SCALE = 0.40;

// ==============================
// KALIBRASI PER MOTOR
// Isi manual dari hasil test satu-satu (lihat penjelasan di bawah).
// 1.0 = tidak dikurangi. Naikkan skala motor yang lebih lemah.
// ==============================
double CAL1 = 1.00; // Depan
double CAL2 = 1.00; // Kanan
double CAL3 = 1.00; // Kiri
double CAL4 = 1.00; // Belakang

// ==============================
// MOTOR CONTROL
// ==============================
void stopAll() {
    analogWrite(M1_PWM_R, 0); analogWrite(M1_PWM_L, 0);
    analogWrite(M2_PWM_R, 0); analogWrite(M2_PWM_L, 0);
    analogWrite(M3_PWM_R, 0); analogWrite(M3_PWM_L, 0);
    analogWrite(M4_PWM_R, 0); analogWrite(M4_PWM_L, 0);
}

void setMotor(int motor, int speed) {
    int pwmR = (speed > 0) ? speed : 0;
    int pwmL = (speed < 0) ? -speed : 0;
    if (pwmR > maxPWM) pwmR = maxPWM;
    if (pwmL > maxPWM) pwmL = maxPWM;
    switch (motor) {
        case 1: analogWrite(M1_PWM_R, pwmR); analogWrite(M1_PWM_L, pwmL); break;
        case 2: analogWrite(M2_PWM_R, pwmR); analogWrite(M2_PWM_L, pwmL); break;
        case 3: analogWrite(M3_PWM_R, pwmR); analogWrite(M3_PWM_L, pwmL); break;
        case 4: analogWrite(M4_PWM_R, pwmR); analogWrite(M4_PWM_L, pwmL); break;
    }
}

// ==============================
// INVERSE KINEMATICS - LAYOUT DIAMOND
//         1 (depan)
// 3(kiri)        2(kanan)
//         4 (belakang)
//
// v_i = -sin(phi_i)*Vx + cos(phi_i)*Vy + R*W
// phi: 1(depan)=0 deg, 2(kanan)=270 deg, 3(kiri)=90 deg, 4(belakang)=180 deg
//
// Hasil: M1 & M4 merespon Vy (kanan-kiri)
//        M2 & M3 merespon Vx (maju-mundur)
// ==============================
void Inverse_Kinematics(double Vx, double Vy, double W) {
    double R = 7.6;

    double M1 =  Vy + R * W;   // depan    -> merespon strafe (Vy) = kanan-kiri
    double M2 =  Vx + R * W;   // kanan    -> merespon maju/mundur (Vx)
    double M3 = -Vx + R * W;   // kiri     -> merespon maju/mundur (Vx)
    double M4 = -Vy + R * W;   // belakang -> merespon strafe (Vy) = kanan-kiri

    // Kalibrasi per motor (kompensasi motor lemah)
    M1 *= CAL1;
    M2 *= CAL2;
    M3 *= CAL3;
    M4 *= CAL4;

    double maxVal = max(fabs(M1), max(fabs(M2), max(fabs(M3), fabs(M4))));
    if (maxVal > maxPWM) {
        M1 = M1 / maxVal * maxPWM;
        M2 = M2 / maxVal * maxPWM;
        M3 = M3 / maxVal * maxPWM;
        M4 = M4 / maxVal * maxPWM;
    }

    Serial.printf("[IK] Vx:%.1f Vy:%.1f W:%.1f | M1:%.0f M2:%.0f M3:%.0f M4:%.0f\n",
                  Vx, Vy, W, M1, M2, M3, M4);

    setMotor(1, (int)M1);
    setMotor(2, (int)M2);
    setMotor(3, (int)M3);
    setMotor(4, (int)M4);
}

// ==============================
// HELPER: hapus semua spasi
// ==============================
String removeSpaces(String s) {
    String result = "";
    for (int i = 0; i < s.length(); i++) {
        char c = s[i];
        if (c != ' ' && c != '\t' && c != '\r' && c != '\n') {
            result += c;
        }
    }
    return result;
}

// ==============================
// PROCESS PACKET
// ==============================
void processPacket(String packet) {
    packet = removeSpaces(packet);
    Serial.printf("[RAW] \"%s\"\n", packet.c_str());

    int c1 = packet.indexOf(',');
    int c2 = packet.indexOf(',', c1 + 1);
    int c3 = packet.indexOf(',', c2 + 1);

    if (c1 < 1 || c2 < 1 || c3 < 1) {
        Serial.println("[WARN] Format tidak valid, skip.");
        stopAll();
        return;
    }

    String sX  = packet.substring(0, c1);
    String sY  = packet.substring(c1 + 1, c2);
    String sB6 = packet.substring(c2 + 1, c3);
    String sB7 = packet.substring(c3 + 1);

    Serial.printf("[PARSED] X:[%s] Y:[%s] B6:[%s] B7:[%s]\n",
                  sX.c_str(), sY.c_str(), sB6.c_str(), sB7.c_str());

    int rawX = sX.toInt();
    int rawY = sY.toInt();
    int b6   = sB6.toInt();
    int b7   = sB7.toInt();

    // Mapping 0..255 -> -127..128, scale x2 agar PWM cukup untuk TB6612
    double Vy = (double)(rawX - 127) * 2.0;
    double Vx = (double)(rawY - 127) * 2.0;

    // Deadband
    if (fabs(Vx) < 20) Vx = 0;
    if (fabs(Vy) < 20) Vy = 0;

    // Rotasi
    double W = 0;
    if (b6 == 1) W = -5.0;
    if (b7 == 1) W =  5.0;

    // Turunkan kecepatan ke 40% (translasi & rotasi)
    Vx *= SPEED_SCALE;
    Vy *= SPEED_SCALE;
    W  *= SPEED_SCALE;

    Inverse_Kinematics(Vx, Vy, W);
}

// ==============================
// SETUP
// ==============================
void setup() {
    Serial.begin(115200);
    SerialBT.begin("OMNI-ESP32");

    pinMode(M1_PWM_R, OUTPUT); pinMode(M1_PWM_L, OUTPUT);
    pinMode(M2_PWM_R, OUTPUT); pinMode(M2_PWM_L, OUTPUT);
    pinMode(M3_PWM_R, OUTPUT); pinMode(M3_PWM_L, OUTPUT);
    pinMode(M4_PWM_R, OUTPUT); pinMode(M4_PWM_L, OUTPUT);

    stopAll();
    Serial.println("ESP32 Omni Diamond Ready. Layout: 1=depan,2=kanan,3=kiri,4=belakang");
    Serial.println("Bluetooth SPP aktif, cari perangkat: OMNI-ESP32");
}

// ==============================
// LOOP — parser char-by-char per stream
// Data kendali utama datang dari SerialBT (Bluetooth).
// USB Serial tetap dibaca & dipakai untuk log debug.
// ==============================
struct PacketParser {
    bool inPacket = false;
    String inputString = "";

    void read(Stream &s) {
        while (s.available()) {
            char c = (char)s.read();

            if (c == '<') {
                inPacket = true;
                inputString = "";
            } else if (c == '>') {
                if (inPacket && inputString.length() > 0) {
                    processPacket(inputString);
                }
                inPacket = false;
                inputString = "";
            } else {
                if (inPacket) {
                    inputString += c;
                }
            }
        }
    }
};

PacketParser parserUSB;
PacketParser parserBT;

void loop() {
    parserBT.read(SerialBT);   // jalur utama: Bluetooth
    parserUSB.read(Serial);    // cadangan/tes via USB serial monitor
}
