import asyncio
import json
import logging

import aiohttp
from aiohttp import web

CHUNK_SIZE = 2048


class DataHandler:
    def __init__(self, remote_ip, remote_port):
        self.received_data_event = asyncio.Event()
        self.data_consumed_event = asyncio.Event()
        self.data = None
        self.data_consumed_event.set()

        self.ip = remote_ip
        self.port = remote_port

    async def send_bytes_in_session(self, session, byte_data):
        async with session.post(f'http://{self.ip}:{self.port}/receive_bytes', data=byte_data) as response:
            if response.status == 200:
                # Data sent successfully
                return
            else:
                logging.error("Failed to send data.")

    async def send_data(self, data):
        async with aiohttp.ClientSession() as session:
            async with session.post(f'http://{self.ip}:{self.port}/receive_data', json={'data': data}) as response:
                if response.status == 200:
                    # print("Data sent successfully.")
                    return
                else:
                    print("Failed to send data.")

    async def send_data_flow(self, data):
        async with aiohttp.ClientSession() as session:
            async with session.post(f'http://{self.ip}:{self.port}/receive_data_flow',
                                    data=self.data_generator(data),
                                    headers={'Content-Type': 'application/json'}) as response:
                if response.status == 200:
                    # print("Data stream sent successfully.")
                    return
                else:
                    print(f"Failed to send data stream. Status: {response.status}")

    async def send_bytes(self, byte_data):
        async with aiohttp.ClientSession() as session:
            async with session.post(f'http://{self.ip}:{self.port}/receive_bytes', data=byte_data) as response:
                if response.status == 200:
                    # print("Bytes data sent successfully.")
                    return
                else:
                    print("Failed to send bytes data.")

    async def send_bytes_flow(self, byte_data):
        async with aiohttp.ClientSession() as session:
            async with session.post(f'http://{self.ip}:{self.port}/receive_bytes_flow',
                                    data=self.bytes_generator(byte_data),
                                    headers={'Content-Type': 'application/octet-stream'}) as response:
                if response.status == 200:
                    # print("Bytes stream sent successfully.")
                    return
                else:
                    print(f"Failed to send bytes stream. Status: {response.status}")

    async def bytes_generator(self, byte_data):
        for i in range(0, len(byte_data), CHUNK_SIZE):
            if i + CHUNK_SIZE >= len(byte_data):
                chunk = byte_data[i:]
            else:
                chunk = byte_data[i:i + CHUNK_SIZE]
            yield chunk

    async def data_generator(self, data):
        # 逐块传输数据，每块都作为 JSON 字符串
        for item in data:
            chunk = json.dumps({"data": item}).encode('utf-8') + b'\n'
            yield chunk

    async def receive_data(self, request):
        await self.data_consumed_event.wait()

        data = await request.json()
        self.received_data_event.set()
        self.data_consumed_event.clear()
        self.data = data.get('data')
        logging.info("Received data")
        return web.json_response({'status': 'ok'})

    async def receive_data_flow(self, request):
        await self.data_consumed_event.wait()
        logging.info("Start receiving data...")
        received_data = []
        buffer = b""

        async for chunk in request.content.iter_any():
            buffer += chunk
            while b'\n' in buffer:
                line, buffer = buffer.split(b'\n', 1)
                if line:
                    try:
                        chunk_str = line.decode('utf-8')
                        chunk_json = json.loads(chunk_str)
                        received_data.append(chunk_json.get('data', []))
                    except json.JSONDecodeError as e:
                        logging.error(f"JSON decode error: {e}")

        if buffer:
            try:
                chunk_str = buffer.decode('utf-8')
                chunk_json = json.loads(chunk_str)
                received_data.append(chunk_json.get('data', []))
            except json.JSONDecodeError as e:
                logging.error(f"JSON decode error: {e}")

        logging.info("Received data")
        self.received_data_event.set()
        self.data_consumed_event.clear()
        self.data = received_data
        return web.json_response({'status': 'ok'})

    async def receive_bytes(self, request):
        await self.data_consumed_event.wait()
        self.data = await request.read()
        self.received_data_event.set()
        self.data_consumed_event.clear()
        return aiohttp.web.json_response({'status': 'ok'})

    async def receive_bytes_flow(self, request):
        await self.data_consumed_event.wait()
        received_bytes = bytearray()
        async for chunk in request.content.iter_chunked(CHUNK_SIZE):
            received_bytes.extend(chunk)
        self.data = bytes(received_bytes)
        self.received_data_event.set()
        self.data_consumed_event.clear()
        return aiohttp.web.json_response({'status': 'ok'})

    def consume_data(self):
        # 当数据被消耗时，调用此方法
        self.received_data_event.clear()  # 清除接收事件标志，表示数据未接收
        self.data_consumed_event.set()  # 设置消耗事件标志，表示数据已被消耗


class EndHandler:
    def __init__(self, remote_ip, remote_port):
        self.received_end_signal_event = asyncio.Event()
        self.received_end_confirmation_event = asyncio.Event()

        self.ip = remote_ip
        self.port = remote_port

    async def send_end_signal(self):
        async with aiohttp.ClientSession() as session:
            async with session.post(f'http://{self.ip}:{self.port}/end', json={'signal': 'end'}) as response:
                if response.status == 200:
                    logging.info(f"成功向 {self.ip}:{self.port} 发送结束信号")
                    data = await response.json()
                    if data.get('confirmation') == 'end signal received':
                        logging.info(f"收到来自 {self.ip}:{self.port} 的结束信号确认")
                        self.received_end_confirmation_event.set()
                else:
                    logging.error(f"向 {self.ip}:{self.port} 发送结束信号失败")

    async def end_handle(self, request):
        data = await request.json()
        if data.get('signal') == 'end':
            logging.info("Received end signal")
            self.received_end_signal_event.set()
            return web.json_response({'confirmation': 'end signal received'})
        return web.json_response({'status': 'ok'})


async def wait_for_remote_host(remote_ip, remote_port):
    while True:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f'http://{remote_ip}:{remote_port}/healthcheck') as response:
                    if response.status == 200:
                        logging.info(f"Connected to {remote_ip}:{remote_port}")
                        break
        except aiohttp.ClientConnectorError:
            logging.info(f"Waiting for {remote_ip}:{remote_port} to be available...")
            await asyncio.sleep(1)


async def main():
    data_handler = DataHandler("127.0.0.1", 8080)

    # 示例数据
    json_data = ["item1", "item2", "item3"]
    byte_data = b"Example bytes data"

    # 运行示例
    loop = asyncio.get_event_loop()
    await data_handler.send_data("localhost", 8000, json_data)
    await data_handler.received_data_event.wait()
    print(data_handler.data)
    data_handler.received_data_event.clear()

    await data_handler.send_bytes("localhost", 8000, byte_data)
    await data_handler.received_data_event.wait()
    print(data_handler.data)
    data_handler.received_data_event.clear()


if __name__ == "__main__":
    asyncio.run(main())
