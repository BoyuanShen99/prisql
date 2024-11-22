import csv
import secrets
import numpy as np

from functools import reduce
from operator import mul
from typing import Tuple, Union
from Crypto.Hash import SHAKE256, SHA256

def read_csv(file_path):
    try:
        with open(file_path, newline='', encoding='utf-8') as csvfile:
            reader = csv.reader(csvfile)
            return {row[0] for row in reader}
    except FileNotFoundError:
        print(f"文件 {file_path} 未找到")
        return set()
    except Exception as e:
        print(f"读取文件 {file_path} 时发生错误: {e}")
        return set()


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
    return data_set
