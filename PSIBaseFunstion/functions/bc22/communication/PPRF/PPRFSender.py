import time

from functions.bc22.communication.OT.OTSender import OTSender
from functions.bc22.communication.PPRF.GGMTree import GGMTree
from functions.bc22.communication.PPRF.utils import xor_bytes


# 标准版PPRF，提供plain_key
class PPRFSender:
    def __init__(self, handler, l, prime, r, lam, beta, k_pprf):
        # l OT 轮数，GGM Tree深度
        # prime, r 数据域定义参数，内部范围均是p^r
        # lam, key长度，也是节点包含值的长度，是PRG的参数
        # beta, 分享秘密参数
        # k_pprf GGM Tree生成树

        # 1. GGMTree准备
        # key = os.urandom(lam)
        # lam是指定字节数量
        assert len(k_pprf) == lam, f"need len {lam} key to gene GGM tree"
        self.tree = GGMTree(l + 1, pow(prime, r), lam)
        self.tree.gene_tree(k_pprf)

        self._p = prime
        self._r = r
        self._l = l
        self._lam = lam
        # 暂时不确定是外部生成还是内部随机
        # 改：beta是由外部生成的长度为t的数组，每次传入beta[i]，用于 VOLE gen 阶段，计算z
        self.beta = beta

        self.handler = handler

    def get_plain_key(self):
        return self.tree.nodes_in_level(self._l)

    async def transfer(self, session):
        shared_c = None

        for i in range(self._l):
            start = time.time()

            node_list = self.tree.nodes_in_level(i + 1)
            t_l = None
            t_r = None

            if i < self._l - 1:
                t_l = b''
                t_r = b''
                # 遍历列表中的每个元素
                for index, data in enumerate(node_list):
                    # index: 0, 2, 4,
                    if index % 2 == 0:
                        t_l = xor_bytes(t_l, data)
                    # index: 1, 3, 5
                    else:
                        t_r = xor_bytes(t_r, data)
            else:
                t_l = 0
                t_r = 0
                for index, data in enumerate(node_list):
                    # index: 0, 2, 4,……
                    if index % 2 == 0:
                        t_l = (t_l + data) % pow(self._p, self._r)
                    # index: 1, 3, 5，……
                    else:
                        t_r = (t_r + data) % pow(self._p, self._r)

                # todo 之前测试疏忽了，传输位数必须包含值域 p^r 256字节占有2048位
                # 改：传入beta为外部数组beta[i]，用于计算z的值
                shared_c = int((self.beta - t_l - t_r) % pow(self._p, self._r))
                t_l = t_l.to_bytes(256, "big")
                t_r = t_r.to_bytes(256, "big")

            ot_sender = OTSender(self.handler, (t_l, t_r))

            await ot_sender.transfer(session)
            if i == self._l - 1:
                await self.handler.send_data_in_session(shared_c, session)

            print(f"ot one round need {time.time() - start}")
