import math
import os
import pickle
import random
import time

import numpy as np

from functions.bc22.communication.PPRF.PPRFSender import PPRFSender

from functions.bc22.communication.VOLE.utils import bytes_to_np


class VOLEReceiver:
    # todo 修改参数
    def __init__(self, handler, x, beta, N, n, t, prime, r, lam):
        # 有些参数数外部传入还是怎么样需要再议
        self._n = n
        self.beta = beta
        self._N = N
        self._r = r
        self._p = prime
        self._t = t
        self._l = int(math.log2(N))

        self._x = x
        self._lam = lam
        # 中间生成
        self._H = None

        self._plain_key = None

        self.handler = handler

    async def gen(self, session):
        all_plain_key = []

        start = time.time()
        await self.handler.received_data_event.wait()
        H_bytes = self.handler.data
        self.handler.consume_data()

        self._H = bytes_to_np(H_bytes)

        print(f" H matrix need {time.time() - start}")

        # 上同态加密计算z
        # 同态加密需要
        # public_key, private_key = paillier.generate_paillier_keypair()
        # e_x = public_key.encrypt(self._x)
        #
        # await self.handler.send_bytes(pickle.dumps(e_x))

        # 论文中方法，令p=2，省去reverse VOLE的调用
        c = self._x * np.ones_like(self.beta) - self.beta
        await self.handler.send_bytes_in_session(pickle.dumps(c), session)
        # print("-------------")
        # print(f"beta {self.beta}")
        # print(f"c {c}")

        for i in range(self._t):
            start = time.time()
            # 每次生成新的GGM Tree
            # beta应该是没什么影响

            # 改：beta有重要影响，用于计算i，生成一个mod p 的长度为t的数组
            # beta = random.randint(10, 100)
            k_pprf = os.urandom(self._lam)
            # print(self._l, self._p, self._r, self._lam, self.beta[i])
            pprf_sender = PPRFSender(self.handler, self._l, self._p, self._r, self._lam, self.beta[i], k_pprf)

            await pprf_sender.transfer(session)

            plain_key = pprf_sender.get_plain_key()
            # print(f"round {i}, plain key: {plain_key}")
            all_plain_key.append(plain_key)

            print(f"pprf one round need {time.time() - start}")

        # 每次计算z_i（错误）
        # 重新思考后发现，确实是要累计计算z，以使得最后e - v_0 = v_1
        # 因为只支持同态加法，所以这里传递负值
        # e_all_plain_key = [[public_key.encrypt(-self._t * key) for key in plain_k] for plain_k in all_plain_key]
        #
        # # todo 小心数据量
        # await self.handler.send_bytes_flow(pickle.dumps(e_all_plain_key))
        #
        # await self.handler.received_data_event.wait()
        # e_sum_z = pickle.loads(self.handler.data)
        # self.handler.consume_data()
        #
        # sum_z = [(private_key.decrypt(e_z) // self._t) % pow(self._p, self._r) for e_z in e_sum_z]
        # # z_list.append(private_key.decrypt(e_z) % pow(self._p, self._r) for e_z in e_z_list)
        #
        # await self.handler.send_data(sum_z)

        sum_plain_key = [0] * self._N
        for i in range(self._N):
            for plain_key in all_plain_key:
                sum_plain_key[i] = (sum_plain_key[i] + plain_key[i]) % pow(self._p, self._r)

        self._plain_key = sum_plain_key

        # 验证部分
        # print("--------------------------")
        # print(self._x)
        #
        # for plain_key in all_plain_key:
        #     print(plain_key)
        #
        # await self.handler.received_data_event.wait()
        # temp_S = pickle.loads(self.handler.data)
        # self.handler.consume_data()
        #
        # await self.handler.received_data_event.wait()
        # temp_y = pickle.loads(self.handler.data)
        # self.handler.consume_data()
        #
        # print(temp_S)
        # print(temp_y)
        #
        # temp_sum_z = [0] * self._t
        # for plain_key in all_plain_key:
        #     for i in range(self._t):
        #         temp_sum_z[i] = (temp_sum_z[i] + self._x * temp_y[i] - plain_key[temp_S[i]]) % pow(self._p, self._r)
        # print(temp_sum_z)
        # print(sum_z)

    def expand(self):
        start = time.time()
        v_1 = np.empty(self._N, dtype=object)
        for i in range(self._N):
            v_1[i] = self._plain_key[i]

        print(f"gene v_1 cost {time.time() - start}")

        start = time.time()
        w = np.matmul(v_1, self._H)
        print(f"cal matrix w cost {time.time() - start}")
        # 测试用
        # print("-------------")
        # print(f"v1 {v_1}")
        # print(f"w {w % pow(self._p, self._r)}")
        # print(np.matmul(v_1, self._H) % pow(self._p, self._r))

        # 这样才行，对于结果还是要求模
        # print(w % pow(self._p, self._r))

        return w % pow(self._p, self._r)
