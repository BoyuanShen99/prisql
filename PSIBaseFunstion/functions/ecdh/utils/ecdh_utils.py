import hashlib
import logging
from functools import partial
from multiprocessing import Pool, cpu_count
from ecdsa.ellipticcurve import Point

from time import time


def hash_to_curve(value, curve):
    """将值散列到曲线上某点"""
    digest = hashlib.sha256(value.encode()).digest()
    integer_value = int.from_bytes(digest, 'big')
    point = curve.generator * (integer_value % curve.order)
    return point


def encrypt(value, curve, sk):
    point = hash_to_curve(value, curve)
    encrypted = point * sk
    return encrypted


def parallel_encrypt(data_chunk, curve, sk):
    index, chunk = data_chunk
    return index, [encrypt(value, curve, sk) for value in chunk]


def parallel_re_encrypt(data_chunk, sk):
    index, chunk = data_chunk
    return index, [value * sk for value in chunk]


# hash
async def encrypt_dataset(values, curve, sk):
    logging.info("Encrypting data")
    start = time()
    # 使用进程池进行并行计算

    # 定义 chunk 大小
    chunk_size = len(values) // cpu_count()

    # 切分数据
    data_chunks = list(chunk_data(values, chunk_size))

    with Pool(cpu_count()) as pool:
        partial_encrypt = partial(parallel_encrypt, curve=curve, sk=sk)
        results = pool.map(partial_encrypt, data_chunks)

    results.sort(key=lambda x: x[0])
    encrypted_data = [item for _, sublist in results for item in sublist]
    logging.info(f"Data encrypted, use {time() - start}")
    return encrypted_data


async def re_encrypt_dataset(values, sk):
    logging.info("Re Encrypting data")
    start = time()
    # 使用进程池进行并行计算

    # 定义 chunk 大小
    chunk_size = len(values) // cpu_count()

    # 切分数据
    data_chunks = list(chunk_data(values, chunk_size))

    with Pool(cpu_count()) as pool:
        partial_encrypt = partial(parallel_re_encrypt, sk=sk)
        results = pool.map(partial_encrypt, data_chunks)

    results.sort(key=lambda x: x[0])
    encrypted_data = [item for _, sublist in results for item in sublist]
    logging.info(f"Data re encrypted, use {time() - start}")
    return encrypted_data


def chunk_data(data, chunk_size):
    for i in range(0, len(data), chunk_size):
        if i + chunk_size > len(data):
            yield i, data[i:]
        else:
            yield i, data[i:i + chunk_size]


async def encrypt_df(df, curve, sk):
    logging.info("Encrypting data")
    start = time()
    partial_encrypt = partial(encrypt, curve=curve, sk=sk)
    with Pool(cpu_count()) as pool:
        results = pool.map(partial_encrypt, df.values)
    logging.info(f"Data encrypted, use {time() - start}")
    return results


async def encrypt_df_apply(df, curve, sk):
    logging.info("Encrypting data")
    start = time()
    encrypted_data = df["fruit"].apply(encrypt, args=(curve, sk))
    logging.info(f"Data encrypted, use {time() - start}")
    return encrypted_data


def find_intersection(local_points, peer_points):
    peer_xy = {(p.x(), p.y()) for p in peer_points}
    local_xy = {(p.x(), p.y()) for p in local_points}

    intersection = peer_xy.intersection(local_xy)
    res = [idx for idx, p in enumerate(local_points) if (p.x(), p.y()) in intersection]

    return res


def dict_to_point(point_dict, curve):
    return Point(curve.curve, point_dict['x'], point_dict['y'])


def point_to_dict(point):
    return {'x': point.x(), 'y': point.y()}


def tuple_to_point(point_xy, curve):
    return Point(curve.curve, point_xy[0], point_xy[1])


def parallel_to_point(data_chunk, curve):
    index, chunk = data_chunk
    return index, [tuple_to_point(value, curve) for value in chunk]


def point_to_tuple(point):
    return point.x(), point.y()


def parallel_to_tuple(data_chunk):
    index, chunk = data_chunk
    return index, [point_to_tuple(value) for value in chunk]


async def transfer_to_tuple(values):
    logging.info("Transform data to tuple")
    start = time()
    # 使用进程池进行并行计算

    # 定义 chunk 大小
    chunk_size = len(values) // cpu_count()

    # 切分数据
    data_chunks = list(chunk_data(values, chunk_size))

    with Pool(cpu_count()) as pool:
        results = pool.map(parallel_to_tuple, data_chunks)

    results.sort(key=lambda x: x[0])
    xy_data = [item for _, sublist in results for item in sublist]
    logging.info(f"Data transformed, use {time() - start}")
    return xy_data


async def transfer_to_point(values, curve):
    logging.info("Transform data to tuple")
    start = time()
    # 使用进程池进行并行计算

    # 定义 chunk 大小
    chunk_size = len(values) // cpu_count()

    # 切分数据
    data_chunks = list(chunk_data(values, chunk_size))

    with Pool(cpu_count()) as pool:
        partial_transform = partial(parallel_to_point, curve=curve)
        results = pool.map(partial_transform, data_chunks)

    results.sort(key=lambda x: x[0])
    point_data = [item for _, sublist in results for item in sublist]
    logging.info(f"Data transformed, use {time() - start}")
    return point_data
