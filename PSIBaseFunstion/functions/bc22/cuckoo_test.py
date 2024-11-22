import os
import random

from bc22.utils.cuckoo import CuckooHashTable
from bc22.utils.funtions import pad_to_fixed_length

n = int(1.27 * 100)
s = 0
length = 16

words = ["hello", "world", "python", "programming"]

cuckoo = CuckooHashTable(n, s)
for word in words:
    cuckoo.update(word.rstrip().encode('utf-8'))
table = cuckoo.table
table_hash_index = cuckoo.table_hash_index

# 计算向量r
dummy_table = []
for key, hash_index in zip(table, table_hash_index):
    if key is None:
        key = os.urandom(length)
    else:
        key = key + bytes(hash_index)
        key = pad_to_fixed_length(key, length)

    dummy_table.append(key)

print("check")


