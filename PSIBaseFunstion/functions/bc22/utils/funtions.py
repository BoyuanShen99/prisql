import csv
import hashlib
import secrets
import numpy as np

from functools import reduce
from operator import mul
from typing import Tuple, Union
from Crypto.Hash import SHAKE256, SHA256
from cryptography.hazmat.primitives.asymmetric import rsa


def generate_large_prime(bits):
    key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=bits
    )
    return key.private_numbers().p


# 加解密，可用于任意长度bytes对象
def encrypt(secret: bytes, plaintext: bytes):
    shake = SHAKE256.new(secret)
    key = shake.read(len(plaintext))

    int_key = int.from_bytes(key, "big")
    int_pt = int.from_bytes(plaintext, "big")

    int_ct = int_key ^ int_pt
    return int_ct.to_bytes(len(plaintext), "big")


def decrypt(secret: bytes, ciphertext: bytes):
    shake = SHAKE256.new(secret)
    key = shake.read(len(ciphertext))

    int_key = int.from_bytes(key, "big")
    int_ct = int.from_bytes(ciphertext, "big")

    int_pt = int_key ^ int_ct
    return int_pt.to_bytes(len(ciphertext), "big")


def getHash(val):
    m = hashlib.md5()
    m.update(val)
    return m.hexdigest().encode("utf-8")


def chunkify(lst, n):
    # 将列表 lst 分割成 n 个块
    return [lst[i::n] for i in range(n)]


# 以下三个都是为BC22准备的
def pad_to_fixed_length(m_bytes, length):
    # 检查长度是否超过目标长度
    if len(m_bytes) > length:
        raise ValueError(f"Encoded string exceeds {length} bytes.")

    # 使用 ljust 右侧填充空字节
    padded_bytes = m_bytes.ljust(length, b'\0')

    return padded_bytes


def unpad(padded_bytes):
    # 去除右侧的空字节
    unpadded_bytes = padded_bytes.rstrip(b'\0')

    return unpadded_bytes


def message_to_bytes(self, m):
    # todo 暂时先认为是256字节长度
    length = 256
    if isinstance(m, str):
        m = m.encode('utf-8')
        # 检查长度是否超过目标长度
        m = pad_to_fixed_length(m, length)

        return m
    elif isinstance(m, bytes):
        m = pad_to_fixed_length(m, length)

        return m
    elif isinstance(m, int):
        m = m.to_bytes(length, "big")
        return m


def hash_to_finite_int(bytes_item, field):
    shake = SHAKE256.new(bytes_item)
    hash_res = shake.read(len(bytes_item))

    hash_int = int.from_bytes(hash_res, "big") % field

    return hash_int

# todo 旧的 待删


# 生成一个随机的二进制数组
def rand_binary_arr(shape: Union[int, Tuple[int, ...]]):
    if isinstance(shape, int):
        size = shape
    else:
        size = reduce(mul, shape)
    bs = secrets.randbits(size).to_bytes((size + 7) // 8, "big")
    res = bytes_to_bit_arr(int_to_bytes(size) + bs)
    res.resize(shape)
    return res


def bit_arr_to_bytes(arr: np.ndarray) -> bytes:
    """
    :param arr: 1-d uint8 numpy array
    :return: bytes, one element in arr maps to one bit in output bytes, padding in the left
    """
    n = arr.size
    pad_width = (8 - n % 8) % 8
    arr = np.pad(arr, pad_width=((pad_width, 0),), constant_values=0)
    bs = bytes(np.packbits(arr).tolist())

    return int_to_bytes(n) + bs


def bytes_to_bit_arr(data: bytes) -> np.ndarray:
    """
    :param data: bytes, first 4 bytes is array length, and the remaining is array data
    :return:
    """

    prefix_length = 4
    n = bytes_to_int(data[:prefix_length])
    while (n + 7) // 8 != len(data) - prefix_length:
        # todo 陷入循环

        prefix_length += 4
    arr = np.array(list(data[prefix_length:]), dtype=np.uint8)
    res = np.unpackbits(arr)[-n:]
    return res


def int_to_bytes(value: int):
    byte_length = (value.bit_length() + 7) // 8
    byte_length = (byte_length + 3) // 4 * 4
    byte_length = 4 if byte_length == 0 else byte_length
    return value.to_bytes(byte_length, "big")


def bytes_to_int(data: bytes):
    return int.from_bytes(data, "big")


def _encode(self, data: bytes) -> bytes:
    shake = SHAKE256.new(data)
    length = (self._codewords + 7) // 8
    return shake.read(length)


def pack_byte_data(byte_data_list):
    packed_data = b''.join(data for data in byte_data_list)
    return packed_data


def unpack_byte_data(packed_data, length):
    data_set = []
    offset = 0
    while offset + length < len(packed_data):
        data = packed_data[offset:offset + length]
        data_set.append(data)
        offset += length
    data_set.append(packed_data[offset:])
    return data_set
