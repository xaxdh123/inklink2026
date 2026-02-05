import shutil
import subprocess
from datetime import datetime
from trayapp import constant
from qcloud_cos import CosConfig
from qcloud_cos import CosS3Client
import sys
import json
import os
import logging
import hashlib
from pathlib import Path

md5_hash = hashlib.md5()
# 正常情况日志级别使用 INFO，需要定位时可以修改为 DEBUG，此时 SDK 会打印和服务端的通信信息
logging.basicConfig(level=logging.ERROR, stream=sys.stdout)

app_dir = Path(__file__).parent.parent
config = CosConfig(
    Region=constant.COS_REGION,
    SecretId=constant.COS_SECRET_ID,
    SecretKey=constant.COS_SECRET_KEY,
)
client = CosS3Client(config)
ver_dir = app_dir / constant.DIR_NEW_VERSION
if not os.path.exists(ver_dir):
    os.mkdir(ver_dir)


def download_single_file(key, path: Path = ver_dir, callback=None):
    def report(finished, total):
        if callback:
            callback(key, finished, total)

    path.parent.mkdir(parents=True, exist_ok=True)

    client.download_file(
        Bucket=constant.COS_BUCKET, Key=key, DestFilePath=path, progress_callback=report
    )


def get_single_file(key):
    return client.head_object(Bucket=constant.COS_BUCKET, Key=key)


def object_exists(key):
    return client.object_exists(Bucket=constant.COS_BUCKET, Key=key)


def get_app_version_info(app_key):
    """
    通过 COS Select 检索单条 App 版本信息并返回 JSON 对象
    """
    # SQL 语句：筛选指定 key 的对象
    sql_expression = f"""
    SELECT * FROM COSObject WHERE id = '{app_key}';
    """
    try:
        response = client.select_object_content(
            Bucket=constant.COS_BUCKET,
            Key=constant.COS_MAIN_FILE,
            ExpressionType="SQL",
            Expression=sql_expression,
            InputSerialization={"JSON": {"Type": "DOCUMENT"}},
            # 这里定义了记录间用 \n 分隔
            OutputSerialization={"JSON": {"RecordDelimiter": "\n"}},
        )

        results = ""
        # 提取事件流中的数据
        for event in response["Payload"]:
            if "Records" in event:
                # Payload 可能是分片传输的，需要累加
                results += event["Records"]["Payload"].decode("utf-8")

        # 核心逻辑：
        # 1. strip() 去掉末尾的 \n
        # 2. 如果 SQL 匹配到了数据，results.strip() 就是一个合法的 JSON 字符串
        clean_results = results.strip()

        if clean_results:
            return json.loads(clean_results)
        else:
            print(f"未找到 key 为 '{app_key}' 的配置信息")
            return None

    except json.JSONDecodeError as je:
        print(f"JSON 解析失败: {je}，原始数据: {results}")
        return None
    except Exception as e:
        print(f"COS 检索异常: {e}")
        return None


def md5_single(path):
    md5_hash = hashlib.md5()
    # dict[rel_path] = os.path.getmtime(join)
    with open(path, "rb") as file:
        # Read and update hash in chunks of 4K
        for byte_block in iter(lambda: file.read(4096), b""):
            md5_hash.update(byte_block)
    return md5_hash.hexdigest()


def count_files_in_dir(directory: str, extension: str = ".js") -> str:
    """统计目录下指定后缀的文件数量及最近更新时间"""
    count = 0
    last_time = datetime.fromtimestamp(0)
    if not os.path.exists(directory):
        return f"数量： {count}    最近更新时间：无"
    for root, _, files in os.walk(directory):
        for file in files:
            if file.lower().endswith(extension):
                count += 1
                file_path = os.path.join(root, file)
                date_mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
                last_time = max(date_mtime, last_time)
    time_str = last_time.strftime("%Y-%m-%d %H:%M:%S") if count > 0 else "无"
    return f"数量： {count}    最近更新时间：{time_str}"


def get_file_list(prefix):
    """列举 COS 前缀下所有对象，自动处理分页。"""
    marker = ""
    content = []
    while True:
        response = client.list_objects(
            Bucket=constant.COS_BUCKET, Prefix=prefix, Marker=marker, MaxKeys=100
        )
        if "Contents" in response:
            content.extend(response["Contents"])
        # IsTruncated=false 表示已取完全部分页
        if response["IsTruncated"] == "false":
            break
        marker = response["NextMarker"]
    return content


def download_file(i, count, key):
    ver_file = os.path.join(ver_dir, key)
    if key.endswith("/"):
        if not os.path.exists(ver_file):
            os.makedirs(ver_file)
        return None
    else:
        temp_dir = os.path.split(ver_file)[0]
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir)
        client.download_file(Bucket=constant.COS_BUCKET, Key=key, DestFilePath=ver_file)
        name = os.path.split(key)[1]
        res = f"{name} {i+1}/{count} 下载进度：{(i+1)*100//count}%"
        return res


def copy_folder(source_folder, destination_folder):
    if not os.path.exists(destination_folder):
        os.makedirs(destination_folder)
    for item in os.listdir(source_folder):
        source = os.path.join(source_folder, item)
        destination = os.path.join(destination_folder, item)
        if os.path.isdir(source):
            copy_folder(source, destination)
        else:
            shutil.copy2(source, destination_folder)
