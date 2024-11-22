import os
from typing import List

from functions.bc22.communication.PPRF.prg import prg, prg_to_finite_field


class GGMTree:
    def __init__(self, height: int, field: int, k_len):
        self.height = height
        self.field = field
        self.k_len = k_len
        self.tree = [None] * (2 ** height - 1)

    def gene_tree(self, key: bytes):
        if len(key) != self.k_len:
            self.tree[0] = prg(key, self.k_len)[:self.k_len]  # 根节点
        else:
            self.tree[0] = key
        for level in range(1, self.height):
            start_index = 2 ** level - 1
            end_index = 2 ** (level + 1) - 1
            for index in range(start_index, end_index):
                parent_index = (index - 1) // 2
                parent_key = self.tree[parent_index]
                if level < self.height - 1:
                    prg_output = prg(parent_key, self.k_len *2)
                    self.tree[index] = prg_output[:self.k_len] if index % 2 == 0 else prg_output[self.k_len:]
                else:
                    self.tree[index] = prg_to_finite_field(parent_key, self.field)[index % 2]

    def nodes_in_level(self, level: int) -> List[int]:
        start_index = 2 ** level - 1
        end_index = 2 ** (level + 1) - 1
        return self.tree[start_index:end_index]

    def insert_node(self, l: int, pos: int, val: bytes):
        # todo 出问题
        start_index = 2 ** l - 1
        end_index = 2 ** (l + 1) - 1

        # 查找第 i+1 层的首个或第二个空白位置
        target_index = None
        count = 0
        for index in range(start_index, end_index):
            if self.tree[index] is None:
                if count == pos:
                    target_index = index
                    break
                count += 1

        if target_index is None:
            raise ValueError("No empty position found at the specified level.")

        # 插入值
        self.tree[target_index] = val

        # 根据 gene_tree 规则生成所有子节点，直到叶子层
        for level in range(l + 1, self.height):
            start_index = 2 ** level - 1
            end_index = 2 ** (level + 1) - 1
            for index in range(start_index, end_index):
                parent_index = (index - 1) // 2
                parent_key = self.tree[parent_index]
                if parent_key is None:
                    continue
                if level < self.height - 1:
                    prg_output = prg(parent_key, self.k_len * 2)
                    self.tree[index] = prg_output[:self.k_len] if index % 2 == 0 else prg_output[self.k_len:]
                else:
                    self.tree[index] = prg_to_finite_field(parent_key, self.field)[index % 2]


# Usage example
def main():
    key = os.urandom(32)
    tree = GGMTree(4, 100, 32)  # Assuming a height of 3 and field of 100

    test = os.urandom(32)
    tree.insert_node(1, 1, test)
    print("check")

    tree.gene_tree(key)

    for i in range(3):
        print(f"level {i}")
        level_key = tree.nodes_in_level(i)
        print(level_key)
        print(len(level_key[0]))



    print("check")


if __name__ == "__main__":
    main()
