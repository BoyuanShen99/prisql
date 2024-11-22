import numpy as np

from typing import Union, Sequence
from .funtions import rand_binary_arr, bit_arr_to_bytes, int_to_bytes
from .send import send
from .recv import decrypt, unpack


class Receiver(object):
    _r: np.ndarray  # 1-d uint8 array of 0 and 1, select bits for m OTs, length is m
    _t: np.ndarray  # OT extension matrix, shape: m * k
    _index: int = 0
    _codewords: int  # codewords length, matrix q's width, should be greater equal than 128 (for security)

    def __init__(self, r: Sequence[Union[int, bool]],
                 handler, codewords: int = 128,
                 ):
        self._r = np.array(r, dtype=np.uint8)

        self.handler = handler

        if codewords < 128:
            raise ValueError(
                f"codewords {codewords} is too small,"
                f" it should be greater equal than 128 to ensure security"
            )
        self._codewords = codewords

    async def prepare(self):
        m = self._r.size
        self._t = rand_binary_arr((m, self._codewords))  # 512 x 128

        # col(u) = col(t) xor r
        # u = [128x512 ^ 512].T = 512 x 128
        u = (self._t.T ^ self._r).T
        if self._codewords == 128:
            for i in range(self._codewords):
                t_col_bytes = bit_arr_to_bytes(self._t[:, i])
                u_col_bytes = bit_arr_to_bytes(u[:, i])
                # 发送一列
                await send(t_col_bytes, u_col_bytes, self.handler)
        else:
            from .sender import Sender

            sender = Sender(self.handler, 128)
            await sender.prepare()
            for i in range(self._codewords):
                t_col_bytes = bit_arr_to_bytes(self._t[:, i])
                u_col_bytes = bit_arr_to_bytes(u[:, i])
                # ote发送

                await sender.send(t_col_bytes, u_col_bytes)

    def is_available(self):
        return self._t is not None and self._index < self._r.size

    @property
    def max_count(self) -> int:
        if self._r is None:
            return 0
        return self._r.shape[0]

    async def recv(self):
        key = int_to_bytes(self._index) + bit_arr_to_bytes(self._t[self._index, :])

        # todo 加密消息 接收
        await self.handler.received_data_event.wait()
        c_pack = self.handler.data
        self.handler.consume_data()

        cipher_m = unpack(c_pack)[self._r[self._index]]
        res = decrypt(key, cipher_m)
        self._index += 1
        return res
