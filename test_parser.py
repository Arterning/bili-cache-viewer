"""
测试脚本 - 验证缓存解析功能
"""
import sys
import io
from pathlib import Path
from bilibili_cache_parser import BilibiliCacheParser

# 设置输出编码为UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def test_single_video():
    """测试单个视频解析"""
    print("=" * 60)
    print("测试1: 解析单个缓存目录")
    print("=" * 60)

    test_dir = Path("c_549206412")
    if not test_dir.exists():
        print("❌ 测试目录不存在")
        return

    video = BilibiliCacheParser.parse_cache_dir(test_dir)

    if video:
        print("✅ 解析成功！")
        print(f"\n视频信息：")
        print(f"  标题: {video.title}")
        print(f"  UP主: {video.owner_name}")
        print(f"  BV号: {video.bvid}")
        print(f"  分P: 第{video.page_index}P - {video.page_title}")
        print(f"  缓存目录: {video.cache_dir}")
        print(f"\n可用画质：")
        for i, q in enumerate(video.qualities, 1):
            print(f"  {i}. {q.quality_desc} ({q.get_size_str()})")
            print(f"     音频: {q.audio_path}")
            print(f"     视频: {q.video_path}")
    else:
        print("❌ 解析失败")

def test_directory_scan():
    """测试目录扫描"""
    print("\n" + "=" * 60)
    print("测试2: 扫描当前目录")
    print("=" * 60)

    current_dir = Path(".")
    videos = BilibiliCacheParser.scan_directory(current_dir)

    print(f"\n找到 {len(videos)} 个缓存视频：")

    for i, video in enumerate(videos, 1):
        print(f"\n{i}. {video.get_display_title()}")
        print(f"   UP主: {video.owner_name}")
        print(f"   画质: {', '.join([q.quality_desc for q in video.qualities])}")

def test_ffmpeg():
    """测试FFmpeg"""
    print("\n" + "=" * 60)
    print("测试3: FFmpeg检测")
    print("=" * 60)

    from ffmpeg_manager import FFmpegManager

    manager = FFmpegManager()

    if manager.is_available():
        print(f"✅ FFmpeg可用")
        print(f"   路径: {manager.ffmpeg_path}")
        version = manager.get_version()
        if version:
            print(f"   版本: {version}")
    else:
        print("❌ FFmpeg不可用")
        print("   请运行主程序自动下载，或手动安装FFmpeg")

if __name__ == "__main__":
    print("B站缓存视频管理工具 - 测试脚本\n")

    test_single_video()
    test_directory_scan()
    test_ffmpeg()

    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)
    print("\n提示：如果所有测试通过，可以运行主程序：")
    print("  python bilibili_cache_manager.py")
