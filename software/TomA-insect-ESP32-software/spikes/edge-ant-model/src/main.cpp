// Step 1 of the spike: does the mixed `arduino, espidf` framework even
// compile and boot for this exact board? No ESP-DL yet - that's step 2,
// added only once this is proven. See docs/adr/0002-on-device-ant-edge-model.md.
#include <Arduino.h>

void setup() {
  Serial.begin(115200);
  delay(250);
  Serial.println("spike: arduino+espidf mixed framework boots");
}

void loop() {
  delay(1000);
}
