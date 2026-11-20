#include <Arduino.h>
#include <math.h>
#include "BluetoothSerial.h"
#include <ESP32Encoder.h>

// ==============================
// BLUETOOTH (SPP)
// ==============================
BluetoothSerial SerialBT;

// ==============================
// PIN DEFINITION - MOTOR
// ==============================
#define M2_PWM_R 4    // Depan      Motor 2
#define M2_PWM_L 16

#define M1_PWM_R 15   // Kanan      Motor 1
#define M1_PWM_L 2

#define M4_PWM_R 17   // Kiri       Motor 4
#define M4_PWM_L 5

#define M3_PWM_R 18   // Belakang   Motor 3
#define M3_PWM_L 19

// ==============================
// PIN DEFINITION - 4 ENCODER YT06-OP
// (Deretan sisi 5V, tidak bentrok dengan pin motor)
// ==============================
#define ENC1_A 27     // Encoder 1 (Roda Kanan)
#define ENC1_B 14

#define ENC2_A 25     // Encoder 2 (Roda Depan)
#define ENC2_B 26

#define ENC3_A 32     // Encoder 3 (Roda Kiri)
#define ENC3_B 33

#define ENC4_A 34     // Encoder 4 (Roda Belakang)
#define ENC4_B 35

// ==============================
// PARAMETER FISIK RODA & ENCODER (COUPLED 48mm -> 150mm)
// ==============================
const double ENCODER_PPR      = 600.0;  // Sesuai label YT06-OP Anda
const double COUNTS_PER_REV   = ENCODER_PPR * 4.0;

// Roda encoder 48mm menempel pada permukaan luar roda omni 150mm,
// sehingga jarak tempuh linear permukaannya sama dengan keliling roda 48mm (4.8 cm).
const double ENC_WHEEL_DIAM   = 4.8;    // Diameter roda encoder = 48 mm = 4.8 cm
const double ROBOT_RADIUS_R   = 7.6;    // Jarak pusat robot ke titik kontak roda omni 150mm (cm)
const double CM_PER_COUNT     = (M_PI * ENC_WHEEL_DIAM) / COUNTS_PER_REV;

// Kalibrasi arah encoder [0:Kanan, 1:Depan, 2:Kiri, 3:Belakang]
// Default -1.0 karena roda 48mm bersinggungan dari luar (berputar berlawanan arah roda utama).
double ENC_DIR[4] = {-1.0, -1.0, -1.0, -1.0};

ESP32Encoder encoder[4];
long lastEncCount[4] = {0, 0, 0, 0};

// ==============================
// DATA ODOMETRI & TELEMETRY
// ==============================
double posX     = 0.0; // Posisi global X maju/mundur (cm)
double posY     = 0.0; // Posisi global Y kiri/kanan (cm)
double posTheta = 0.0; // Orientasi sudut global (radian)

double velX     = 0.0; // Kecepatan lokal maju/mundur (cm/s)
double velY     = 0.0; // Kecepatan lokal geser kiri/kanan (cm/s)
double velW     = 0.0; // Kecepatan sudut rotasi (rad/s)

unsigned long lastOdomTime = 0;
const unsigned long ODOM_INTERVAL_MS = 50; // Kirim data odometri tiap 50ms (20 Hz)

// ==============================
// KONSTANTA KENDALI MOTOR & KINEMATIKA
// ==============================
const int maxPWM = 255;
const double TRANSLATE_SCALE = 0.2;

const double COS45 = 0.7071067811865476;
int ROT_DIR = -1;
double SIN45 = 0.7071067811865476 * ROT_DIR;

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
// ==============================
void Inverse_Kinematics(double Vx, double Vy, double W) {
    double R = ROBOT_RADIUS_R;

    double M1 =  Vy + R * W;   // depan    -> merespon strafe (Vy)
    double M2 =  Vx + R * W;   // kanan    -> merespon maju/mundur (Vx)
    double M3 = -Vx + R * W;   // kiri     -> merespon maju/mundur (Vx)
    double M4 = -Vy + R * W;   // belakang -> merespon strafe (Vy)

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

    setMotor(1, (int)M1);
    setMotor(2, (int)M2);
    setMotor(3, (int)M3);
    setMotor(4, (int)M4);
}

// ==============================
// FORWARD KINEMATICS (ODOMETRI DARI 4 ENCODER)
// d[0]=Kanan, d[1]=Depan, d[2]=Kiri, d[3]=Belakang
// ==============================
void updateOdometry(double dt_sec) {
    long currCount[4];
    double d[4]; // Perpindahan linear tiap roda (cm)

    for (int i = 0; i < 4; i++) {
        currCount[i] = encoder[i].getCount();
        long deltaCount = currCount[i] - lastEncCount[i];
        lastEncCount[i] = currCount[i];
        d[i] = deltaCount * CM_PER_COUNT * ENC_DIR[i];
    }

    // 1. Perpindahan pada kerangka Diamond asli (sebelum rotasi 45 deg)
    double dx_diamond = (d[0] - d[2]) / 2.0; // Roda Kanan & Kiri
    double dy_diamond = (d[1] - d[3]) / 2.0; // Roda Depan & Belakang
    double dTheta     = (d[0] + d[1] + d[2] + d[3]) / (4.0 * ROBOT_RADIUS_R);

    // 2. Proyeksi ke sumbu maju baru robot (rotasi balik -45 deg: di antara Roda Depan & Kanan)
    double sin45_val = 0.7071067811865476 * ROT_DIR;
    double dx_robot  = dx_diamond * COS45 + dy_diamond * sin45_val;
    double dy_robot  = dx_diamond * sin45_val - dy_diamond * COS45;

    // 3. Hitung kecepatan aktual robot (cm/s dan rad/s)
    if (dt_sec > 0.0) {
        velX = dx_robot / dt_sec;
        velY = dy_robot / dt_sec;
        velW = dTheta / dt_sec;
    }

    // 4. Integrasi ke posisi global lapangan (X, Y, Theta)
    double midTheta = posTheta + (dTheta / 2.0);
    posX += dx_robot * cos(midTheta) - dy_robot * sin(midTheta);
    posY += dx_robot * sin(midTheta) + dy_robot * cos(midTheta);
    posTheta += dTheta;
}

