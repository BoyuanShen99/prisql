import argparse
import asyncio
import logging
import math
import os
import time
from typing import List

import aiohttp
import numpy as np
from Crypto.Util import number
from aiohttp import web

from communication.OPRF.OPRFReceiver import OPRFReceiver
from communication.handler import DataHandler, EndHandler, wait_for_remote_host
from utils.cuckoo import CuckooHashTable
from utils.funtions import unpack_byte_data, \
    pad_to_fixed_length, hash_to_finite_int, generate_large_prime
from utils.io import read_csv, save_to_csv

# 获取 aiohttp.access 记录器
aiohttp_access_logger = logging.getLogger('aiohttp.access')
# 设置记录器级别为 WARNING 或更高
aiohttp_access_logger.setLevel(logging.WARNING)
logging.basicConfig(level=logging.INFO)


class Bob(object):
    # Receiver
    def __init__(self, words: List[bytes], handler,
                 N, t, prime, r,
                 codewords=128):

        if codewords < 128:
            raise ValueError(f"codewords {codewords} is too small,"
                             f" it should be greater equal than 128 to ensure security")

        self.n = int(1.27 * len(words))
        self.s = 0
        self._p = prime
        self._r = r

        self.N = N
        self.t = t

        self._lam = codewords

        self.handler = handler

        start = time.time()
        cuckoo = CuckooHashTable(self.n, self.s)
        for word in words:
            cuckoo.update(word)
        self.table = cuckoo.table
        self.table_hash_index = cuckoo.table_hash_index
        logging.info(f"build cuckoo table cost {time.time() - start}")

        # 计算向量r
        dummy_table = []
        for key, hash_index in zip(self.table, self.table_hash_index):
            if key is None:
                key = os.urandom(self._lam)
            else:
                key = key + bytes(hash_index)
                # print(f"key {key} pad {pad_to_fixed_length(key, self._lam)} value {hash_to_finite_int(pad_to_fixed_length(key, self._lam), pow(self._p, self._r))}")
                key = pad_to_fixed_length(key, self._lam)

            dummy_table.append(hash_to_finite_int(key, pow(self._p, self._r)))

        # print(dummy_table)
        # OprfClient
        pad_r = np.array(dummy_table, dtype=object)
        # 需要填充

        self.oprf_receiver = OPRFReceiver(self.handler, N=self.N, n=self.n,
                                          t=self.t, prime=self._p, r=self._r, lam=codewords, x=pad_r)

    async def prepare(self):
        timeout = aiohttp.ClientTimeout(total=None, connect=None, sock_connect=None, sock_read=None)
        session = aiohttp.ClientSession(timeout=timeout)

        await self.handler.send_data_in_session((self.N, self.n, self.t, self._p, self._r, self._lam), session)

        start = time.time()
        await self.oprf_receiver.transfer(session)
        logging.info(f"oprf part cost {time.time() - start}")

        start = time.time()
        self._oprf_res = self.oprf_receiver.eval()
        logging.info(f"oprf res cost {time.time() - start}")

        await session.close()

    async def intersect(self) -> List[bytes]:

        start = time.time()

        peer_tables = set()

        await self.handler.received_data_event.wait()
        bytes_chunk_len = self.handler.data
        self.handler.consume_data()

        await self.handler.received_data_event.wait()
        bytes_vals = self.handler.data
        self.handler.consume_data()

        peer_byte_vals = unpack_byte_data(bytes_vals, bytes_chunk_len)
        peer_tables.update(peer_byte_vals)

        end = time.time()
        logging.info(f"接收Alice加密后数据所用时间为 {end - start} 秒")

        start = time.time()
        start1 = time.time()
        res = []

        for i, (key, hash_index) in enumerate(zip(self.table, self.table_hash_index)):
            if key is not None:
                local_val = self.eval(i)

                # print(f"{key} ({hash_index}) index {i}: {local_val}")

                if local_val in peer_tables:
                    res.append(key.decode('utf-8'))
        end1 = time.time()
        logging.info(f"求交数据所用时间为 {end1 - start1} 秒")

        await self.handler.send_data_flow(res)

        end = time.time()
        logging.info(f"求交并发送求交所得数据所用时间为{end - start}秒")

        return res

    def eval(self, i: int) -> bytes:
        return self._oprf_res[i]


async def main(local_port, remote_ip, remote_port,
               read_path, save_path, inter):

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

    df = read_csv(read_path)
    target_col = df[inter]
    data = [item.rstrip().encode('utf-8') for item in target_col]

    start_time = time.time()

    start = time.time()

    # 参数设置
    secure_param = 20
    # prime = number.getPrime(int(math.log2(len(data))) + secure_param)
    prime = 2
    r = 30

    sparse_param = 0.05
    N = 128

    bob = Bob(data, data_handler, N=N, t=int(N * sparse_param), prime=prime, r=r)
    logging.info(f"初始化+哈希运行时间：{time.time() - start} 秒")

    await wait_for_remote_host(remote_ip, remote_port)

    logging.info("start prepare")
    start = time.time()
    await bob.prepare()  # prepare stage
    logging.info(f"prepare程序运行时间：{time.time() - start}秒")
    logging.info("finish prepare")

    logging.info("start intersection")
    start = time.time()
    res = await bob.intersect()  # intersect stage, res is the intersection
    logging.info(f"intersect程序运行时间：{time.time() - start} 秒")
    logging.info("finish intersection")

    res_strs = sorted(res)
    save_to_csv(res_strs, save_path, inter)

    logging.info(f"程序运行时间：{time.time() - start_time} 秒")

    # 发送结束信号
    logging.info("Sending end signal...")
    await end_handler.send_end_signal()

    # 确认双方结束
    await end_handler.received_end_signal_event.wait()
    await end_handler.received_end_confirmation_event.wait()

    logging.info("Both parties have confirmed the end of the communication.")
    await runner.cleanup()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Host A')
    parser.add_argument('--local-port', type=int, default=8080, help='Local port to bind')
    parser.add_argument('--remote-ip', type=str, required=True, help='Remote host IP address')
    parser.add_argument('--remote-port', type=int, required=True, help='Remote host port')
    parser.add_argument('--read-path', type=str, required=True, help='path of file to intersection')
    parser.add_argument('--save-path', type=str, required=True, help='path to save result')
    parser.add_argument('--inter', type=str, required=True, help='intersection column')

    args = parser.parse_args()

    asyncio.run(main(args.local_port, args.remote_ip, args.remote_port,
                     args.read_path, args.save_path, args.inter))
