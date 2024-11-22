from functions.bc22.communication.OT.OTReceiver import OTReceiver

from functions.bc22.communication.PPRF.GGMTree import GGMTree
from functions.bc22.communication.PPRF.utils import xor_bytes


# 标准版PPRF，提供punctured key，注意bc22会进行后续加工
class PPRFReceiver:
    def __init__(self, handler, l, prime, r, lam, alpha):
        self.alpha = alpha
        self._l = l
        self._p = prime
        self._r = r
        self._lam = lam

        self.handler = handler

        self.tree = GGMTree(self._l + 1, pow(self._p, self._r), self._lam)

    async def transfer(self, session):
        puncture = None
        puncture_key = None
        for i in range(self._l):
            choice = 0 if self.alpha & (1 << (self._l - i - 1)) > 0 else 1
            ot_receiver = OTReceiver(self.handler, choice)

            secret = await ot_receiver.transfer(session)

            if i == self._l - 1:
                secret = int.from_bytes(secret, "big")
            curr_level_node_list = self.tree.nodes_in_level(i + 1)

            if i < self._l - 1:
                # 求的是目标节点的邻居节点的坐标同奇偶的其他节点的累加
                to_insert = secret
                if choice == 1:
                    for j in range(len(curr_level_node_list)):
                        if curr_level_node_list[j] is None:
                            continue
                        elif j % 2 == 1:
                            to_insert = xor_bytes(to_insert, curr_level_node_list[j])
                else:
                    for j in range(len(curr_level_node_list)):
                        if curr_level_node_list[j] is None:
                            continue
                        elif j % 2 == 0:
                            to_insert = xor_bytes(to_insert, curr_level_node_list[j])

                self.tree.insert_node(i + 1, choice, to_insert)
            else:
                # 同时也可以求出目标叶子节点邻居节点的值并且插入
                # l层是反的，求的是与目标叶子节点的坐标同奇偶的其他节点的累加
                await self.handler.received_data_event.wait()
                shared_c = self.handler.data
                self.handler.consume_data()

                s_sum = 0
                to_insert = secret
                if choice == 1:
                    for j in range(len(curr_level_node_list)):
                        if curr_level_node_list[j] is not None and j % 2 == 1:
                            to_insert = (to_insert - curr_level_node_list[j]) % pow(self._p, self._r)
                        elif curr_level_node_list[j] is not None and j % 2 == 0:
                            s_sum = (s_sum + curr_level_node_list[j]) % pow(self._p, self._r)
                else:
                    for j in range(len(curr_level_node_list)):
                        if curr_level_node_list[j] is not None and j % 2 == 0:
                            to_insert = (to_insert - curr_level_node_list[j]) % pow(self._p, self._r)
                        elif curr_level_node_list[j] is not None and j % 2 == 1:
                            s_sum = (s_sum + curr_level_node_list[j]) % pow(self._p, self._r)
                self.tree.insert_node(i + 1, choice, to_insert)
                puncture = (shared_c + secret + s_sum) % pow(self._p, self._r)

                puncture_key = self.tree.nodes_in_level(self._l)
                for j in range(len(puncture_key)):
                    if puncture_key[j] is None:
                        puncture_key[j] = puncture
                        break
        # 当前返回结果中puncture位置是beta - eval(alpha)
        return puncture_key
