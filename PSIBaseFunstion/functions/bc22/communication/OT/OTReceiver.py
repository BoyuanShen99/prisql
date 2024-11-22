import random
import time

from functions.bc22.communication.handler import DataHandler
from functions.bc22.utils.funtions import getHash, decrypt


# 只负责bytes信息收发，真实类型由外部控制
class OTReceiver:
    def __init__(self, handler: DataHandler, choice):
        self._p = None
        self._g = None
        self._b = random.randint(2 ** 127, 2 ** 128 - 1)

        self.handler = handler
        self.choice = choice

    async def transfer(self, session):
        # print("accept parameter")
        # 公共参数交换

        await self.handler.received_data_event.wait()
        self._p = self.handler.data
        self.handler.consume_data()

        # print("accept g")
        await self.handler.received_data_event.wait()
        self._g = self.handler.data
        self.handler.consume_data()

        # print("accept key")
        # 接收对方公钥
        await self.handler.received_data_event.wait()
        g_a = self.handler.data
        self.handler.consume_data()

        # print("gene and send key")
        # 生成自己公钥
        g_b = pow(self._g, self._b, self._p) \
            if self.choice == 0 else g_a * pow(self._g, self._b, self._p)
        await self.handler.send_data_in_session(g_b, session)

        # 本地保留密钥
        key = str(pow(g_a, self._b, self._p)).encode("utf-8")
        local_key = getHash(key)

        # 等待加密数据
        await self.handler.received_data_event.wait()
        encrypted_m0 = self.handler.data
        self.handler.consume_data()

        await self.handler.received_data_event.wait()
        encrypted_m1 = self.handler.data
        self.handler.consume_data()

        target_message = decrypt(local_key, encrypted_m0 if self.choice == 0 else encrypted_m1)

        return target_message