void resetOdometry() {
    for (int i = 0; i < 4; i++) {
        encoder[i].clearCount();
        lastEncCount[i] = 0;
    }
    posX = 0.0;
    posY = 0.0;
    posTheta = 0.0;
    velX = 0.0;
    velY = 0.0;
    velW = 0.0;
    Serial.println("[ODOM] Posisi & kecepatan di-reset ke 0.");
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

    // Perintah reset dari tombol "Reset Odom (<RESET>)" di GUI Python
    if (packet.equalsIgnoreCase("RESET")) {
        resetOdometry();
        return;
    }

    int c1 = packet.indexOf(',');
    int c2 = packet.indexOf(',', c1 + 1);
    int c3 = packet.indexOf(',', c2 + 1);

    if (c1 < 1 || c2 < 1 || c3 < 1) {
        Serial.println("[WARN] Format tidak valid, skip.");
        stopAll();
        return;
    }

    int rawX = packet.substring(0, c1).toInt();
    int rawY = packet.substring(c1 + 1, c2).toInt();
    int b4   = packet.substring(c2 + 1, c3).toInt(); // Putar kiri
    int b5   = packet.substring(c3 + 1).toInt();     // Putar kanan

    // Mapping 0..255 -> -127..128, scale x2 agar PWM cukup untuk TB6612
    // Tanda minus pada Vy membalik arah analog kanan-kiri agar sesuai gerak fisik
    double Vy = -(double)(rawX - 127) * 2.0;
    double Vx =  (double)(rawY - 127) * 2.0;

    // ROTASI 45°: arah maju berada di antara Roda Depan dan Roda Kanan
    SIN45 = 0.7071067811865476 * ROT_DIR;
    double Vx_rot = Vx * COS45 - Vy * SIN45;
    double Vy_rot = Vx * SIN45 + Vy * COS45;
    Vx = Vx_rot;
    Vy = Vy_rot;

    // Deadband
    if (fabs(Vx) < 20) Vx = 0;
    if (fabs(Vy) < 20) Vy = 0;

    // Rotasi: B4 = putar kiri (-5.0), B5 = putar kanan (+5.0)
    double W = 0;
    if (b4 == 1) W = -5.0; // Putar Kiri
    if (b5 == 1) W =  5.0; // Putar Kanan

    // Translasi
    Vx *= TRANSLATE_SCALE;
    Vy *= TRANSLATE_SCALE;

    Inverse_Kinematics(Vx, Vy, W);
}

// ==============================
// SETUP
// ==============================
void setup() {
    Serial.begin(115200);
    SerialBT.begin("OMNI-ESP32");

    // Setup Pin Motor
    pinMode(M1_PWM_R, OUTPUT); pinMode(M1_PWM_L, OUTPUT);
    pinMode(M2_PWM_R, OUTPUT); pinMode(M2_PWM_L, OUTPUT);
    pinMode(M3_PWM_R, OUTPUT); pinMode(M3_PWM_L, OUTPUT);
    pinMode(M4_PWM_R, OUTPUT); pinMode(M4_PWM_L, OUTPUT);
    stopAll();

    // Setup 4 Hardware PCNT Encoder
    ESP32Encoder::useInternalWeakPullResistors = puType::none;
    encoder[0].attachFullQuad(ENC1_A, ENC1_B); // Kanan (A:27, B:14)
    encoder[1].attachFullQuad(ENC2_A, ENC2_B); // Depan (A:25, B:26)
    encoder[2].attachFullQuad(ENC3_A, ENC3_B); // Kiri  (A:32, B:33)
    encoder[3].attachFullQuad(ENC4_A, ENC4_B); // Blkng (A:34, B:35)
    resetOdometry();

    lastOdomTime = millis();
    Serial.println("ESP32 Omni + Odometry Ready (B4: Putar Kiri, B5: Putar Kanan).");
    Serial.println("Bluetooth SPP aktif, nama device: OMNI-ESP32");
}

// ==============================
// LOOP — parser char-by-char & telemetry odometri
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
    // 1. Baca paket perintah kendali dari Bluetooth (utama) & USB (cadangan)
    parserBT.read(SerialBT);
    parserUSB.read(Serial);

    // 2. Hitung odometri & kirim data <ODOM,...> ke GUI Python setiap 50ms (20 Hz)
    unsigned long now = millis();
    if (now - lastOdomTime >= ODOM_INTERVAL_MS) {
        double dt_sec = (now - lastOdomTime) / 1000.0;
        lastOdomTime = now;

        updateOdometry(dt_sec);

        double thetaDeg = posTheta * 180.0 / M_PI;

        // Format wajib sesuai parser Python:
        // <ODOM,X(cm),Y(cm),Theta(deg),Vx(cm/s),Vy(cm/s),W(rad/s)>
        char odomMsg[128];
        snprintf(odomMsg, sizeof(odomMsg), "<ODOM,%.2f,%.2f,%.2f,%.2f,%.2f,%.3f>\n",
                 posX, posY, thetaDeg, velX, velY, velW);

        if (SerialBT.hasClient()) {
            SerialBT.print(odomMsg);
        }
    }
}
