
def xor_bytes(a, b):
    max_len = max(len(a), len(b))
    a_padded = a.ljust(max_len, b'\x00')
    b_padded = b.ljust(max_len, b'\x00')
    return bytes([x ^ y for x, y in zip(a_padded, b_padded)])

