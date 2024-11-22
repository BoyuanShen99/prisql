import pickle
import random
import time

import numpy as np
from .utils import eval_hash
from functions.bc22.communication.VOLE.VOLEReceiver import VOLEReceiver


class OPRFSender:
    def __init__(self, handler, N, n, t, prime, r, lam):
        self._n = n
        # VOLE 必须参数
        self._N = N
        self._r = r
        self._p = prime
        self._t = t
        self._lam = lam

        # VOLE 结果
        self._delta = None
        self._w = None
        self._v_t = None

        self.handler = handler

    async def transfer(self, session):
        delta = random.randint(1, pow(self._p, self._r))
        self._delta = delta
        beta = np.array([random.randint(0, self._p - 1) for _ in range(self._t)])
        vole_receiver = VOLEReceiver(self.handler, delta, beta, self._N, self._n, self._t, self._p, self._r, self._lam)

        start = time.time()
        await vole_receiver.gen(session)
        print(f"vole gen need {time.time() - start}")

        start = time.time()
        self._w = vole_receiver.expand()
        print(f"vole expand need {time.time() - start}")

        # print("------------------")
        # print(self._delta)
        # print(self._w)
        # print("------------------")

        await self.handler.received_data_event.wait()
        self._v_t = pickle.loads(self.handler.data)
        self.handler.consume_data()

        self.handler = None

    def eval(self, i, y):
        # 这里需指定下标，给定要计算的元素, 单个数值点
        return eval_hash(int(y), int((self._w[i] - self._delta * (self._v_t[i] + y)) % pow(self._p, self._r)),
                         pow(self._p, self._r), pow(self._p, self._r), self._lam)
