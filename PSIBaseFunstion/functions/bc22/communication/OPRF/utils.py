import hashlib


def finite_field_to_bytes(value, prime):
    """
    将有限域中的元素转换为字节表示。
    value: 有限域中的元素
    prime: 有限域的模数
    """
    # 将元素表示为大端字节序
    byte_len = (prime.bit_length() + 7) // 8
    return value.to_bytes(byte_len, byteorder='big')


def eval_hash(x_p, x_q, p, q, v):
    """
    构建哈希函数 H: F_p × F_q → {0, 1}^v
    x_p: F_p 中的元素
    x_q: F_q 中的元素
    p: F_p 的模数
    q: F_q 的模数
    v: 输出的字节长度
    """
    # 将 F_p 和 F_q 中的元素转换为字节表示
    x_p_bytes = finite_field_to_bytes(x_p, p)
    x_q_bytes = finite_field_to_bytes(x_q, q)

    # 拼接两个字节串
    input_bytes = x_p_bytes + x_q_bytes

    # 使用 SHAKE256 生成 v 比特的哈希值
    shake = hashlib.shake_256()
    shake.update(input_bytes)

    hash_output = shake.digest(v)

    return hash_output
