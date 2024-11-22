import pickle
import random

import numpy as np


def sample_D_t_N(p, N, t):
    """
    从权重t错误分布 D_{t, N} 进行采样。

    参数:
    p -- 有限域 F_p 的素数 p
    N -- 向量空间 F_p^N 的维度
    t -- 错误向量中的非零元素个数

    返回:
    一个长度为 N 的向量，按照 D_{t, N} 分布进行采样
    """
    # 初始化向量为零
    vector = np.zeros(N, dtype=object)

    # 随机选择 t 个位置
    positions = np.random.choice(N, t, replace=False)

    # 在选定的位置插入随机非零元素
    for pos in positions:
        # 从 F_p 中随机选择一个非零元素
        non_zero_element = random.randint(1, p - 1)
        vector[pos] = non_zero_element

    return vector


# 将numpy数组转换为字节流
def np_to_bytes(arr: np.ndarray) -> bytes:
    return pickle.dumps(arr)

def bytes_to_np(byte_data: bytes) -> np.ndarray:
    return pickle.loads(byte_data)
