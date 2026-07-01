#include <Arduino.h>
#include <math.h>

#define M4_PWM_R 15
#define M4_PWM_L 2

#define M1_PWM_R 16
#define M1_PWM_L 4

#define M3_PWM_R 5
#define M3_PWM_L 17

#define M2_PWM_R 18
#define M2_PWM_L 19

const int maxPWM = 255;

// -------------------

void setMotor(int motor, int speed) {
    int pwmR = (speed > 0) ? speed : 0;
    int pwmL = (speed < 0) ? -speed : 0;
    if (pwmR > maxPWM) pwmR = maxPWM;
    if (pwmL > maxPWM) pwmL = maxPWM;
    switch(motor) {
        case 1: analogWrite(M1_PWM_R, pwmR); analogWrite(M1_PWM_L, pwmL); break;
        case 2: analogWrite(M2_PWM_R, pwmR); analogWrite(M2_PWM_L, pwmL); break;
        case 3: analogWrite(M3_PWM_R, pwmR); analogWrite(M3_PWM_L, pwmL); break;
        case 4: analogWrite(M4_PWM_R, pwmR); analogWrite(M4_PWM_L, pwmL); break;
    }
}

void Inverse_Kinematics(double Vx, double Vy, double W) {
    double R = 7.6;
    double M1 = ( sin(1*M_PI_4)*Vx + cos(1*M_PI_4)*Vy - R*W);
    double M2 = ( sin(3*M_PI_4)*Vx + cos(3*M_PI_4)*Vy + R*W);
    double M3 = ( sin(5*M_PI_4)*Vx + cos(5*M_PI_4)*Vy - R*W);
    double M4 = ( sin(7*M_PI_4)*Vx + cos(7*M_PI_4)*Vy + R*W);

    double maxVal = max(fabs(M1), max(fabs(M2), max(fabs(M3), fabs(M4))));
    if(maxVal > maxPWM) {
        M1 = M1/maxVal*maxPWM;
        M2 = M2/maxVal*maxPWM;
        M3 = M3/maxVal*maxPWM;
        M4 = M4/maxVal*maxPWM;
    }

    setMotor(1,(int)M1);
    setMotor(2,(int)M2);
    setMotor(3,(int)M3);
    setMotor(4,(int)M4);
}

// -------------------

void setup() {
    Serial.begin(115200);
    
    pinMode(M1_PWM_R, OUTPUT); pinMode(M1_PWM_L, OUTPUT);
    pinMode(M2_PWM_R, OUTPUT); pinMode(M2_PWM_L, OUTPUT);
    pinMode(M3_PWM_R, OUTPUT); pinMode(M3_PWM_L, OUTPUT);
    pinMode(M4_PWM_R, OUTPUT); pinMode(M4_PWM_L, OUTPUT);
    
    Serial.println("ESP Ready for Serial Control");
}

String inputString = "";
boolean stringComplete = false;

void loop() {
    // FIX #1: Flush karakter sisa (\n, spasi, dll) sebelum '<'
    while (Serial.available()) {
        char inChar = (char)Serial.read();
        if (inChar == '<') {
            inputString = "";
        } else if (inChar == '>') {
            stringComplete = true;
            break;
        } else {
            // Hanya tambahkan ke string jika sudah mulai paket (ada isi)
            // Karakter noise sebelum '<' akan diabaikan karena inputString di-reset saat '<'
            inputString += inChar;
        }
    }

    if (stringComplete) {
        // Format: x,y,b6,b7
        int firstComma = inputString.indexOf(',');
        int secondComma = inputString.indexOf(',', firstComma + 1);
        int thirdComma = inputString.indexOf(',', secondComma + 1);
        
        if (firstComma > 0 && secondComma > 0 && thirdComma > 0) {
            String sX = inputString.substring(0, firstComma);
            String sY = inputString.substring(firstComma + 1, secondComma);
            String sB6 = inputString.substring(secondComma + 1, thirdComma);
            String sB7 = inputString.substring(thirdComma + 1);
            
            // Trim whitespace/newline yang mungkin tersisa
            sX.trim();
            sY.trim();
            sB6.trim();
            sB7.trim();

            int rawX = sX.toInt();
            int rawY = sY.toInt();
            int b6 = sB6.toInt();
            int b7 = sB7.toInt();
            
            // Mapping 0..255 -> -127..128
            // rawX (axes[0], Left Stick X) -> Vy (gerak lateral)
            // rawY (axes[1], Left Stick Y, sudah diinvert di Python) -> Vx (gerak maju/mundur)
            double Vy = (double)(rawX - 127);
            double Vx = (double)(rawY - 127);
            
            // Deadband
            if (abs(Vx) < 10) Vx = 0;
            if (abs(Vy) < 10) Vy = 0;
            
            // Rotation: b6 -> CCW, b7 -> CW
            double W = 0;
            if (b6 == 1) W = -5.0;
            if (b7 == 1) W =  5.0;
            
            // Debug (uncomment jika perlu)
            Serial.printf("rawX:%d rawY:%d Vx:%.1f Vy:%.1f W:%.1f\n", rawX, rawY, Vx, Vy, W);
            
            Inverse_Kinematics(Vx, Vy, W);
        }
        
        inputString = "";
        stringComplete = false;
    }
}
