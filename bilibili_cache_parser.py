"""
B站缓存视频解析模块
用于扫描和解析B站缓存目录结构
"""
import json
import os
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass


@dataclass
class VideoQuality:
    """视频画质信息"""
    quality_code: str  # 画质代号，如 "32"
    quality_desc: str  # 画质描述，如 "480P"
    audio_path: str    # audio.m4s 文件路径
    video_path: str    # video.m4s 文件路径
    total_size: int    # 总大小（字节）

    def get_size_str(self) -> str:
        """获取可读的文件大小"""
        size = self.total_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} TB"


@dataclass
class BilibiliVideo:
    """B站缓存视频信息"""
    cid: str                          # 视频CID
    title: str                        # 视频标题
    owner_name: str                   # UP主名称
    bvid: str                         # BV号
    page_index: int                   # 分P索引
    page_title: str                   # 分P标题
    cache_dir: str                    # 缓存目录路径
    qualities: List[VideoQuality]     # 可用画质列表

    def get_display_title(self) -> str:
        """获取显示用的标题"""
        if self.page_title and self.page_title != self.title:
            return f"{self.title} - P{self.page_index}: {self.page_title}"
        return self.title


class BilibiliCacheParser:
    """B站缓存解析器"""

    @staticmethod
    def parse_cache_dir(cache_dir: Path) -> Optional[BilibiliVideo]:
        """
        解析单个缓存目录

        Args:
            cache_dir: 缓存目录路径（如 c_549206412）

        Returns:
            BilibiliVideo对象，如果解析失败则返回None
        """
        entry_json = cache_dir / "entry.json"

        # 检查entry.json是否存在
        if not entry_json.exists():
            return None

        try:
            # 读取entry.json
            with open(entry_json, 'r', encoding='utf-8') as f:
                entry_data = json.load(f)

            # 提取基本信息
            cid = cache_dir.name.replace('c_', '')
            title = entry_data.get('title', '未知标题')
            owner_name = entry_data.get('owner_name', '未知UP主')
            bvid = entry_data.get('bvid', '')

            # 提取分P信息
            page_data = entry_data.get('page_data', {})
            page_index = page_data.get('page', 1)
            page_title = page_data.get('part', '')

            # 扫描所有画质目录
            qualities = []
            for quality_dir in cache_dir.iterdir():
                if not quality_dir.is_dir():
                    continue

                quality_code = quality_dir.name
                audio_file = quality_dir / "audio.m4s"
                video_file = quality_dir / "video.m4s"

                # 检查音视频文件是否存在
                if not (audio_file.exists() and video_file.exists()):
                    continue

                # 获取文件大小
                audio_size = audio_file.stat().st_size
                video_size = video_file.stat().st_size
                total_size = audio_size + video_size

                # 获取画质描述
                quality_desc = BilibiliCacheParser._get_quality_desc(
                    quality_code,
                    entry_data.get('quality_pithy_description', '')
                )

                qualities.append(VideoQuality(
                    quality_code=quality_code,
                    quality_desc=quality_desc,
                    audio_path=str(audio_file),
                    video_path=str(video_file),
                    total_size=total_size
                ))

            # 如果没有找到有效的画质，返回None
            if not qualities:
                return None

            # 按画质代号降序排序（数字越大画质越高）
            qualities.sort(key=lambda x: int(x.quality_code), reverse=True)

            return BilibiliVideo(
                cid=cid,
                title=title,
                owner_name=owner_name,
                bvid=bvid,
                page_index=page_index,
                page_title=page_title,
                cache_dir=str(cache_dir),
                qualities=qualities
            )

        except Exception as e:
            print(f"解析缓存目录 {cache_dir} 失败: {e}")
            return None

    @staticmethod
    def _get_quality_desc(quality_code: str, hint: str = '') -> str:
        """获取画质描述"""
        quality_map = {
            '6': '240P',
            '16': '360P',
            '32': '480P',
            '64': '720P',
            '74': '720P60',
            '80': '1080P',
            '112': '1080P+',
            '116': '1080P60',
            '120': '4K',
            '125': 'HDR',
            '126': 'Dolby',
            '127': '8K',
        }

        # 优先使用hint
        if hint:
            return hint

        return quality_map.get(quality_code, f'画质{quality_code}')

    @staticmethod
    def scan_directory(root_dir: Path) -> List[BilibiliVideo]:
        """
        递归扫描目录，查找所有B站缓存视频

        Args:
            root_dir: 根目录路径

        Returns:
            BilibiliVideo对象列表
        """
        videos = []

        # 递归查找所有 c_ 开头的目录
        for path in root_dir.rglob('c_*'):
            if path.is_dir():
                video = BilibiliCacheParser.parse_cache_dir(path)
                if video:
                    videos.append(video)

        # 按标题和分P排序
        videos.sort(key=lambda x: (x.title, x.page_index))

        return videos


# 测试代码
if __name__ == "__main__":
    # 测试解析示例目录
    test_dir = Path(r"C:\Users\ningh\Desktop\coding\new-parse\c_549206412")
    if test_dir.exists():
        print("测试单个目录解析：")
        video = BilibiliCacheParser.parse_cache_dir(test_dir)
        if video:
            print(f"标题: {video.get_display_title()}")
            print(f"UP主: {video.owner_name}")
            print(f"BV号: {video.bvid}")
            print(f"分P: 第{video.page_index}P - {video.page_title}")
            print(f"可用画质:")
            for q in video.qualities:
                print(f"  - {q.quality_desc} ({q.get_size_str()})")
        else:
            print("解析失败")
