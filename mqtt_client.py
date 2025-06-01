import os
import ssl
import django
import json
import paho.mqtt.client as mqtt
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from datetime import datetime
from django.utils import timezone
import time
import random

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webquanly.settings')
django.setup()

from app.models import CardEvent, CardUser, PersonalAttendanceSetting

# Sử dụng các biến môi trường
MQTT_BROKER = os.getenv("MQTT_BROKER", '0c1804ec304d42579831c43b09c0c5b3.s1.eu.hivemq.cloud')
MQTT_PORT = int(os.getenv("MQTT_PORT", 8883))
MQTT_USERNAME = os.getenv("MQTT_USERNAME", "Taicute123")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "Tai123123")
CA_CERT_CONTENT = os.getenv("CA_CERT_CONTENT")

# Đảm bảo tất cả các topic bắt đầu bằng tên người dùng
MQTT_TOPIC = f"{MQTT_USERNAME}/rfid/uid"
ESP32_TOPIC = f"{MQTT_USERNAME}/esp32/data"
STATUS_TOPIC = f"{MQTT_USERNAME}/esp32/status"

channel_layer = get_channel_layer()

# Khởi tạo MQTT client với Client ID ngẫu nhiên
CLIENT_ID = f"railway_client_{random.randint(1000,9999)}"
mqtt_client = mqtt.Client(client_id=CLIENT_ID, clean_session=True, protocol=mqtt.MQTTv311)
mqtt_client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)

# Cấu hình TLS an toàn hơn
ssl_context = ssl.create_default_context()
if CA_CERT_CONTENT:
    ssl_context.load_verify_locations(cadata=CA_CERT_CONTENT)
else:
    # Chế độ development (không nên dùng production)
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

mqtt_client.tls_set_context(ssl_context)

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print('Connected successfully to MQTT broker!')
        client.subscribe(MQTT_TOPIC)
        client.subscribe(ESP32_TOPIC)
    else:
        # Bổ sung thông báo lỗi chi tiết
        errors = {
            1: "Incorrect protocol version",
            2: "Invalid client identifier",
            3: "Server unavailable",
            4: "Bad username/password",
            5: "Not authorised"
        }
        error_msg = errors.get(rc, f"Unknown error ({rc})")
        print(f'Connection failed: {error_msg}')

def on_message(client, userdata, msg):
    print(f"on_message called. Topic: {msg.topic}, Payload: {msg.payload}")
    data = msg.payload.decode()
    print(f'Received MQTT message: {data}')
    try:
        payload = json.loads(data)
        card_id = payload.get('card_id')
        user_name = "Unknown User"
        card_user = None

        if card_id:
            try:
                card_user = CardUser.objects.select_related('user').get(card_id=card_id)
                user_name = card_user.user.username
                print(f"Found user_name: {user_name} for card_id: {card_id}")
            except CardUser.DoesNotExist:
                print(f"No user found for card_id: {card_id}")
                publish_message(STATUS_TOPIC, "người dùng không tồn tại")
                return
            except Exception as db_error:
                print(f"Database lookup error: {db_error}")
                publish_message(STATUS_TOPIC, "lỗi hệ thống")
                return

            CardEvent.objects.create(card_id=card_id, user=card_user.user)

            async_to_sync(channel_layer.group_send)(
                'esp32_data',
                {
                    'type': 'esp32_message',
                    'data': {
                        'card_id': card_id,
                        'user_name': user_name
                    }
                }
            )

            # Xử lý trạng thái điểm danh
            status = "Không hợp lệ"
            now = timezone.localtime()
            today = now.date()
            setting = PersonalAttendanceSetting.objects.filter(user=card_user.user, date=today).first()
            if not setting:
                status = "Không có cấu hình"
            else:
                checkin_dt = datetime.combine(today, setting.checkin_time)
                checkout_dt = datetime.combine(today, setting.checkout_time)
                now_naive = now.replace(tzinfo=None)
                if now_naive < checkin_dt:
                    status = "sớm"
                elif now_naive > checkin_dt:
                    status = "trễ"
                else:
                    status = "đúng giờ"

            publish_message(STATUS_TOPIC, status)
            print(f"Đã gửi trạng thái '{status}' tới ESP32 qua MQTT topic '{STATUS_TOPIC}'")
        else:
            print("Received MQTT message without card_id")
    except json.JSONDecodeError:
        print(f"Failed to decode JSON from MQTT message: {data}")
    except Exception as e:
        print('Error processing MQTT message:', e)

def publish_message(topic, message):
    try:
        mqtt_client.publish(topic, message)
        print(f"Published '{message}' to topic '{topic}'")
    except Exception as e:
        print(f"Failed to publish message: {e}")

def on_disconnect(client, userdata, rc):
    print(f"Disconnected with code {rc}")
    if rc != 0:
        print("Reconnecting...")
        # Xử lý reconnect an toàn
        while True:
            try:
                client.reconnect()
                return
            except Exception as e:
                print(f"Reconnect failed: {e}")
                time.sleep(5)

def start_mqtt():
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message
    mqtt_client.on_disconnect = on_disconnect
    
    try:
        mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
        mqtt_client.loop_start()  # Sử dụng loop_start thay vì loop_forever
    except Exception as e:
        print(f"Initial connection failed: {e}")
        # Khởi động tiến trình reconnect
        on_disconnect(mqtt_client, None, 0)

if __name__ == "__main__":
    start_mqtt()
