import argparse
import asyncio

from ecdsa import SECP256k1

from functions.ecdh.entrance import process as ecdh
from functions.kkrt import Alice_entrance as kkrt_a_entrance, Bob_entrance as kkrt_b_entrance
from functions.bc22 import Alice_entrance as bc22_a_entrance, Bob_entrance as bc22_b_entrance


async def main(rule, proto, store_path, save_path, inter, local_port, remote_ip, remote_port, curve=None):
    if rule == 0:
        # Sender
        if proto == "ecdh":
            await ecdh(store_path, save_path, inter, curve, local_port, remote_ip, remote_port)
        elif proto == "kkrt":
            await kkrt_a_entrance.process(store_path, save_path, inter, local_port, remote_ip, remote_port)
        elif proto == "bc22":
            await bc22_a_entrance.process(store_path, save_path, inter, local_port, remote_ip, remote_port)
        else:
            raise ValueError("Invalid protocol name.")
    elif rule == 1:
        # Receiver
        if proto == "ecdh":
            await ecdh(store_path, save_path, inter, curve, local_port, remote_ip, remote_port)
        elif proto == "kkrt":
            await kkrt_b_entrance.process(store_path, save_path, inter, local_port, remote_ip, remote_port)
        elif proto == "bc22":
            await bc22_b_entrance.process(store_path, save_path, inter, local_port, remote_ip, remote_port)
        else:
            raise ValueError("Invalid protocol name.")

    else:
        raise ValueError("Invalid rule value. Must be 0 or 1.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Host')
    parser.add_argument('--rule', type=int, required=True, help='0-sender, 1-receiver')
    parser.add_argument('--proto', type=str, required=True, help='protocol name')
    parser.add_argument('--store-path', type=str, required=True, help='path to save data prepare result')
    parser.add_argument('--save-path', type=str, required=True, help='path to save PSI result')
    parser.add_argument('--inter', type=str, required=True, help='intersection column')
    parser.add_argument('--local-port', type=int, default=8080, help='Local port to bind')
    parser.add_argument('--remote-ip', type=str, required=True, help='Remote host IP address')
    parser.add_argument('--remote-port', type=int, required=True, help='Remote host port')
    parser.add_argument('--curve', type=str, default="SECP256k1", help='curve type for ecdh')

    args = parser.parse_args()

    if args.curve == "SECP256k1":
        curve = SECP256k1
    else:
        curve = None
        raise ValueError("Unsupported curve type")

    asyncio.run(main(args.rule, args.proto, args.store_path, args.save_path,
                     args.inter, args.local_port, args.remote_ip, args.remote_port, curve))
