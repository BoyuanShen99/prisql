import argparse
import asyncio
import logging
import multiprocessing
import random
import time
from typing import List

import aiohttp
from aiohttp import web

from communication.OPRF.OPRFSender import OPRFSender
from communication.handler import DataHandler, EndHandler, wait_for_remote_host
from utils.cuckoo import position_hash
from utils.funtions import pack_byte_data, hash_to_finite_int, pad_to_fixed_length
from utils.io import read_csv, save_to_csv

# 获取 aiohttp.access 记录器
aiohttp_access_logger = logging.getLogger('aiohttp.access')
# 设置记录器级别为 WARNING 或更高
aiohttp_access_logger.setLevel(logging.WARNING)
logging.basicConfig(level=logging.INFO)


def chunkify(lst, n):
    # 将列表 lst 分割成 n 个块
    return [lst[i::n] for i in range(n)]


class Alice(object):
    def __init__(self, words: List[bytes], handler):

        self.oprf_sender = None
        self.words = words
        self.handler = handler

    async def prepare(self):
        timeout = aiohttp.ClientTimeout(total=None, connect=None, sock_connect=None, sock_read=None)
        session = aiohttp.ClientSession(timeout=timeout)

        await self.handler.received_data_event.wait()
        N, n, t, prime, r, lam = self.handler.data
        self.handler.consume_data()

        self.n = n
        self._p = prime
        self._r = r
        self._lam = lam

        self.oprf_sender = OPRFSender(self.handler, N, n, t, prime, r, lam)
        await self.oprf_sender.transfer(session)

        await session.close()

    def process_words(self, params):
        words_chunk, n = params
        results = []
        for i in range(3):
            for word in words_chunk:
                h = position_hash(i + 1, word, n)
                # print(f"{word} ({i + 1}) index {h}")
                # print(f"pad result {pad_to_fixed_length(word + bytes(i + 1), self._lam)}")

                val = self.eval(h, pad_to_fixed_length(word + bytes(i + 1), self._lam))

                results.append(val)
        return results

    async def intersect(self):
        temp_handler = self.handler
        self.handler = None

        words = random.sample(self.words, len(self.words))
        n = self.n

        start = time.time()
        num_processes = multiprocessing.cpu_count()
        words_chunks = list(chunkify(words, num_processes))

        process_args = [(chunk, n) for chunk in words_chunks]

        with multiprocessing.Pool(processes=num_processes) as pool:
            results = pool.map(self.process_words, process_args)

        vals = [val for sublist in results for val in sublist]

        # 长度固定
        byte_vals = pack_byte_data(vals)
        logging.info(f"finish local process cost {time.time() - start}")

        start = time.time()
        self.handler = temp_handler
        await self.handler.send_data(len(vals[0]))
        await self.handler.send_bytes_flow(byte_vals)
        logging.info(f"net transfer cost {time.time() - start}")

        res: List[bytes] = []
        word = []

        await self.handler.received_data_event.wait()
        res = self.handler.data
        self.handler.consume_data()
        return res

    def eval(self, i: int, data: bytes) -> bytes:
        value = hash_to_finite_int(data, pow(self._p, self._r))
        res = self.oprf_sender.eval(i, value)
        # print("----------")
        # print(value, res)

        return res

        # return self.oprf_sender.eval(i, hash_to_finite_int(data, pow(self._p, self._r)))


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

    # 读入本地数据
    start = time.time()
    df = read_csv(read_path)

    target_col = df[inter]
    data = [item.rstrip().encode('utf-8') for item in target_col]

    logging.info(f"read data cost {time.time() - start}")

    start_time = time.time()
    # 初始化alice
    alice = Alice(data, data_handler)

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

