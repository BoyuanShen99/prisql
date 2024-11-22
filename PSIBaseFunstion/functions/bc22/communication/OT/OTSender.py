import asyncio
import random

from functions.bc22.communication.handler import DataHandler
from functions.bc22.utils.funtions import getHash, encrypt, generate_large_prime


# 只负责bytes信息收发，真实类型由外部控制
class OTSender:
    def __init__(self, handler: DataHandler, messages, prime=None):
        # 生成元和安全素数
        self._g = None
        self._p = None
        # 128位随机数
        self._a = random.randint(2 ** 127, 2 ** 128 - 1)

        self.handler = handler
        self.m0, self.m1 = messages

        if prime is None:
            self.prepare()

        self._g = 2

    def prepare(self, bits=2048):
        # 生成安全素数
        # while True:
        #     q = number.getPrime(bits - 1)
        #     p = 2 * q + 1
        #     if number.isPrime(p):
        #         break

        # 替换素数生成函数 解决问题
        p = generate_large_prime(bits)
        self._p = p

    async def transfer(self, session):
        # print("exchange parameter")
        # 交换公共参数
        await self.handler.send_data_in_session(self._p, session)
        await self.handler.send_data_in_session(self._g, session)
        # print("send key")
        # 交换公钥
        g_a = pow(self._g, self._a, self._p)
        await self.handler.send_data_in_session(g_a, session)
        # print("receiver key")
        # 接收对方公钥
        await self.handler.received_data_event.wait()
        g_b = self.handler.data
        self.handler.consume_data()
        # print("process")
        # 数据加密密钥生成
        key_0 = str(pow(g_b, self._a, self._p)).encode("utf-8")
        key_1 = str(pow(g_b // g_a, self._a, self._p)).encode("utf-8")

        key_hashed_0, key_hashed_1 = getHash(key_0), getHash(key_1)

        # 加密数据并发送
        encrypted_m0 = encrypt(key_hashed_0, self.m0)
        encrypted_m1 = encrypt(key_hashed_1, self.m1)

        # 用bytes_flow传输
        await asyncio.sleep(0.005)
        await self.handler.send_bytes_flow_in_session(encrypted_m0, session)
        await self.handler.send_bytes_flow_in_session(encrypted_m1, session)

