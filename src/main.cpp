#include <Arduino.h>
#include <U8g2lib.h>

static const uint8_t LCD_CS_PIN = 9;
static const uint16_t FRAME_WIDTH = 128;
static const uint16_t FRAME_HEIGHT = 64;
static const uint16_t FRAME_BUFFER_SIZE = FRAME_WIDTH * FRAME_HEIGHT / 8;
static const uint8_t SYNC0 = 0xA5;
static const uint8_t SYNC1 = 0x5A;

U8G2_ST7920_128X64_F_HW_SPI u8g2(U8G2_R0, LCD_CS_PIN, U8X8_PIN_NONE);

void setup() {
  Serial.begin(115200);
  u8g2.begin();
  u8g2.clearBuffer();
  u8g2.setFont(u8g2_font_helvR08_tf);
  u8g2.drawStr(0, 10, "Host disconnected");
  u8g2.drawStr(0, 20, "115200, 8, N, 1");
  u8g2.sendBuffer();
  Serial.println("READY");
}

bool receiveFrameBuffer(void) {
  static uint8_t syncState = 0;
  static uint16_t bytesReceived = 0;
  uint8_t *buffer = u8g2.getBufferPtr();

  while (Serial.available() > 0) 
  {
    int incoming = Serial.read();
    if (incoming < 0) 
    {
      syncState = 0;
      break;
    }
    uint8_t ch = static_cast<uint8_t>(incoming);

    if (syncState == 0) 
    {
      if (ch == SYNC0) 
      {
        syncState = 1;
      }
      continue;
    }

    if (syncState == 1) 
    {
      if (ch == SYNC1) 
      {
        syncState = 2;
        bytesReceived = 0;
        continue;
      }
      syncState = (ch == SYNC0) ? 1 : 0;
      continue;
    }

    if(syncState == 2) 
    {
      buffer[bytesReceived++] = ch;
    }

    if (bytesReceived >= FRAME_BUFFER_SIZE) 
    {
      syncState = 0;
      bytesReceived = 0;
      return true;
    }
  }

  return false;
}

void loop() {
  if (receiveFrameBuffer()) {
    u8g2.sendBuffer();
    Serial.println("FRAME_OK");
  }
}
