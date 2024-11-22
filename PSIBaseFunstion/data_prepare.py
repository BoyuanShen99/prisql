import argparse
import asyncio

from ecdsa import SECP256k1

from functions.ecdh.entrance import data_prepare as ecdh_data_prepare
from functions.kkrt import Alice_entrance as kkrt_a_entrance, Bob_entrance as kkrt_b_entrance
from functions.bc22 import Alice_entrance as bc22_a_entrance, Bob_entrance as bc22_b_entrance


async def main(rule, proto, read_path, store_path, inter, curve=None):
    if rule == 0:
        # Sender
        if proto == "ecdh":
            await ecdh_data_prepare(read_path, store_path, inter, curve)
        elif proto == "kkrt":
            # 实际上什么都不做
            kkrt_a_entrance.data_prepare(read_path, store_path, inter)
        elif proto == "bc22":
            # 实际上什么都不做
            bc22_a_entrance.data_prepare(read_path, store_path, inter)
        else:
            raise ValueError("Invalid protocol name.")
    elif rule == 1:
        # Receiver
        if proto == "ecdh":
            await ecdh_data_prepare(read_path, store_path, inter, curve)
        elif proto == "kkrt":
            kkrt_b_entrance.data_prepare(read_path, store_path, inter)
        elif proto == "bc22":
            bc22_b_entrance.data_prepare(read_path, store_path, inter)
        else:
            raise ValueError("Invalid protocol name.")

    else:
        raise ValueError("Invalid rule value. Must be 0 or 1.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Host')
    parser.add_argument('--rule', type=int, required=True, help='0-sender, 1-receiver')
    parser.add_argument('--proto', type=str, required=True, help='protocol name')
    parser.add_argument('--read-path', type=str, required=True, help='path of file to intersection')
    parser.add_argument('--store-path', type=str, required=True, help='path to store data prepare result')
    parser.add_argument('--inter', type=str, required=True, help='intersection column')
    parser.add_argument('--curve', type=str, default="SECP256k1", help='curve type for ecdh')

    args = parser.parse_args()

    if args.curve == "SECP256k1":
        curve = SECP256k1
    else:
        curve = None
        raise ValueError("Unsupported curve type")

    asyncio.run(main(args.rule, args.proto, args.read_path, args.store_path, args.inter, curve))
