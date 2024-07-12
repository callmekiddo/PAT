#include <WiFi.h>
#include <freertos/task.h>
#include <freertos/queue.h>
#include <freertos/timers.h>

#define WIFI_SSID "NhaBaoViec"
#define WIFI_PASSWORD "0433821415"

#define BUZZER_PIN 2
#define SIGNAL_QUEUE_SIZE 10
#define SERVER_PORT 8088

QueueHandle_t signalQueue;
TimerHandle_t buzzerTimer;
TaskHandle_t buzzerTaskHandle;
TaskHandle_t signalTaskHandle;
TaskHandle_t sendToPhoneTaskHandle;

WiFiServer server(SERVER_PORT);

void connectToWiFi() {
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  while (WiFi.status() != WL_CONNECTED) {
    delay(1000);
    Serial.println("Connecting to WiFi...");
  }
  Serial.println("Connected to WiFi");
  Serial.print("ESP32 IP: ");
  Serial.println(WiFi.localIP());
}

void buzzerOffCallback(TimerHandle_t xTimer) {
  digitalWrite(BUZZER_PIN, LOW);
}

void buzzerTask(void *pvParameters) {
  char signal;
  while (1) {
    if (xQueueReceive(signalQueue, &signal, portMAX_DELAY) == pdTRUE) {
      while 
      if (signal == 'unknown') {
        digitalWrite(BUZZER_PIN, HIGH);
        xTimerStart(buzzerTimer, 0);
      } else if (signal == 'known') {
        digitalWrite(BUZZER_PIN, LOW);
        xTimerStop(buzzerTimer, 0);
      }
    }
  }
}

void receiveSignal(void *parameter) {
  while (true) {
    WiFiClient client = server.available();
    if (client.available()) {
      char signal = client.read();
      xQueueSend(signalQueue, &signal, portMAX_DELAY);
    }
  }
}

void sendToPhoneTask(void *pvParameters) {
  while (1) {
    if (WiFi.status() == WL_CONNECTED) {
      HTTPClient http;
      http.begin(APP_SERVER_URL);
      http.addHeader("Content-Type", "application/json");
      String jsonPayload = "{\"signal\": \"unknown\"}";
      int httpResponseCode = http.POST(jsonPayload);
      if (httpResponseCode > 0) {
        String response = http.getString();
        Serial.println(response);
      } else {
        Serial.printf("Error sending POST request: %s\n", http.errorToString(httpResponseCode).c_str());
      }
      http.end();
    }
    vTaskDelay(pdMS_TO_TICKS(5000)); 
  }
}

void setup() {
  Serial.begin(115200);

  pinMode(BUZZER_PIN, OUTPUT);
  digitalWrite(BUZZER_PIN, LOW);

  connectToWiFi();
  server.begin();

  signalQueue = xQueueCreate(SIGNAL_QUEUE_SIZE, sizeof(char));
  if (signalQueue == NULL) {
    Serial.println("Failed to create signal queue");
    while (1)
      ;
  }

  buzzerTimer = xTimerCreate("BuzzerTimer", pdMS_TO_TICKS(5000), pdFALSE, (void *)0, buzzerOffCallback);
  if (buzzerTimer == NULL) {
    Serial.println("Failed to create buzzer timer");
    while (1)
      ;
  }

  xTaskCreate(buzzerTask, "BuzzerTask", 10000, NULL, 1, &buzzerTaskHandle);
  xTaskCreate(receiveSignal, "SignalTask", 10000, NULL, 1, &signalTaskHandle);
  xTaskCreate(sendToPhoneTask, "SendToPhoneTask", 10000, NULL, 1, &sendToPhoneTaskHandle);
}

void loop() {
  // Main loop
}
