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
    audio_path: str    # audio.m4s 文件路径（M4S格式）或空字符串（BLV格式）
    video_path: str    # video.m4s 文件路径（M4S格式）或 .blv 文件路径（BLV格式）
    total_size: int    # 总大小（字节）
    format_type: str = 'M4S'  # 格式类型：'M4S' 或 'BLV'
    blv_files: List[str] = None  # BLV格式的所有分段文件列表

    def __post_init__(self):
        """初始化后处理"""
        if self.blv_files is None:
            self.blv_files = []

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
    cover_url: str = ''               # 封面图URL
    cover_path: str = ''              # 本地封面图路径
    time_create: int = 0              # 创建时间戳（毫秒）

    def get_display_title(self) -> str:
        """获取显示用的标题"""
        if self.page_title and self.page_title != self.title:
            return f"{self.title} - P{self.page_index}: {self.page_title}"
        return self.title

    def get_cover(self) -> str:
        """获取封面图路径或URL，优先返回本地路径"""
        return self.cover_path if self.cover_path else self.cover_url


class BilibiliCacheParser:
    """B站缓存解析器"""

    @staticmethod
    def parse_cache_dir(cache_dir: Path) -> Optional[BilibiliVideo]:
        """
        解析单个缓存目录（支持M4S和BLV两种格式）

        Args:
            cache_dir: 缓存目录路径（如 c_549206412 或数字目录）

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
            # 兼容旧版和新版entry.json
            cid = str(entry_data.get('page_data', {}).get('cid', '')) or cache_dir.name.replace('c_', '')
            title = entry_data.get('title', '未知标题')
            owner_name = entry_data.get('owner_name', '未知UP主')
            bvid = entry_data.get('bvid', '')
            avid = entry_data.get('avid', 0)

            # 提取封面信息
            cover_url = entry_data.get('cover', '')
            cover_file = cache_dir / 'cover.jpg'
            cover_path = str(cover_file) if cover_file.exists() else ''

            # 提取分P信息
            page_data = entry_data.get('page_data', {})
            page_index = page_data.get('page', 1)
            page_title = page_data.get('part', '')

            # 提取创建时间
            time_create = entry_data.get('time_create_stamp', 0)

            # 检测缓存格式并解析画质信息
            qualities = []

            # 尝试解析M4S格式（新版缓存）
            m4s_qualities = BilibiliCacheParser._parse_m4s_format(cache_dir, entry_data)
            if m4s_qualities:
                qualities.extend(m4s_qualities)

            # 尝试解析BLV格式（旧版缓存）
            blv_qualities = BilibiliCacheParser._parse_blv_format(cache_dir, entry_data)
            if blv_qualities:
                qualities.extend(blv_qualities)

            # 如果没有找到有效的画质，返回None
            if not qualities:
                return None

            # 按画质代号降序排序（数字越大画质越高）
            qualities.sort(key=lambda x: int(x.quality_code) if x.quality_code.isdigit() else 0, reverse=True)

            return BilibiliVideo(
                cid=cid,
                title=title,
                owner_name=owner_name,
                bvid=bvid,
                page_index=page_index,
                page_title=page_title,
                cache_dir=str(cache_dir),
                qualities=qualities,
                cover_url=cover_url,
                cover_path=cover_path,
                time_create=time_create
            )

        except Exception as e:
            print(f"解析缓存目录 {cache_dir} 失败: {e}")
            return None

    @staticmethod
    def _parse_m4s_format(cache_dir: Path, entry_data: dict) -> List[VideoQuality]:
        """解析M4S格式的缓存（新版）"""
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
                total_size=total_size,
                format_type='M4S'
            ))

        return qualities

    @staticmethod
    def _parse_blv_format(cache_dir: Path, entry_data: dict) -> List[VideoQuality]:
        """解析BLV格式的缓存（旧版）"""
        qualities = []

        # 递归查找所有包含index.json的目录
        for index_json_path in cache_dir.rglob('index.json'):
            quality_dir = index_json_path.parent

            try:
                # 读取index.json
                with open(index_json_path, 'r', encoding='utf-8') as f:
                    index_data = json.load(f)

                # 从目录名中提取画质代号（如 lua.mp4.bili2api.16 -> 16）
                dir_name = quality_dir.name
                type_tag = entry_data.get('type_tag', '')

                # 提取画质代号
                quality_code = dir_name.split('.')[-1] if '.' in dir_name else '16'

                # 获取画质描述
                quality_desc = index_data.get('description', '') or BilibiliCacheParser._get_quality_desc(quality_code)

                # 查找所有.blv文件
                blv_files = sorted(quality_dir.glob('*.blv'))
                if not blv_files:
                    continue

                # 计算总大小
                total_size = sum(f.stat().st_size for f in blv_files)

                # 获取segment信息
                segment_list = index_data.get('segment_list', [])
                if segment_list and len(segment_list) > 0:
                    segment = segment_list[0]
                    total_size = segment.get('bytes', total_size)

                qualities.append(VideoQuality(
                    quality_code=quality_code,
                    quality_desc=quality_desc,
                    audio_path='',  # BLV格式音视频合并在一起
                    video_path=str(blv_files[0]) if len(blv_files) == 1 else str(quality_dir),
                    total_size=total_size,
                    format_type='BLV',
                    blv_files=[str(f) for f in blv_files]
                ))

            except Exception as e:
                print(f"解析BLV格式失败 {quality_dir}: {e}")
                continue

        return qualities

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
        递归扫描目录，查找所有B站缓存视频（支持M4S和BLV格式）

        Args:
            root_dir: 根目录路径

        Returns:
            BilibiliVideo对象列表
        """
        videos = []
        processed_dirs = set()  # 避免重复处理

        # 递归查找所有包含entry.json的目录
        for entry_json_path in root_dir.rglob('entry.json'):
            cache_dir = entry_json_path.parent

            # 避免重复处理同一目录
            if cache_dir in processed_dirs:
                continue

            processed_dirs.add(cache_dir)

            # 解析缓存目录
            video = BilibiliCacheParser.parse_cache_dir(cache_dir)
            if video:
                videos.append(video)

        # 按创建时间倒序排序（最新的在前面）
        videos.sort(key=lambda x: x.time_create, reverse=True)

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
            print(f"封面URL: {video.cover_url}")
            print(f"本地封面: {video.cover_path if video.cover_path else '无'}")
            print(f"可用画质:")
            for q in video.qualities:
                print(f"  - {q.quality_desc} ({q.get_size_str()})")
        else:
            print("解析失败")
