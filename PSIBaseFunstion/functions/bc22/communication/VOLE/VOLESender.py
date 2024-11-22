import math
import pickle
import random
import time

import numpy as np

from functions.bc22.communication.PPRF.PPRFReceiver import PPRFReceiver
from functions.bc22.communication.VOLE.utils import sample_D_t_N

from functions.bc22.communication.VOLE.utils import np_to_bytes


class VOLESender:
    def __init__(self, handler, N, n, t, prime, r, lam):
        # N GGM tree最底层叶子数，GGMtree高度等于 log2(N) + 1
        # n 外面要用的向量长度
        # t 控制稀疏程度
        # prime r 值域控制
        self._N = N
        self._n = n
        self._t = t
        self._p = prime
        self._r = r
        self._lam = lam

        self._l = int(math.log2(N))

        self.handler = handler

        # 中间数据
        self._e = None
        self._S = None
        self._puncture_key = None
        self._H = None

    async def gen(self, session):
        # 需要参数生成
        # print("1")
        e = sample_D_t_N(self._p, self._N, self._t)

        S = np.where(e != 0)[0]
        y = np.empty(self._t, dtype=object)
        for i in range(len(S)):
            y[i] = e[S[i]]

        self._e = e
        self._S = S

        start = time.time()
        # print("start gene matrix H")
        # H = np.empty((self._N, self._n), dtype=object)
        #
        # for m in range(self._N):
        #     for n in range(self._n):
        #         H[m][n] = random.randint(0, self._p - 1)
        H = np.random.randint(0, 2, size=(self._N, self._n), dtype=np.int8)

        # print(f"vole gene matrix H {time.time() - start}")

        self._H = H
        # print(H)

        await self.handler.send_bytes_flow_in_session(np_to_bytes(H), session)

        all_puncture_key = []

        # 同态加密需要
        # await self.handler.received_data_event.wait()
        # e_x = pickle.loads(self.handler.data)
        # self.handler.consume_data()

        # 论文中方法，令p=2，省去reverse VOLE的调用
        await self.handler.received_data_event.wait()
        c = pickle.loads(self.handler.data)
        self.handler.consume_data()

        all_z = []

        # print("-------------")
        # print(f"e {e}")
        # print(f"S {S}")
        # print(f"y {y}")
        # start = time.time()
        # print("2")
        for i in range(self._t):
            # todo 修改参数
            pprf_receiver = PPRFReceiver(self.handler, self._l, self._p, self._r, self._lam, S[i])

            puncture_key = await pprf_receiver.transfer(session)
            # print(f"round {i}, punc key: {puncture_key}")

            all_puncture_key.append(puncture_key)
            z = [0] * self._t
            for j in range(self._t):
                if i == j:
                    # 当前轮次穿刺对象
                    z[j] = puncture_key[S[j]] + c[j]
                    # print(f"punc one {j} index {S[j]} res {z[j]}")
                else:
                    # 非当前轮次穿刺对象
                    z[j] = -puncture_key[S[j]]
                    # print(f"not punc {j} index {S[j]} res {z[j]}")
            all_z.append(z)

        # for z in all_z:
        #     print(z)
        # print(f"vole communication cost {time.time() - start}")
        sum_z = [0] * self._t
        for i in range(self._t):
            for z in all_z:
                sum_z[i] = (sum_z[i] + z[i]) % pow(self._p, self._r)

        # print("-------------")
        # print(f"c {c}")
        # print(f"sum_z {sum_z}")

        # 同态加密方法，z的准备

        # await self.handler.received_data_event.wait()
        # e_all_plain_key = pickle.loads(self.handler.data)
        # self.handler.consume_data()
        #
        # # e_z_list = [[0] * self._t for _ in range(self._l)]
        # e_sum_z = [0] * self._t
        # for e_plain_key in e_all_plain_key:
        #     for i in range(self._t):
        #         e_sum_z[i] += e_x * y[i] + e_plain_key[S[i]]
        #
        # await self.handler.send_bytes_flow(pickle.dumps(e_sum_z))
        #
        # await self.handler.received_data_event.wait()
        # self._sum_z = self.handler.data
        # self.handler.consume_data()

        sum_puncture_key = [0] * self._N
        for i in range(self._N):
            for puncture_key in all_puncture_key:
                sum_puncture_key[i] = (sum_puncture_key[i] + puncture_key[i]) % pow(self._p, self._r)

        # 这里有问题
        # print(f"before set {sum_puncture_key}")

        for i in range(self._t):
            sum_puncture_key[S[i]] = int(sum_z[i])

        # print(f"_after set {sum_puncture_key}")

        self._puncture_key = sum_puncture_key

        # 验证部分
        # print("--------------------------")
        # print(S)
        # print("--------------------------")
        # print(y)
        # print("--------------------------")
        # print(self._sum_z)
        #
        # await self.handler.send_bytes(pickle.dumps(S))
        # await self.handler.send_bytes(pickle.dumps(y))

        # 错误的单条计算z
        #     await self.handler.received_data_event.wait()
        #     e_plain_key = self.handler.data
        #     self.handler.consume_data()
        #
        #     e_needed_plain_key = e_plain_key[S[i]]
        #
        #     e_z = e_x * y[i] + e_needed_plain_key
        #
        #     await self.handler.send_data(e_z)
        #
        # await self.handler.received_data_event.wait()
        # z = self.handler.data
        # self.handler.consume_data()
        #
        # self._z = z
        # self.all_puncture_key = all_puncture_key

    def expand(self):

        v_0 = np.empty(self._N, dtype=object)
        for i in range(self._N):
            if i in self._S:
                v_0[i] = self._puncture_key[i]
            else:
                v_0[i] = -self._puncture_key[i]

        # 暂时放弃对矩阵计算结果的求模
        # 离谱，他完全不考虑矩阵运算带来的数值域变换问题吗
        u = np.matmul(self._e, self._H) % pow(self._p, self._r)
        v = np.matmul(-v_0, self._H) % pow(self._p, self._r)

        # print("-------------")
        # print(f"e {self._e}")
        # print(f"v_0 {-v_0}")
        # print(f"valid {(2 * self._e - v_0) % pow(self._p, self._r)}")
        #
        # print(f"u {u}")
        # print(f"v {v}")
        # print((2 * u + v) % pow(self._p, self._r))

        # valid_u = np.matmul(self._t * self._e, self._H) % pow(self._p, self._r)
        #
        # test_u1 = self._t * (np.matmul(self._e, self._H) % (self._t * self._p))
        # test_u2 = (np.matmul(self._t * self._e, self._H) % (self._t * self._p))
        # test_u3 = self._t * (np.matmul(self._e, self._H) % self._p)
        # print(valid_u)
        # print(test_u1)
        # print(test_u2)
        # print(test_u3)

        # print("----------------------")

        # 测试用
        # print((self._t * 2 * self._e - v_0) % pow(self._p, self._r))
        # # 当前不一致是求余操作带来的
        # print(np.matmul(((2 * self._t * self._e - v_0) % pow(self._p, self._r)), self._H) % pow(self._p, self._r))
        # print((np.matmul(2 * self._t * self._e, self._H) - np.matmul(v_0, self._H)) % pow(self._p, self._r))

        # 这样才行，对于结果还是要求模
        # print((2 * u + v) % pow(self._p, self._r))

        return u, v
