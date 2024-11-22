# 伪随机生成器

import hashlib
import os
from Crypto.Hash import SHAKE256


def prg(seed, output_length):
    # # output_length是字节长度
    # # 使用 SHAKE-256 哈希函数进行两次调用
    # hash_func = hashlib.sha256
    #
    # # 生成第一个 l 位伪随机值
    # hash1 = hash_func(seed + b'0').digest()[:output_length]
    #
    # # 生成第二个 l 位伪随机值
    # hash2 = hash_func(seed + b'1').digest()[:output_length]
    #
    # # 将两个 l 位输出连接起来
    # return hash1 + hash2
    shake = SHAKE256.new(seed)
    return shake.read(output_length)



def prg_to_finite_field(seed, field, length=256):
    # 使用 SHA-256 哈希函数生成伪随机数
    shake = SHAKE256.new(seed)
    hash = shake.read(length * 2)

    while field > (1 << (length * 8)):
        length *= 2

    # 将哈希值转换为整数并取模 field
    value1 = int.from_bytes(hash[:length], 'big') % field

    # 将哈希值转换为整数并取模 field
    value2 = int.from_bytes(hash[length:], 'big') % field

    return value1, value2


def bytes_to_bitstring(byte_data):
    # 将字节数据转换为二进制字符串表示
    return ''.join(format(byte, '08b') for byte in byte_data)


def bitstring_to_bytes(bitstring):
    # 检查二进制字符串的长度是否是8的倍数
    if len(bitstring) % 8 != 0:
        raise ValueError("Bitstring length must be a multiple of 8")

    # 将二进制字符串按每8个字符分割成多个部分
    byte_chunks = [bitstring[i:i + 8] for i in range(0, len(bitstring), 8)]

    # 将每个8位的二进制字符串转换为对应的字节值，并组合成字节数据
    byte_data = bytes(int(byte, 2) for byte in byte_chunks)

    return byte_data


if __name__ == "__main__":
    # 设定种子的长度 l 和输出的总长度 2l
    l = 256  # 例如，l = 16 字节，即 128 位
    seed = os.urandom(l)
    output_length = l  # 每个哈希生成 l 长度的伪随机值

    output = prg(seed,  l * 2)
    seed_bitstring = bytes_to_bitstring(seed)
    output_bitstring = bytes_to_bitstring(output)

    print(seed)
    print(output)
    print(len(seed))
    print(len(output))

    print("Seed:", seed_bitstring)
    print("Output:", output_bitstring)
    print("Output Length:", len(output))  # 确认输出长度为 2l

    p = 5
    r = 3
    field = p ** r
    value1, value2 = prg_to_finite_field(seed, field)

    print(f"value1: {value1}, value2: {value2}")
