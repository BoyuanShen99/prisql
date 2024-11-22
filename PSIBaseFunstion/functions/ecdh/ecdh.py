import argparse
import asyncio
import logging
import pickle
import time

import aiohttp
from aiohttp import web
from ecdsa import SECP256k1, SigningKey

from handler import DataHandler, EndHandler
from utils.ecdh_utils import find_intersection, encrypt_dataset, point_to_tuple, tuple_to_point, transfer_to_tuple, \
    transfer_to_point, re_encrypt_dataset
from utils.io import save_to_csv, read_csv

# 设置日志
logging.basicConfig(level=logging.INFO)


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


async def main(local_port, remote_ip, remote_port,
               read_path, save_path, inter, curve):
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

    # loca_data
    df = read_csv(read_path)
    # local_data = df[inter].tolist()
    local_data = df[inter]

    sk = SigningKey.generate(curve=curve).privkey.secret_multiplier

    # encrypted_data
    logging.info("Step 1: local data process")
    encrypted_data_future = asyncio.create_task(encrypt_dataset(local_data, curve, sk))

    await encrypted_data_future
    encrypted_data = encrypted_data_future.result()

    # encrypted_data_t = [point_to_dict(point) for point in encrypted_data]
    # encrypted_data_t_future = asyncio.create_task(transfer_to_tuple(encrypted_data))
    encrypted_data_bytes = pickle.dumps(encrypted_data)

    # 本地准备好后再启动连接
    await wait_for_remote_host(remote_ip, remote_port)

    # exchanged_encrypted_data
    logging.info("Step 2: exchange encrypted data")
    start = time.time()
    await data_handler.send_bytes_flow(encrypted_data_bytes)
    await data_handler.received_data_event.wait()
    peer_encrypted_data = pickle.loads(data_handler.data)
    data_handler.consume_data()

    logging.info(f"Step 2 take {time.time() - start}")

    # final_encrypted_data
    logging.info("Step 3: final data process")
    start = time.time()

    # final_peer_encrypted_data = [point * sk for point in peer_encrypted_data]
    final_peer_encrypted_data_future = asyncio.create_task(re_encrypt_dataset(peer_encrypted_data, sk))

    await final_peer_encrypted_data_future
    final_peer_encrypted_data = final_peer_encrypted_data_future.result()

    final_peer_encrypted_data_bytes = pickle.dumps(final_peer_encrypted_data)
    logging.info(f"Step 3 take {time.time() - start}")

    # peer_final_encrypted_data
    logging.info("Step 4: exchange final data")

    start = time.time()
    await data_handler.send_bytes_flow(final_peer_encrypted_data_bytes)
    await data_handler.received_data_event.wait()
    final_encrypted_data = pickle.loads(data_handler.data)
    data_handler.consume_data()

    logging.info(f"Step 4 take {time.time() - start}")

    # 本地求交
    # final_encrypted_data
    logging.info("Step 5: local intersection")
    start = time.time()
    inter_indices = find_intersection(
        final_encrypted_data, final_peer_encrypted_data
    )

    intersection = [local_data[i] for i in inter_indices]

    save_to_csv(intersection, save_path, inter)
    logging.info(f"Step 5 take {time.time() - start}")

    # 发送结束信号
    logging.info("Sending end signal...")
    await end_handler.send_end_signal()

    # 确认双方结束
    await end_handler.received_end_signal_event.wait()
    await end_handler.received_end_confirmation_event.wait()

    logging.info("Both parties have confirmed the end of the communication.")
    await runner.cleanup()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Host A')
    parser.add_argument('--local-port', type=int, default=8080, help='Local port to bind')
    parser.add_argument('--remote-ip', type=str, required=True, help='Remote host IP address')
    parser.add_argument('--remote-port', type=int, required=True, help='Remote host port')
    parser.add_argument('--read-path', type=str, required=True, help='path of file to intersection')
    parser.add_argument('--save-path', type=str, required=True, help='path to save result')
    parser.add_argument('--inter', type=str, required=True, help='intersection column')
    # todo 后续添加更多椭圆曲线支持
    parser.add_argument('--curve', type=str, default="SECP256k1", help='intersection column')

    args = parser.parse_args()

    # todo curve具体选择
    if args.curve == "SECP256k1":
        curve = SECP256k1
    else:
        curve = None
        logging.error("Unsupported curve type")

    asyncio.run(main(args.local_port, args.remote_ip, args.remote_port,
                     args.read_path, args.save_path, args.inter, curve))
