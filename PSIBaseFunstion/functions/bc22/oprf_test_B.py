import argparse
import asyncio
import logging

import aiohttp
import numpy as np
from aiohttp import web

from communication.OPRF.OPRFReceiver import OPRFReceiver
from communication.handler import DataHandler, EndHandler, wait_for_remote_host

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

    x = 2
    l = 4
    prime = 17
    r = 3
    lam = 128
    beta = 21

    x = np.array([825, 3230])

    oprf_receiver = OPRFReceiver(data_handler, N=16, n=2, t=3, prime=prime, r=r, lam=lam, x=x)

    await oprf_receiver.transfer()

    res = oprf_receiver.eval()
    for item in res:
        print(item)

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
