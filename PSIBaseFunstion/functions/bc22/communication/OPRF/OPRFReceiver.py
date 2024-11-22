import math
import pickle

from functions.bc22.communication.OPRF.utils import eval_hash
from functions.bc22.communication.VOLE.VOLESender import VOLESender


class OPRFReceiver:
    def __init__(self, handler, N, n, t, prime, r, lam, x):
        self._N = N
        self._n = n
        self._t = t
        self._p = prime
        self._r = r
        self._lam = lam

        self._l = int(math.log2(N)) + 1

        self._x = x

        self.handler = handler

        self._v = None
        self._u = None

    async def transfer(self, session):
        vole_sender = VOLESender(self.handler, self._N, self._n, self._t, self._p, self._r, self._lam)

        # start = time.time()
        await vole_sender.gen(session)
        # print(f" oprf gen cost {time.time() - start}")

        self._u, self._v = vole_sender.expand()

        # print("------------------")
        # print(self._u)
        # print(self._v)
        # print("------------------")

        # v_t = (self._u - self._x) % pow(self._p, 2)
        # todo 抽象问题
        v_t = (self._u - self._x) % pow(self._p, self._r)

        await self.handler.send_bytes_flow_in_session(pickle.dumps(v_t), session)

    def eval(self):
        res = []
        for i in range(self._n):
            res.append(eval_hash(int(self._x[i]), int(self._v[i]),
                                 pow(self._p, self._r), pow(self._p, self._r), self._lam))

        return res
