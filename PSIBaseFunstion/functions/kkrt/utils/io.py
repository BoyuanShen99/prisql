import csv
import logging

import pandas as pd


def read_csv(file_path):
    try:
        return pd.read_csv(file_path)
    except FileNotFoundError:
        logging.error(f"文件 {file_path} 未找到")
        return pd.DataFrame()
    except Exception as e:
        logging.error(f"读取文件 {file_path} 时发生错误: {e}")
        return pd.DataFrame()

def save_to_csv(data, file_path, inter):
    try:
        with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow([inter])  # 首先写入列名
            for item in data:
                writer.writerow([item])  # 然后写入数据
    except Exception as e:
        print(f"保存文件 {file_path} 时发生错误: {e}")
