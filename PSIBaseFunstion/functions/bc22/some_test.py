# 同态加密库phe测试
# import pickle
#
# import phe as paillier
#
# # 初始化公钥和私钥
# public_key, private_key = paillier.generate_paillier_keypair()
#
# # 定义向量A和B
# A = [1, 2, 3, 4]
# B = [4, 3, 2, 1]
# x = 10  # 标量
#
# # 加密向量A和B
# encrypted_A = [public_key.encrypt(a) for a in A]
# encrypted_B = [public_key.encrypt(b) for b in B]
#
# print(encrypted_A[0])
# b_e_A_0 = pickle.dumps(encrypted_A[0])
# print(pickle.loads(b_e_A_0))
#
# # 进行线性运算 x*A + B
# encrypted_result = [x * enc_a + enc_b for enc_a, enc_b in zip(encrypted_A, encrypted_B)]
#
# # 解密结果
# result = [private_key.decrypt(enc_res) for enc_res in encrypted_result]
#
# print("计算结果:", result)
#
# a = 10
# e_a = public_key.encrypt(a)
# c = -5
# e_c = public_key.encrypt(c)
#
# print(private_key.decrypt(e_a + e_c))
#
# a = [3, 4, 7]
# x = 10
# b = [1, 2, 1]
#
# res = []
# e_x = public_key.encrypt(x)
# for i in range(len(a)):
#     res.append(e_x * a[i] + public_key.encrypt(-b[i]))
#
# for e in res:
#     print(private_key.decrypt(e))
#
# print("---------")
#
# print([x * a_i - b_i for a_i, b_i in zip(a, b)])
import numpy as np

# np编码解码测试

# import pickle
# import numpy as np
#
# def np_to_bytes(arr: np.ndarray) -> bytes:
#     return pickle.dumps(arr)
#
# def bytes_to_np(byte_data: bytes) -> np.ndarray:
#     return pickle.loads(byte_data)
#
#
# # 示例：创建一个numpy数组
# arr = np.array([[2 ** 128 - 10, 2, 3], [4, 5, 6]], dtype=object)
#
# # 转换为字节流
# byte_data = np_to_bytes(arr)
#
# # 对字节流进行Base64编码（用于网络传输）
# # encoded_data = base64.b64encode(byte_data).decode('utf-8')
#
# # 发送encoded_data（例如通过网络）
#
# # 解码Base64编码的数据
# # decoded_data = base64.b64decode(encoded_data)
#
# # 将字节流转换回numpy数组
# decoded_array = bytes_to_np(byte_data)
#
# print(decoded_array)

u = np.array([5, 4, 10, 3, 2, 5, 7, 7, 3, 9])
v = np.array([62, 87, 74, 23, 98, 20, 32, 98, 72, 26])

print((2 * u + v) % 121)

# ans  [61 84 72 18 14 96 112 35 67 44]

import numpy as np

# 假设 p 和 q
p = 7
q = 100

# 向量 x, y, 矩阵 H
x = np.array([2, 3])
y = np.array([1, 1])

# 模 p 下的矩阵 H
H = np.array([[1, 2], [3, 4]])

# 计算 a = x, b = x - y
a = x % p
b = (x - y) % q

# 计算 aH % p 和 bH % q
aH = np.matmul(a, H) % p
bH = np.matmul(b, H) % q

# 计算差值
diff = (aH - bH) % q

print(f"aH mod p: {aH}")
print(f"bH mod q: {bH}")
print(f"Difference mod q: {diff}")

print(a - b)
print(np.matmul(a - b, H) % q)


a = np.array([191, 286])
b = np.array([3683, 1203])

x = 3026
res = (x * a + b) % pow(17, 3)
# [1915 1951]
print(res)
