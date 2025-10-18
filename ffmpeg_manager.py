"""
FFmpeg 管理模块
负责检测、下载和使用FFmpeg进行音视频合并
"""
import os
import platform
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Optional
import urllib.request
import shutil


class FFmpegManager:
    """FFmpeg管理器"""

    def __init__(self):
        self.ffmpeg_path: Optional[str] = None
        self._detect_ffmpeg()

    def _detect_ffmpeg(self):
        """检测系统中的FFmpeg"""
        # 1. 检查是否在PATH中
        ffmpeg_cmd = "ffmpeg.exe" if platform.system() == "Windows" else "ffmpeg"
        if shutil.which(ffmpeg_cmd):
            self.ffmpeg_path = ffmpeg_cmd
            return

        # 2. 检查当前目录下的ffmpeg文件夹
        local_ffmpeg_dir = Path(__file__).parent / "ffmpeg"
        if platform.system() == "Windows":
            local_ffmpeg = local_ffmpeg_dir / "bin" / "ffmpeg.exe"
        else:
            local_ffmpeg = local_ffmpeg_dir / "ffmpeg"

        if local_ffmpeg.exists():
            self.ffmpeg_path = str(local_ffmpeg)
            return

    def is_available(self) -> bool:
        """检查FFmpeg是否可用"""
        return self.ffmpeg_path is not None

    def get_version(self) -> Optional[str]:
        """获取FFmpeg版本"""
        if not self.is_available():
            return None

        try:
            result = subprocess.run(
                [self.ffmpeg_path, "-version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            # 提取第一行的版本信息
            first_line = result.stdout.split('\n')[0]
            return first_line
        except Exception:
            return None

    def download_ffmpeg(self, progress_callback=None) -> bool:
        """
        下载FFmpeg

        Args:
            progress_callback: 进度回调函数 callback(current, total, status_msg)

        Returns:
            是否下载成功
        """
        system = platform.system()

        if system == "Windows":
            return self._download_ffmpeg_windows(progress_callback)
        elif system == "Darwin":  # macOS
            return self._download_ffmpeg_macos(progress_callback)
        else:  # Linux
            return self._download_ffmpeg_linux(progress_callback)

    def _download_ffmpeg_windows(self, progress_callback) -> bool:
        """下载Windows版FFmpeg"""
        try:
            # 使用gyan.dev的FFmpeg构建（精简版）
            url = "https://github.com/GyanD/codexffmpeg/releases/download/7.1/ffmpeg-7.1-essentials_build.zip"

            download_dir = Path(__file__).parent / "temp_download"
            download_dir.mkdir(exist_ok=True)

            zip_path = download_dir / "ffmpeg.zip"
            extract_path = Path(__file__).parent / "ffmpeg"

            if progress_callback:
                progress_callback(0, 100, "开始下载FFmpeg...")

            # 下载文件
            def report_progress(block_num, block_size, total_size):
                if progress_callback and total_size > 0:
                    downloaded = block_num * block_size
                    percent = min(100, (downloaded / total_size) * 100)
                    progress_callback(
                        int(percent), 100,
                        f"下载中... {percent:.1f}%"
                    )

            urllib.request.urlretrieve(url, zip_path, reporthook=report_progress)

            if progress_callback:
                progress_callback(100, 100, "解压中...")

            # 解压文件
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(download_dir)

            # 移动到目标位置
            # 找到解压后的目录
            extracted_dirs = [d for d in download_dir.iterdir() if d.is_dir()]
            if extracted_dirs:
                src_dir = extracted_dirs[0]
                if extract_path.exists():
                    shutil.rmtree(extract_path)
                shutil.move(str(src_dir), str(extract_path))

            # 清理临时文件
            shutil.rmtree(download_dir)

            # 更新ffmpeg路径
            self.ffmpeg_path = str(extract_path / "bin" / "ffmpeg.exe")

            if progress_callback:
                progress_callback(100, 100, "下载完成！")

            return True

        except Exception as e:
            if progress_callback:
                progress_callback(0, 100, f"下载失败: {e}")
            print(f"下载FFmpeg失败: {e}")
            return False

    def _download_ffmpeg_macos(self, progress_callback) -> bool:
        """macOS用户需要手动安装"""
        if progress_callback:
            progress_callback(0, 100, "请使用 Homebrew 安装: brew install ffmpeg")
        return False

    def _download_ffmpeg_linux(self, progress_callback) -> bool:
        """Linux用户需要手动安装"""
        if progress_callback:
            progress_callback(0, 100, "请使用包管理器安装: sudo apt install ffmpeg")
        return False

    def merge_video(self, audio_path: str, video_path: str, output_path: str,
                   progress_callback=None) -> bool:
        """
        合并音频和视频文件

        Args:
            audio_path: 音频文件路径
            video_path: 视频文件路径
            output_path: 输出文件路径
            progress_callback: 进度回调函数

        Returns:
            是否合并成功
        """
        if not self.is_available():
            print("FFmpeg不可用")
            return False

        try:
            # FFmpeg命令：复制流而不重新编码（速度快）
            cmd = [
                self.ffmpeg_path,
                "-i", video_path,
                "-i", audio_path,
                "-c", "copy",  # 复制编码，不重新编码
                "-y",  # 覆盖输出文件
                output_path
            ]

            if progress_callback:
                progress_callback(0, 100, "开始合并...")

            # 执行FFmpeg
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5分钟超时
            )

            if result.returncode == 0:
                if progress_callback:
                    progress_callback(100, 100, "合并完成！")
                return True
            else:
                error_msg = result.stderr
                print(f"FFmpeg执行失败: {error_msg}")
                if progress_callback:
                    progress_callback(0, 100, f"合并失败: {error_msg[:100]}")
                return False

        except subprocess.TimeoutExpired:
            print("FFmpeg执行超时")
            if progress_callback:
                progress_callback(0, 100, "合并超时")
            return False
        except Exception as e:
            print(f"合并视频时出错: {e}")
            if progress_callback:
                progress_callback(0, 100, f"错误: {e}")
            return False


# 测试代码
if __name__ == "__main__":
    manager = FFmpegManager()
    print(f"FFmpeg可用: {manager.is_available()}")
    if manager.is_available():
        print(f"版本: {manager.get_version()}")
        print(f"路径: {manager.ffmpeg_path}")
    else:
        print("FFmpeg未找到，可以使用 download_ffmpeg() 方法下载")
