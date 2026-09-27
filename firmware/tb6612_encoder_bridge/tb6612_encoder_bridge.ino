
#define STBY 6

#define AIN1 8
#define AIN2 12
#define PWMA 9   // left motor

#define BIN1 13
#define BIN2 5
#define PWMB 10  // right motor

#define ENCODER_LEFT_A 2   // must be an interrupt pin
#define ENCODER_LEFT_B 4
#define ENCODER_RIGHT_A 3  // must be an interrupt pin
#define ENCODER_RIGHT_B 7


const unsigned long ENCODER_REPORT_INTERVAL_MS = 20;   // 50 Hz
const unsigned long CMD_TIMEOUT_MS = 500;               // stop if the Pi goes quiet


volatile long leftTicks = 0;
volatile long rightTicks = 0;

long lastReportedLeftTicks = 0;
long lastReportedRightTicks = 0;
unsigned long lastReportTime = 0;

int targetLeftPwm = 0;
int targetRightPwm = 0;
unsigned long lastCommandTime = 0;

String rxLine = "";

void leftEncoderISR() {
  bool a = digitalRead(ENCODER_LEFT_A);
  bool b = digitalRead(ENCODER_LEFT_B);
  if (a == b) {
    leftTicks++;
  } else {
    leftTicks--;
  }
}

void rightEncoderISR() {
  bool a = digitalRead(ENCODER_RIGHT_A);
  bool b = digitalRead(ENCODER_RIGHT_B);
  if (a == b) {
    rightTicks--;
  } else {
    rightTicks++;
  }
}

void setMotor(int pwm, int pinIN1, int pinIN2, int pinPWM) {
  pwm = constrain(pwm, -255, 255);
  if (pwm > 0) {
    digitalWrite(pinIN1, HIGH);
    digitalWrite(pinIN2, LOW);
  } else if (pwm < 0) {
    digitalWrite(pinIN1, LOW);
    digitalWrite(pinIN2, HIGH);
  } else {
    digitalWrite(pinIN1, LOW);
    digitalWrite(pinIN2, LOW);
  }
  analogWrite(pinPWM, abs(pwm));
}

void stopMotors() {
  targetLeftPwm = 0;
  targetRightPwm = 0;
  setMotor(0, AIN1, AIN2, PWMA);
  setMotor(0, BIN1, BIN2, PWMB);
}

void handleLine(const String& line) {
  // Expected: "M <left> <right>"
  if (line.length() < 3 || line.charAt(0) != 'M') return;

  int firstSpace = line.indexOf(' ');
  int secondSpace = line.indexOf(' ', firstSpace + 1);
  if (firstSpace < 0 || secondSpace < 0) return;

  targetLeftPwm = line.substring(firstSpace + 1, secondSpace).toInt();
  targetRightPwm = line.substring(secondSpace + 1).toInt();
  lastCommandTime = millis();
}

void setup() {
  Serial.begin(115200);

  pinMode(STBY, OUTPUT);
  pinMode(AIN1, OUTPUT);
  pinMode(AIN2, OUTPUT);
  pinMode(PWMA, OUTPUT);
  pinMode(BIN1, OUTPUT);
  pinMode(BIN2, OUTPUT);
  pinMode(PWMB, OUTPUT);
  digitalWrite(STBY, HIGH);

  pinMode(ENCODER_LEFT_A, INPUT_PULLUP);
  pinMode(ENCODER_LEFT_B, INPUT_PULLUP);
  pinMode(ENCODER_RIGHT_A, INPUT_PULLUP);
  pinMode(ENCODER_RIGHT_B, INPUT_PULLUP);

  attachInterrupt(digitalPinToInterrupt(ENCODER_LEFT_A), leftEncoderISR, CHANGE);
  attachInterrupt(digitalPinToInterrupt(ENCODER_RIGHT_A), rightEncoderISR, CHANGE);

  stopMotors();
  lastCommandTime = millis();
  lastReportTime = millis();

  Serial.println("READY");
}

void loop() {

  while (Serial.available() > 0) {
    char c = Serial.read();
    if (c == '\n') {
      handleLine(rxLine);
      rxLine = "";
    } else if (c != '\r') {
      rxLine += c;
      if (rxLine.length() > 32) {
        rxLine = "";  // guard against garbage filling the buffer forever
      }
    }
  }

  
  if (millis() - lastCommandTime > CMD_TIMEOUT_MS) {
    targetLeftPwm = 0;
    targetRightPwm = 0;
  }

  setMotor(targetLeftPwm, AIN1, AIN2, PWMA);
  setMotor(targetRightPwm, BIN1, BIN2, PWMB);

 
  unsigned long now = millis();
  if (now - lastReportTime >= ENCODER_REPORT_INTERVAL_MS) {
    long curLeft, curRight;
    noInterrupts();
    curLeft = leftTicks;
    curRight = rightTicks;
    interrupts();

    long dLeft = curLeft - lastReportedLeftTicks;
    long dRight = curRight - lastReportedRightTicks;
    unsigned long dt = now - lastReportTime;

    Serial.print("E ");
    Serial.print(dLeft);
    Serial.print(" ");
    Serial.print(dRight);
    Serial.print(" ");
    Serial.println(dt);

    lastReportedLeftTicks = curLeft;
    lastReportedRightTicks = curRight;
    lastReportTime = now;
  }
}
