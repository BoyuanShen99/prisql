import argparse
import asyncio
import logging
import multiprocessing
import random
import time

import aiohttp
import numpy as np
from aiohttp import web
from utils.io import read_csv, save_to_csv

from handler import DataHandler, EndHandler, wait_for_remote_host
from utils.recv import recv
from typing import List
from Crypto.Hash import SHAKE256, SHA256

from utils.cuckoo import position_hash
from utils.receiver import Receiver
from utils.funtions import rand_binary_arr, bit_arr_to_bytes, bytes_to_bit_arr, int_to_bytes, pack_byte_data

# 获取 aiohttp.access 记录器
aiohttp_access_logger = logging.getLogger('aiohttp.access')
# 设置记录器级别为 WARNING 或更高
aiohttp_access_logger.setLevel(logging.WARNING)
logging.basicConfig(level=logging.INFO)


def chunkify(lst, n):
    # 将列表 lst 分割成 n 个块
    return [lst[i::n] for i in range(n)]


class Alice(object):
    def __init__(self, words: List[bytes], handler, remote_ip, remote_port):
        self._q = None
        self.s = 0
        self.words = words
        self.handler = handler

        self.remote_ip = remote_ip
        self.remote_port = remote_port

        # self.oprf_server = OprfServer(pair, 512)

        codewords = 128
        if codewords < 128:
            raise ValueError(f"codewords {codewords} is too small,"
                             f" it should be greater equal than 128 to ensure security")
        self._codewords = codewords

    async def prepare(self):
        # self.oprf_server.prepare()

        session = aiohttp.ClientSession()

        self._s = rand_binary_arr(self._codewords)
        # q (keys)
        self._q = None
        m = 0
        q_cols = []

        if self._codewords == 128:
            # q (keys)
            for i, b in enumerate(self._s):
                start = time.time()

                q_col = await recv(b, self.handler, session)  # column of q, bytes of 0,1 arr
                # print(q_col, "q_col")
                if m == 0:
                    m = len(q_col)
                else:
                    assert m == len(q_col), f"base OT message length should be all the same, but the round {i} is not"
                q_cols.append(q_col)

                print(f"one round cost {time.time() - start}")
        else:
            receiver = Receiver(self._s, self.handler, 128)
            await receiver.prepare()

            for i in range(self._s.size):
                q_col = await receiver.recv()
                if m == 0:
                    m = len(q_col)
                else:
                    assert m == len(q_col), f"base OT message length should be all the same, but the round {i} is not"
                q_cols.append(q_col)

        await session.close()

        self._q = np.vstack([bytes_to_bit_arr(col) for col in q_cols]).T  # Q

    def process_words(self, params):
        i, words_chunk, n = params
        results = []
        for word in words_chunk:
            h = position_hash(i + 1, word, n)
            val = self.eval(h, word + bytes([i + 1]))
            results.append(val)
        return results

    def process_words_m(self, params):
        words_chunk, n = params
        results = []
        for i in range(3):
            for word in words_chunk:
                h = position_hash(i + 1, word, n)
                val = self.eval(h, word + bytes([i + 1]))
                results.append(val)
        return results

    async def intersect(self):
        temp_handler = self.handler
        self.handler = None

        words = random.sample(self.words, len(self.words))
        n = self._q.shape[0]
        num_processes = multiprocessing.cpu_count()
        words_chunks = list(chunkify(words, num_processes))
        # todo 可用版本
        # for i in range(3):
        #     vals = []
        #     process_args = [(i, chunk, n) for chunk in words_chunks]
        #
        #     with multiprocessing.Pool(processes=num_processes) as pool:
        #         results = pool.map(self.process_words, process_args)
        #
        #     vals = [val for sublist in results for val in sublist]
        vals = []
        process_args = [(chunk, n) for chunk in words_chunks]

        with multiprocessing.Pool(processes=num_processes) as pool:
            results = pool.map(self.process_words_m, process_args)

        vals = [val for sublist in results for val in sublist]

        # print("----------------------")
        # max_length = max(len(item) for item in vals)
        # min_length = min(len(item) for item in vals)
        # print(f"max {max_length}, min {min_length}")
        # 长度固定
        byte_vals = pack_byte_data(vals)

        start = time.time()
        self.handler = temp_handler
        await self.handler.send_data(len(vals[0]))
        await self.handler.send_bytes_flow(byte_vals)
        logging.info(f"net transfer cost {time.time() - start}")
        # self.handler = None
        #
        # self.handler = temp_handler

        res: List[bytes] = []
        word = []
        # while True:
        #     word = (await mpc.transfer("", sender_receivers={0: [1], 1: [0]}))[0]
        #     if word == b"end":
        #         break
        #     res.append(word)
        await self.handler.received_data_event.wait()
        res = self.handler.data
        self.handler.consume_data()
        return res

    def _encode(self, data: bytes) -> bytes:
        shake = SHAKE256.new(data)
        length = (self._codewords + 7) // 8
        return shake.read(length)

    @property
    def max_count(self) -> int:
        if self._q is None:
            return 0
        else:
            return self._q.shape[0]

    def _eval_op(self, i: int, enc_data: np.ndarray):
        qi = self._q[i, :]
        return qi ^ (self._s & enc_data)

    def eval(self, i: int, data: bytes) -> bytes:
        if i >= self.max_count:
            raise IndexError(f"i is greater than oprf instance count {self.max_count}")
        enc_data = self._encode(data)
        enc_data_arr = bytes_to_bit_arr(int_to_bytes(self._codewords) + enc_data)

        res = self._eval_op(i, enc_data_arr)
        return SHA256.new(bit_arr_to_bytes(res)[4:]).digest()


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

    # 读入本地数据
    # 已经是字符串
    df = read_csv(read_path)
    target_col = df[inter]
    data = [item.rstrip().encode('utf-8') for item in target_col]

    start_time = time.time()
    # 初始化alice
    alice = Alice(data, data_handler, remote_ip, remote_port)

    # 本地准备好后启动连接
    await wait_for_remote_host(remote_ip, remote_port)

    logging.info("start prepare")
    start = time.time()
    await alice.prepare()  # prepare stage
    logging.info(f"finish prepare, take {time.time() - start}")

    logging.info("start intersection")
    start = time.time()
    res = await alice.intersect()  # intersect stage, res is the intersection
    logging.info(f"finish intersection, take {time.time() - start}")
    logging.info(f"程序运行时间：{time.time() - start_time} 秒")

    # 本地处理
    res_strs = sorted(res)
    save_to_csv(res_strs, save_path, inter)

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
