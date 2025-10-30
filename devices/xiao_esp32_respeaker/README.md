# XIAO ESP32-S3 ReSpeaker Setup для Franky

## Требования

### Оборудование
- XIAO ESP32-S3
- ReSpeaker XVF3800 USB Mic Array (или совместимый микрофон)
- Опционально: Servo мотор для физической челюсти

### Программное обеспечение
- Arduino IDE
- Библиотеки:
  - WiFi (встроена)
  - PubSubClient
  - AudioTools

## Установка библиотек

1. Откройте Arduino IDE
2. Перейдите в **Sketch → Include Library → Manage Libraries**
3. Установите:
   - `PubSubClient` by Nick O'Leary
   - `AudioTools` by Phil Schatzmann

## Настройка

### 1. Скопируйте настройки из .env

Откройте файл `xiao_esp32_respeaker.ino` и замените:

```cpp
const char* ssid = "PUT_YOUR_WIFI_SSID_HERE";
const char* password = "PUT_YOUR_WIFI_PASSWORD_HERE";
const char* mqtt_server = "192.168.x.x";  // IP вашего Mac
```

Значения из вашего `.env` файла.

### 2. Узнайте IP адрес вашего Mac

```bash
ifconfig | grep "inet " | grep -v 127.0.0.1
```

Используйте этот IP как `mqtt_server`.

### 3. Подключение ReSpeaker к XIAO ESP32-S3

Подключите пины согласно конфигурации в коде:
- BCK (Bit Clock) → Pin 7
- WS (Word Select/LRCK) → Pin 8
- DIN (Data In) → Pin 9
- GND → GND
- 3V3 → 3V3

### 4. Загрузка прошивки

1. Подключите XIAO ESP32-S3 к компьютеру
2. В Arduino IDE выберите:
   - **Board**: XIAO_ESP32S3
   - **Port**: /dev/cu.usbmodem... (ваш порт)
3. Нажмите **Upload**

## Использование

### 1. Запустите MQTT broker

```bash
cd /Users/maksimnagaev/Projects/franky
docker-compose up -d
```

### 2. Загрузите прошивку на ESP32

Откройте Serial Monitor (115200 baud) чтобы видеть статус подключения.

### 3. Запустите Franky

```bash
python voice_bot_realtime.py
```

ESP32 будет:
- ✅ Подключаться к WiFi
- ✅ Подключаться к MQTT broker
- ✅ Стримить аудио в топик `franky/audio/input`
- ✅ Получать команды движения челюсти из `franky/jaw`

## Опционально: Подключение серво мотора

Для управления физической челюстью:

1. Подключите серво:
   - Signal → Pin D0 (или измените SERVO_PIN в коде)
   - VCC → 5V
   - GND → GND

2. Раскомментируйте в коде:
```cpp
// #include <ESP32Servo.h>
// Servo jaw_servo;

// В setup():
// jaw_servo.attach(servo_pin);

// В mqtt_callback():
// jaw_servo.write(servo_angle);
```

## Отладка

### Проблемы с WiFi
- Проверьте SSID и пароль
- Убедитесь что ESP32 в зоне покрытия WiFi

### Проблемы с MQTT
- Проверьте что MQTT broker запущен: `docker ps`
- Проверьте IP адрес Mac
- Проверьте firewall настройки

### Проблемы с аудио
- Проверьте подключение пинов I2S
- Откройте Serial Monitor для диагностики
- Проверьте что ReSpeaker правильно подключен

## MQTT топики

- `franky/audio/input` - аудио от микрофона (PCM 16-bit, 24kHz, mono)
- `franky/jaw` - команды для челюсти (float 0.0-1.0)