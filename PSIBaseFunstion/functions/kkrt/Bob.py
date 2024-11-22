import argparse
import asyncio
import logging
import random
import time

import aiohttp
import numpy as np
from aiohttp import web

from handler import DataHandler, EndHandler, wait_for_remote_host

from utils.sender import Sender
from utils.send import send
from typing import List
from Crypto.Hash import SHAKE256, SHA256
from utils.cuckoo import CuckooHashTable
from utils.funtions import rand_binary_arr, bit_arr_to_bytes, bytes_to_bit_arr, int_to_bytes, unpack_byte_data
from utils.io import read_csv, save_to_csv


# 获取 aiohttp.access 记录器
aiohttp_access_logger = logging.getLogger('aiohttp.access')
# 设置记录器级别为 WARNING 或更高
aiohttp_access_logger.setLevel(logging.WARNING)
logging.basicConfig(level=logging.INFO)


class Bob(object):
    def __init__(self, words: List[bytes], handler, remote_ip, remote_port):
        # def __init__(self, words: List[bytes]):
        self.n = int(1.27 * len(words))
        self.s = 0
        cuckoo = CuckooHashTable(self.n, self.s)
        for word in words:
            cuckoo.update(word)
        self.table = cuckoo.table
        self.stash = cuckoo.stash
        self.table_hash_index = cuckoo.table_hash_index

        self.handler = handler

        self.remote_ip = remote_ip
        self.remote_port = remote_port
        # 计算向量r
        dummy_table = []
        for key, hash_index in zip(self.table, self.table_hash_index):
            if key is None:
                key = random.getrandbits(64).to_bytes(8, "big")
            else:
                key = key + bytes([hash_index])
            dummy_table.append(key)

        for key in self.stash:
            if key is None:
                key = random.getrandbits(64).to_bytes(8, "big")
            dummy_table.append(key)
        # print(len(dummy_table))

        # OprfClient
        codewords = 128
        r = dummy_table
        if codewords < 128:
            raise ValueError(f"codewords {codewords} is too small,"
                             f" it should be greater equal than 128 to ensure security")
        self._codewords = codewords

        self._r = np.empty((len(r), self._codewords), dtype=np.uint8)  # _r = 1.2n x 512
        codewords_bytes = int_to_bytes(self._codewords)
        # 将r中的字节转换为位数组，len(_r) = 1.2n _r = C(r)
        for i, word in enumerate(r):
            word_arr = bytes_to_bit_arr(codewords_bytes + self._encode(word))
            self._r[i] = word_arr  # 1.2n x 512

    async def prepare(self):
        # self.oprf_client.prepare()

        session = aiohttp.ClientSession()

        m = self._r.shape[0]  # 1.27n
        self._t = rand_binary_arr((m, self._codewords))  # 1.27n x 128
        u = self._t ^ self._r  # t1 = t0 ^ C(r)
        if self._codewords == 128:
            for i in range(self._codewords):
                ti_bytes = bit_arr_to_bytes(self._t[:, i])
                ui_bytes = bit_arr_to_bytes(u[:, i])
                # 发送 t1和t0
                #
                await send(ti_bytes, ui_bytes, self.handler, session)
        else:
            sender = Sender(self.handler,128)

            await sender.prepare()

            for i in range(self._codewords):
                # start = time.time()

                ti_bytes = bit_arr_to_bytes(self._t[:, i])
                ui_bytes = bit_arr_to_bytes(u[:, i])

                # print(f"per data prepare cost {time.time() - start}")
                # start = time.time()

                await sender.send(ti_bytes, ui_bytes)

        await session.close()

    async def intersect(self) -> List[bytes]:
        start = time.time()
        peer_byte_vals = [None] * 3
        # peer_tables = [set() for _ in range(3)]
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
        logging.info(f"client接收加密1后数据所用时间为 {end - start} 秒")
        # for table in peer_tables:
        #     print(len(table))
        start = time.time()
        start1 = time.time()
        res = []
        cnt = 0
        for i, (key, hash_index) in enumerate(zip(self.table, self.table_hash_index)):
            if key is not None:
                # peer_table = peer_tables[hash_index - 1]
                local_val = self.eval(i)
                if local_val in peer_tables:
                    res.append(key.decode('utf-8'))
        end1 = time.time()
        logging.info(f"client求交数据所用时间为 {end1 - start1} 秒")

        await self.handler.send_data_flow(res)
        # await mpc.transfer(b"end", sender_receivers={0: [1], 1: [0]})
        end = time.time()
        logging.info(f"client求交并发送求交所得数据所用时间为{end - start}秒")
        # print(len(res))
        return res

    def _encode(self, data: bytes):
        shake = SHAKE256.new(data)
        length = (self._codewords + 7) // 8
        return shake.read(length)

    @property
    def max_count(self) -> int:
        if self._r is None:
            return 0
        return self._r.shape[0]

    def eval(self, i: int) -> bytes:
        if i >= self.max_count:
            raise IndexError(f"i is greater than oprf instance count {self.max_count}")
        ti = self._t[i, :]
        return SHA256.new(bit_arr_to_bytes(ti)[4:]).digest()


async def main(local_port, remote_ip, remote_port,
               read_path, save_path, inter):
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

    df = read_csv(read_path)
    target_col = df[inter]
    data = [item.rstrip().encode('utf-8') for item in target_col]

    start_time = time.time()

    start = time.time()
    bob = Bob(data, data_handler, remote_ip, remote_port)
    logging.info(f"初始化+哈希运行时间：{time.time() - start} 秒")

    # 本地准备好后启动连接
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
