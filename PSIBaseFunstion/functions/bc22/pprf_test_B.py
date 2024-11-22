import argparse
import asyncio
import logging
import random
import time
from typing import List

import aiohttp
from Crypto.Hash import SHAKE256, SHA256
from aiohttp import web

from communication.PPRF.PPRFReceiver import PPRFReceiver
from communication.handler import DataHandler, EndHandler, wait_for_remote_host
from utils.cuckoo import CuckooHashTable
from utils.funtions import bit_arr_to_bytes, unpack_byte_data, \
    pad_to_fixed_length

# 获取 aiohttp.access 记录器
aiohttp_access_logger = logging.getLogger('aiohttp.access')
# 设置记录器级别为 WARNING 或更高
aiohttp_access_logger.setLevel(logging.WARNING)
logging.basicConfig(level=logging.INFO)


async def main(local_port, remote_ip, remote_port):
    allowed_remote_ip = remote_ip
    allowed_remote_port = remote_port

    # 事件处理器
    data_handler = DataHandler(remote_ip, remote_port)
    end_handler = EndHandler(remote_ip, remote_port)

    # 启动服务器
    app = web.Application()

    app.router.add_post('/receive_data', data_handler.receive_data)
    app.router.add_post('/receive_data_flow', data_handler.receive_data_flow)
    app.router.add_post('/receive_bytes', data_handler.receive_bytes)
    app.router.add_post('/receive_bytes_flow', data_handler.receive_bytes_flow)
    app.router.add_post('/end', end_handler.end_handle)
    app.router.add_get('/healthcheck', lambda request: aiohttp.web.json_response({'status': 'ok'}))

    runner = aiohttp.web.AppRunner(app)
    await runner.setup()
    site = aiohttp.web.TCPSite(runner, '0.0.0.0', local_port)
    await site.start()

    # 等待服务器启动
    await asyncio.sleep(1)

    await wait_for_remote_host(remote_ip, remote_port)

    alpha = 8
    l = 4
    prime = 11
    r = 2
    lam = 256 // 8
    pprf_receiver = PPRFReceiver(data_handler, l, prime, r, lam, alpha)

    puncture_key = await pprf_receiver.transfer()

    print(puncture_key)
    print("--------------------------")
    for i in range(1, l + 1):
        print(f"level {i}")
        level_key = pprf_receiver.tree.nodes_in_level(i)
        for key in level_key:
            print(key)

    # 发送结束信号
    logging.info("Sending end signal...")
    await end_handler.send_end_signal()

    # 确认双方结束
    await end_handler.received_end_signal_event.wait()
    await end_handler.received_end_confirmation_event.wait()

    logging.info("Both parties have confirmed the end of the communication.")
    await runner.cleanup()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Host B')
    parser.add_argument('--local-port', type=int, default=8080, help='Local port to bind')
    parser.add_argument('--remote-ip', type=str, required=True, help='Remote host IP address')
    parser.add_argument('--remote-port', type=int, required=True, help='Remote host port')

    args = parser.parse_args()

    asyncio.run(main(args.local_port, args.remote_ip, args.remote_port))
