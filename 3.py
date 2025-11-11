import urllib.request
import urllib.error
import socket
import time
import re
from concurrent.futures import ThreadPoolExecutor

def test_stream_speed(url, timeout=5):
    """
    测试单个直播源的连接速度
    返回连接时间（秒），如果连接失败返回None
    """
    try:
        start_time = time.time()
        
        # 设置请求头
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Range': 'bytes=0-1024'  # 只请求少量数据测试连接
        }
        
        # 创建请求
        req = urllib.request.Request(url, headers=headers)
        
        # 发送请求并读取少量数据
        response = urllib.request.urlopen(req, timeout=timeout)
        data = response.read(1024)  # 只读取1KB数据测试连接
        response.close()
        
        connect_time = time.time() - start_time
        return connect_time
    
    except (urllib.error.URLError, socket.timeout, Exception) as e:
        return None

def parse_ptv_file(filename):
    """
    解析ptv_list.txt文件，按频道分组直播源
    """
    channels = {}
    
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            content = f.read()
    except:
        try:
            with open(filename, 'r', encoding='gbk') as f:
                content = f.read()
        except:
            print("无法读取文件，请检查文件路径和编码")
            return {}
    
    lines = content.split('\n')
    current_channel = "默认频道"
    channels[current_channel] = []
    
    for line in lines:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        
        # 检测是否是频道名称行
        if re.match(r'^[^,]+[,，]?$', line) and not line.startswith(('http://', 'https://', 'rtmp://', 'rtsp://')):
            # 如果是频道名称
            current_channel = line.split(',')[0].split('，')[0].strip()
            if current_channel not in channels:
                channels[current_channel] = []
        elif line.startswith(('http://', 'https://', 'rtmp://', 'rtsp://')):
            # 如果是URL
            channels[current_channel].append(line)
    
    return channels

def auto_group_channels(lines):
    """
    自动分组频道，支持多种格式
    """
    channels = {}
    
    for line in lines:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        
        # 处理格式：频道名称,URL
        if ',' in line and line.startswith(('http://', 'https://')):
            parts = line.split(',', 1)
            if len(parts) == 2:
                url, channel = parts[0], parts[1]
                if channel not in channels:
                    channels[channel] = []
                channels[channel].append(url)
        elif ',' in line and not line.startswith(('http://', 'https://')):
            parts = line.split(',', 1)
            if len(parts) == 2 and parts[1].startswith(('http://', 'https://')):
                channel, url = parts[0], parts[1]
                if channel not in channels:
                    channels[channel] = []
                channels[channel].append(url)
        elif line.startswith(('http://', 'https://')):
            # 只有URL，没有频道名称
            if "默认频道" not in channels:
                channels["默认频道"] = []
            channels["默认频道"].append(line)
        else:
            # 可能是频道名称
            channel_name = line
            if channel_name not in channels:
                channels[channel_name] = []
    
    return channels

def main():
    input_file = "ptv_list.txt"
    output_file = "1.txt"
    
    print("正在读取直播源文件...")
    
    # 读取文件
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except:
        try:
            with open(input_file, 'r', encoding='gbk') as f:
                lines = f.readlines()
        except:
            print("无法读取文件，请检查文件路径和编码")
            return
    
    # 解析频道
    channels = parse_ptv_file(input_file)
    
    # 如果解析结果不理想，尝试自动分组
    if len(channels) == 0 or (len(channels) == 1 and "默认频道" in channels and len(channels["默认频道"]) == 0):
        print("使用自动分组模式...")
        channels = auto_group_channels(lines)
    
    # 过滤空频道
    channels = {channel: urls for channel, urls in channels.items() if urls}
    
    print(f"发现 {len(channels)} 个频道")
    
    # 显示频道信息
    for channel_name, urls in channels.items():
        print(f"  {channel_name}: {len(urls)} 个直播源")
    
    # 测试每个频道的直播源速度
    speed_results = {}
    total_tested = 0
    successful_tests = 0
    
    print("\n开始测试直播源速度...")
    
    for channel_name, urls in channels.items():
        print(f"\n测试频道: {channel_name}")
        
        speed_tests = []
        
        # 使用多线程测试速度
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_url = {executor.submit(test_stream_speed, url): url for url in urls}
            
            for future in future_to_url:
                url = future_to_url[future]
                total_tested += 1
                try:
                    speed = future.result(timeout=10)
                    if speed is not None:
                        speed_tests.append((url, speed))
                        successful_tests += 1
                        print(f"  ✓ 连接成功 - 速度: {speed:.2f}秒")
                    else:
                        print(f"  ✗ 连接失败")
                except Exception as e:
                    print(f"  ✗ 测试超时或错误")
        
        # 按速度排序（从快到慢）
        speed_tests.sort(key=lambda x: x[1])
        speed_results[channel_name] = speed_tests
    
    # 生成输出文件
    print(f"\n正在生成结果文件: {output_file}")
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("# 直播源速度测试结果 - 按频道和速度排序\n")
        f.write(f"# 生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"# 总测试数: {total_tested}, 成功数: {successful_tests}\n")
        f.write("# 格式: 频道名称,播放地址,连接速度(秒)\n\n")
        
        # 按频道名称排序输出
        sorted_channels = sorted(speed_results.keys())
        
        for channel_name in sorted_channels:
            speed_list = speed_results[channel_name]
            if speed_list:
                f.write(f"# {channel_name} - 共{len(speed_list)}个有效源\n")
                
                for url, speed in speed_list:
                    # 简化输出，只保留频道和URL
                    f.write(f"{channel_name},{url}\n")
                
                f.write("\n")
    
    # 打印统计信息
    print(f"\n=== 测试完成 ===")
    print(f"输出文件: {output_file}")
    print(f"总测试直播源: {total_tested}")
    print(f"有效直播源: {successful_tests}")
    print(f"成功率: {successful_tests/total_tested*100:.1f}%" if total_tested > 0 else "0%")

# 简化版本
def simple_version():
    """
    简化版本，适合基础使用
    """
    input_file = "ptv_list.txt"
    output_file = "1.txt"
    
    print("简化版直播源速度测试")
    
    # 读取文件
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except:
        with open(input_file, 'r', encoding='gbk') as f:
            lines = f.readlines()
    
    results = []
    
    print("开始测试直播源速度...")
    
    for line in lines:
        line = line.strip()
        if line and not line.startswith('#') and line.startswith(('http://', 'https://')):
            try:
                start_time = time.time()
                req = urllib.request.Request(line, headers={'User-Agent': 'Mozilla/5.0'})
                response = urllib.request.urlopen(req, timeout=5)
                response.read(512)  # 读取少量数据
                response.close()
                speed = time.time() - start_time
                results.append((line, speed))
                print(f"✓ 速度: {speed:.2f}秒")
            except:
                print("✗ 连接失败")
    
    # 按速度排序
    results.sort(key=lambda x: x[1])
    
    # 写入结果文件
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("# 直播源速度测试结果 - 从快到慢排序\n")
        for url, speed in results:
            f.write(f"{url} # 速度: {speed:.2f}秒\n")
    
    print(f"\n测试完成！共找到 {len(results)} 个有效直播源")

if __name__ == "__main__":
    # 使用完整版本
    main()
    
    # 如果需要使用简化版本，取消下面的注释
    # simple_version()
