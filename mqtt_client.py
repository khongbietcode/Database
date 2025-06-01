import os
import django
import json
import paho.mqtt.client as mqtt
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from datetime import datetime
from django.utils import timezone
import time

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webquanly.settings')
django.setup()

from app.models import CardEvent, CardUser, PersonalAttendanceSetting

MQTT_BROKER = '0c1804ec304d42579831c43b09c0c5b3.s1.eu.hivemq.cloud'
MQTT_PORT = 8883
MQTT_TOPIC = 'rfid/uid'
MQTT_USERNAME = 'Taicute123'
MQTT_PASSWORD = 'Tai123123'

channel_layer = get_channel_layer()

# Khởi tạo MQTT client dùng toàn cục
mqtt_client = mqtt.Client(client_id="rfid_main_client", clean_session=False, protocol=mqtt.MQTTv311)
mqtt_client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
mqtt_client.tls_set(ca_certs="certs/Hivemq_Ca.pem")

import os
assert os.path.exists("certs/Hivemq_Ca.pem"), "CA file not found!"

def on_connect(client, userdata, flags, rc):
    
    if rc == 0:
        print('Connected successfully to MQTT broker!')
        client.subscribe(MQTT_TOPIC)
        client.subscribe('esp32/data')
    else:
        print(f'Failed to connect, return code {rc}')

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
                publish_message('esp32/status', "người dùng không tồn tại")
                return
            except Exception as db_error:
                print(f"Database lookup error: {db_error}")
                publish_message('esp32/status', "lỗi hệ thống")
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

            publish_message('esp32/status', status)
            print(f"Đã gửi trạng thái '{status}' tới ESP32 qua MQTT topic 'esp32/status'")
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
    print(f"Disconnected from MQTT broker with result code {rc}")
    if rc != 0:
        print("Unexpected disconnection. Trying to reconnect...")
        try:
            client.reconnect()
        except Exception as e:
            print(f"Reconnect failed: {e}")

def start_mqtt():
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message
    mqtt_client.on_disconnect = on_disconnect  # Thêm dòng này
    mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
    mqtt_client.loop_forever()

if __name__ == "__main__":
    start_mqtt()
