from Crypto.Hash import SHAKE256
from Crypto.PublicKey import ECC
from typing import Tuple


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


def point_to_bytes(point: ECC.EccPoint):
    xs = point.x.to_bytes()  # type: ignore
    ys = bytes([2 + point.y.is_odd()])  # type: ignore
    return xs + ys


def key_to_bytes(key: ECC.EccKey) -> bytes:
    if key.has_private():
        raise ValueError("only public key can be serialized to bytes to send")
    return key.export_key(format="DER", compress=True)  # type: ignore


def bytes_to_key(data: bytes) -> ECC.EccKey:
    return ECC.import_key(data)


def int_to_bytes(value: int):
    byte_length = (value.bit_length() + 7) // 8
    byte_length = (byte_length + 3) // 4 * 4
    byte_length = 4 if byte_length == 0 else byte_length
    return value.to_bytes(byte_length, "big")


def bytes_to_int(data: bytes):
    return int.from_bytes(data, "big")


def pack(m0: bytes, m1: bytes) -> bytes:
    return int_to_bytes(len(m0)) + m0 + m1


def unpack(m: bytes) -> Tuple[bytes, bytes]:
    m0_length = bytes_to_int(m[:4])
    m0 = m[4: 4 + m0_length]
    m1 = m[4 + m0_length:]
    return m0, m1


async def recv(b: int, handler, session) -> bytes:
    assert b == 0 or b == 1, "b should be 0 or 1"
    # 接收公钥
    # print("准备接收")
    # todo 对方公钥 接收
    await handler.received_data_event.wait()
    ak_bytes = handler.data
    handler.consume_data()

    # print(ak_bytes, "接收公钥成功")
    ak = bytes_to_key(ak_bytes)
    curve = ak.curve

    sk = ECC.generate(curve=curve)
    pk = sk.public_key()

    # choose point and pk
    if b == 1:
        point = pk.pointQ + ak.pointQ
        pk = ECC.EccKey(curve=curve, point=point)
    # send chosen public key
    # todo 公钥 发送
    await handler.send_bytes_in_session(key_to_bytes(pk), session)

    ck = ak.pointQ * sk.d
    # 接收经s选择后的t0/t1

    # todo 对方传回消息 接收
    await handler.received_data_event.wait()
    t_pack = handler.data
    handler.consume_data()
    cipher_m = unpack(t_pack)[b]

    res = decrypt(point_to_bytes(ck), cipher_m)
    return res
