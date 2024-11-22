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


async def send(m0: bytes, m1: bytes,
               handler, session,
               curve: str = "secp256r1"):
    sk = ECC.generate(curve=curve)
    pk = sk.public_key()

    pk_bytes = key_to_bytes(pk)
    # 发送公钥
    # todo 公钥 发送
    await handler.send_bytes_in_session(key_to_bytes(pk), session)
    # print(pk_bytes, "发送公钥成功")

    # todo 对方公钥 接收
    await handler.received_data_event.wait()
    bk_bytes = handler.data
    handler.consume_data()
    # 接受公钥（根据s的每一位更改）
    bk = bytes_to_key(bk_bytes)

    # cipher key for m0 and m1
    ck0 = bk.pointQ * sk.d
    ck1 = (-pk.pointQ + bk.pointQ) * sk.d
    # print("ck0, ck1",ck0, ck1)
    #  m0 = t0, m1 = t1
    cipher_m0 = encrypt(point_to_bytes(ck0), m0)
    cipher_m1 = encrypt(point_to_bytes(ck1), m1)
    # 发送选择后的t0/t1
    # print(cipher_m0, "cipher_m0")
    # print(cipher_m1, "cipher_m1")
    # todo 加密消息 发送
    await handler.send_bytes_flow_in_session(pack(cipher_m0, cipher_m1), session)
