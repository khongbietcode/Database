import json
from channels.generic.websocket import AsyncWebsocketConsumer

class ESP32Consumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.channel_layer.group_add("esp32_data", self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard("esp32_data", self.channel_name)

    async def receive(self, text_data):
       
        pass

    async def esp32_message(self, event):
        
        await self.send(text_data=json.dumps(event["data"])) 