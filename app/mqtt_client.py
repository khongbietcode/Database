import os
import django
import json
import threading
import paho.mqtt.client as mqtt
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from datetime import datetime
from django.utils import timezone

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webquanly.settings')
django.setup()

from app.models import CardEvent, CardUser, PersonalAttendanceSetting

MQTT_BROKER = 'ad66d2d5e34a426099f94af411e4ad88.s1.eu.hivemq.cloud' 
MQTT_PORT = 8883 
MQTT_TOPIC = 'rfid/uid'


MQTT_USERNAME = 'Taicute123'
MQTT_PASSWORD = 'Tai123123'

channel_layer = get_channel_layer()


mqtt_client_instance = None

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print('Connected successfully to MQTT broker!')
        client.subscribe(MQTT_TOPIC)
        client.subscribe('esp32/data')
    else:
        print('Failed to connect, return code %d\n', rc)

def on_message(client, userdata, msg):
    print(f"on_message called. Topic: {msg.topic}, Payload: {msg.payload}")
    data = msg.payload.decode()
    print(f'Received MQTT message: {data}')
    try:
        payload = json.loads(data)
        card_id = payload.get('card_id')
        user_name = "Unknown User" 
        card_user = None  # Initialize card_user to None
        if card_id:
            try:
                card_user = CardUser.objects.select_related('user').get(card_id=card_id)
                user_name = card_user.user.username
                print(f"Found user_name: {user_name} for card_id: {card_id}")
            except CardUser.DoesNotExist:
                print(f"No user found for card_id: {card_id}")
                # Gửi trạng thái về ESP32 nếu không tìm thấy user
                publish_message('esp32/status', "người dùng không tồn tại")
                print("Đã gửi trạng thái 'người dùng không tồn tại' tới ESP32 qua MQTT topic 'esp32/status'")
                return  # Dừng xử lý tiếp

            except Exception as db_error:
                print(f"Database lookup error: {db_error}")
                publish_message('esp32/status', "lỗi hệ thống")
                return

            # Nếu tìm thấy user, xử lý như bình thường
            CardEvent.objects.create(
                card_id=card_id,
                user=card_user.user,
            )
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

            # XỬ LÝ TRẠNG THÁI ĐIỂM DANH
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
            # Gửi trạng thái về ESP32
            publish_message('esp32/status', status)
            print(f"Đã gửi trạng thái '{status}' tới ESP32 qua MQTT topic 'esp32/status'")

        else:
            print("Received MQTT message without card_id")

    except json.JSONDecodeError:
        print(f"Failed to decode JSON from MQTT message: {data}")
    except Exception as e:
        print('Error processing MQTT message:', e)

def get_mqtt_client():
    global mqtt_client_instance
    if mqtt_client_instance is None:
        mqtt_client_instance = mqtt.Client()
       
        mqtt_client_instance.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
        
        mqtt_client_instance.tls_set()
        mqtt_client_instance.on_connect = on_connect
        mqtt_client_instance.on_message = on_message
        mqtt_client_instance.connect(MQTT_BROKER, MQTT_PORT, 60)
        
        threading.Thread(target=mqtt_client_instance.loop_start, daemon=True).start()
    return mqtt_client_instance

def publish_message(topic, message):
    client = get_mqtt_client()
    client.publish(topic, message)

def start_mqtt():
    client = mqtt.Client()
    
    client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    
    client.tls_set()
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    client.loop_forever()


mqtt_thread = threading.Thread(target=start_mqtt, daemon=True)
mqtt_thread.start()
