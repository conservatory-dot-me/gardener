#!/usr/bin/env python
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gardener.settings')

import django
django.setup()

import asyncio
import logging
import threading
import time
import tornado.ioloop
import tornado.web
import tornado.websocket
from tornado.options import define
from tornado.options import options
from tornado.platform.asyncio import AnyThreadEventLoopPolicy

from django.conf import settings

from gardener.device.models import Device
from gardener.device.models import Pump

asyncio.set_event_loop_policy(AnyThreadEventLoopPolicy())

define('address', type=str, default='127.0.0.1')
define('port', type=int, default=8888)


class Application(tornado.web.Application):
    def __init__(self):
        handlers = [
            (r'/', MainHandler),
        ]
        tornado.web.Application.__init__(self, handlers)


class MainHandler(tornado.websocket.WebSocketHandler):
    clients = set()

    def open(self):
        self.clients.add(self)

    def on_close(self):
        self.clients.remove(self)

    def check_origin(self, origin):
        return True

    def on_message(self, message):
        self.write_message(message)

    @classmethod
    def send_message(cls, message):
        [client.write_message(message) for client in cls.clients]


def push_data():
    last_data = None

    pubsub = settings.REDIS_CONN.pubsub()
    pubsub.psubscribe(f'__keyspace@*:{settings.REDIS_KEY_PREFIX}:*')

    while True:
        now_ms = time.time() * 1000

        if last_data is None or (now_ms - last_data >= 3000):
            device = Device.objects.primary_device()
            message = dict(
                device_id=device.id,
                public_ip=device.public_ip,
                cpu_temp=device.cpu_temp,
                pump_status=device.pump_status)
            logging.info(message)
            MainHandler.send_message(message)
            last_data = now_ms

        msg = pubsub.get_message()
        if msg is None:
            time.sleep(0.01)  # 10 ms artificial intrinsic latency.
            continue

        (pump_id, pump_status) = Pump.parse_redis_pubsub_msg(msg)
        if pump_id is not None and pump_status is not None:
            message = dict(
                pump_id=pump_id,
                pump_status=pump_status)
            logging.info(message)
            MainHandler.send_message(message)


if __name__ == '__main__':
    tornado.options.parse_command_line()

    threading.Thread(target=push_data).start()

    application = Application()
    server = tornado.httpserver.HTTPServer(application)
    server.listen(options.port, address=options.address)
    tornado.ioloop.IOLoop.current().start()
