import urllib.request
from urllib.parse import urlparse
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import subprocess
import socket

def read_txt_to_array(file_name):
    """读取文本文件到数组"""
    try:
        with open(file_name, 'r', encoding='utf-8') as file:
            return [line.strip() for line in file.readlines()]
    except Exception as e:
        print(f"读取文件错误: {e}")
        return []

def check_url(url, channel_name, timeout=3):
    """检测URL响应时间"""
    start_time = time.time()
    success = False
    
    try:
        if url.startswith("http"):
            response = urllib.request.urlopen(url, timeout=timeout)
            if response.status == 200:
                success = True
        elif url.startswith("rtmp"):
            success = check_rtmp_url(url, timeout)
        else:
            # 其他协议跳过
            return None, False
            
        elapsed_time = (time.time() - start_time) * 1000  # 毫秒
        return elapsed_time, success
        
    except Exception as e:
        return None, False

def check_rtmp_url(url, timeout):
    """检测RTMP协议URL"""
    try:
        result = subprocess.run(['ffprobe', '-v', 'error', '-rtmp_transport', 'tcp', '-select_streams', 'v:0', 
                               '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', 
                               '-timeout', str(timeout * 1000000), url],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
        return result.returncode == 0
    except:
        return False

def process_channel(line):
    """处理单个频道"""
    if "://" not in line or "," not in line:
        return None, None
    
    try:
        name, url = line.split(',', 1)
        name = name.strip()
        url = url.strip()
        
        # 清理URL
        if '$' in url:
            url = url.split('$')[0]
        
        elapsed_time, is_valid = check_url(url, name)
        if is_valid and elapsed_time:
            return elapsed_time, f"{name},{url}"
            
    except Exception as e:
        print(f"处理频道错误: {e}")
    
    return None, None

def get_fastest_channels(input_file, output_file, top_n=3):
    """获取速度最快的频道"""
    
    # 读取所有频道
    channels = read_txt_to_array(input_file)
    if not channels:
        print("没有找到频道数据")
        return
    
    print(f"开始检测 {len(channels)} 个频道的速度...")
    
    # 多线程检测
    results = []
    with ThreadPoolExecutor(max_workers=50) as executor:
        futures = {executor.submit(process_channel, line): line for line in channels}
        
        for future in as_completed(futures):
            elapsed_time, result = future.result()
            if elapsed_time is not None:
                results.append((elapsed_time, result))
                print(f"检测成功: {result.split(',')[0]} - {elapsed_time:.0f}ms")
    
    # 按响应时间排序，取前N个
    if results:
        results.sort(key=lambda x: x[0])
        fastest_channels = results[:top_n]
        
        # 写入文件
        with open(output_file, 'w', encoding='utf-8') as f:
            for elapsed_time, channel in fastest_channels:
                name, url = channel.split(',', 1)
                f.write(f"{name},{url}\n")
                print(f"✓ {name} - {elapsed_time:.0f}ms")
        
        print(f"\n最快的 {top_n} 个频道已保存到: {output_file}")
    else:
        print("没有找到可用的频道")

def main():
    # 输入文件和输出文件
    input_file = "iptv_list.txt"  # 假设这是你的源文件
    output_file = "1.txt"
    
    # 如果输入文件不存在，创建一个示例文件测试
    if not os.path.exists(input_file):
        print(f"输入文件 {input_file} 不存在，创建示例数据...")
        create_sample_file(input_file)
    
    # 获取最快的3个频道
    get_fastest_channels(input_file, output_file, top_n=3)

def create_sample_file(filename):
    """创建示例测试文件"""
    sample_channels = [
        "CCTV1,http://example.com/cctv1",
        "CCTV5,http://example.com/cctv5", 
        "湖南卫视,http://example.com/hunan",
        "浙江卫视,http://example.com/zhejiang",
        "东方卫视,http://example.com/dongfang"
    ]
    
    with open(filename, 'w', encoding='utf-8') as f:
        for channel in sample_channels:
            f.write(channel + '\n')
    print(f"已创建示例文件: {filename}")

if __name__ == "__main__":
    main()
