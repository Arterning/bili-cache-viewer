"""
B站缓存视频管理工具 - 主GUI程序
"""
import os
import sys
import tempfile
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from typing import List, Optional
import subprocess
import platform
from io import BytesIO
import urllib.request

try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("警告: 未安装Pillow库，封面图片将不会显示")
    print("请运行: pip install Pillow")

from bilibili_cache_parser import BilibiliCacheParser, BilibiliVideo, VideoQuality
from ffmpeg_manager import FFmpegManager


class VideoCard(ttk.Frame):
    """视频卡片组件"""

    def __init__(self, parent, video: BilibiliVideo, on_play, on_export):
        super().__init__(parent, relief="raised", borderwidth=1)
        self.video = video
        self.on_play = on_play
        self.on_export = on_export
        self.selected_quality: Optional[VideoQuality] = None
        self.cover_image = None  # 保持对图片的引用，防止被垃圾回收

        self._create_ui()

    def _create_ui(self):
        """创建UI"""
        # 主容器，使用padding
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill="both", expand=True)

        # 左侧：封面图片
        cover_frame = ttk.Frame(main_frame)
        cover_frame.grid(row=0, column=0, rowspan=3, sticky="nw", padx=(0, 10))

        self._load_cover_image(cover_frame)

        # 右侧：视频信息
        info_frame = ttk.Frame(main_frame)
        info_frame.grid(row=0, column=1, sticky="ew")

        # 标题行
        title_label = ttk.Label(
            info_frame,
            text=self.video.get_display_title(),
            font=("Arial", 11, "bold"),
            wraplength=600
        )
        title_label.grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 5))

        # 信息行
        info_text = f"UP主: {self.video.owner_name} | BV号: {self.video.bvid}"
        info_label = ttk.Label(info_frame, text=info_text, foreground="gray")
        info_label.grid(row=1, column=0, columnspan=3, sticky="w", pady=(0, 5))

        # 画质选择
        quality_label = ttk.Label(info_frame, text="画质:")
        quality_label.grid(row=2, column=0, sticky="w", padx=(0, 5))

        # 画质下拉框
        quality_options = [
            f"{q.quality_desc} ({q.get_size_str()})"
            for q in self.video.qualities
        ]
        self.quality_var = tk.StringVar(value=quality_options[0])
        quality_combo = ttk.Combobox(
            info_frame,
            textvariable=self.quality_var,
            values=quality_options,
            state="readonly",
            width=25
        )
        quality_combo.grid(row=2, column=1, sticky="w", padx=(0, 10))
        quality_combo.bind("<<ComboboxSelected>>", self._on_quality_changed)

        # 默认选择第一个画质
        self.selected_quality = self.video.qualities[0]

        # 按钮区域
        button_frame = ttk.Frame(info_frame)
        button_frame.grid(row=2, column=2, sticky="e")

        play_btn = ttk.Button(
            button_frame,
            text="播放",
            command=self._on_play_clicked,
            width=8
        )
        play_btn.pack(side="left", padx=(0, 5))

        export_btn = ttk.Button(
            button_frame,
            text="导出",
            command=self._on_export_clicked,
            width=8
        )
        export_btn.pack(side="left")

        # 配置列权重，使内容合理分布
        main_frame.columnconfigure(1, weight=1)
        info_frame.columnconfigure(1, weight=1)

    def _load_cover_image(self, parent):
        """加载封面图片"""
        if not PIL_AVAILABLE:
            # 如果PIL不可用，显示文本占位符
            placeholder = ttk.Label(
                parent,
                text="[封面]",
                relief="solid",
                borderwidth=1,
                width=12,
                anchor="center"
            )
            placeholder.pack()
            return

        try:
            cover_path = self.video.get_cover()
            if not cover_path:
                self._show_placeholder(parent)
                return

            # 尝试加载本地图片
            if self.video.cover_path and Path(self.video.cover_path).exists():
                image = Image.open(self.video.cover_path)
            # 如果没有本地图片，尝试从URL下载
            elif self.video.cover_url:
                # 在线程中异步加载网络图片
                self._load_cover_from_url(parent, self.video.cover_url)
                return
            else:
                self._show_placeholder(parent)
                return

            # 调整图片大小 (保持宽高比)
            # 封面尺寸：宽度120px，高度自适应
            target_width = 120
            w_percent = target_width / float(image.size[0])
            target_height = int(float(image.size[1]) * w_percent)

            # 限制最大高度
            max_height = 90
            if target_height > max_height:
                target_height = max_height
                h_percent = max_height / float(image.size[1])
                target_width = int(float(image.size[0]) * h_percent)

            image = image.resize((target_width, target_height), Image.Resampling.LANCZOS)

            # 转换为PhotoImage
            self.cover_image = ImageTk.PhotoImage(image)

            # 显示图片
            cover_label = ttk.Label(parent, image=self.cover_image)
            cover_label.pack()

        except Exception as e:
            print(f"加载封面失败: {e}")
            self._show_placeholder(parent)

    def _load_cover_from_url(self, parent, url):
        """从URL异步加载封面图片"""
        # 先显示占位符
        placeholder = ttk.Label(
            parent,
            text="加载中...",
            relief="solid",
            borderwidth=1,
            width=12,
            anchor="center"
        )
        placeholder.pack()

        def download_thread():
            try:
                # 下载图片
                with urllib.request.urlopen(url, timeout=5) as response:
                    image_data = response.read()

                # 在主线程中更新UI
                self.after(0, lambda: self._display_downloaded_cover(
                    parent, placeholder, image_data
                ))
            except Exception as e:
                print(f"从URL加载封面失败: {e}")
                self.after(0, lambda: self._show_placeholder(parent, placeholder))

        thread = threading.Thread(target=download_thread, daemon=True)
        thread.start()

    def _display_downloaded_cover(self, parent, old_widget, image_data):
        """显示下载的封面图片"""
        try:
            # 移除占位符
            old_widget.destroy()

            # 从字节流加载图片
            image = Image.open(BytesIO(image_data))

            # 调整图片大小
            target_width = 120
            w_percent = target_width / float(image.size[0])
            target_height = int(float(image.size[1]) * w_percent)

            max_height = 90
            if target_height > max_height:
                target_height = max_height
                h_percent = max_height / float(image.size[1])
                target_width = int(float(image.size[0]) * h_percent)

            image = image.resize((target_width, target_height), Image.Resampling.LANCZOS)

            # 转换为PhotoImage
            self.cover_image = ImageTk.PhotoImage(image)

            # 显示图片
            cover_label = ttk.Label(parent, image=self.cover_image)
            cover_label.pack()

        except Exception as e:
            print(f"显示封面失败: {e}")
            self._show_placeholder(parent, old_widget)

    def _show_placeholder(self, parent, old_widget=None):
        """显示占位符"""
        if old_widget:
            old_widget.destroy()

        placeholder = ttk.Label(
            parent,
            text="无封面",
            relief="solid",
            borderwidth=1,
            width=12,
            anchor="center"
        )
        placeholder.pack()

    def _on_quality_changed(self, event):
        """画质改变事件"""
        selected_index = self.quality_var.get()
        # 从显示文本中提取画质索引
        for i, q in enumerate(self.video.qualities):
            if f"{q.quality_desc} ({q.get_size_str()})" == selected_index:
                self.selected_quality = q
                break

    def _on_play_clicked(self):
        """播放按钮点击"""
        if self.selected_quality:
            self.on_play(self.video, self.selected_quality)

    def _on_export_clicked(self):
        """导出按钮点击"""
        if self.selected_quality:
            self.on_export(self.video, self.selected_quality)


class BilibiliCacheManager(tk.Tk):
    """B站缓存视频管理器主窗口"""

    def __init__(self):
        super().__init__()

        self.title("B站缓存视频管理工具")
        self.geometry("900x600")

        self.ffmpeg_manager = FFmpegManager()
        self.videos: List[BilibiliVideo] = []
        self.video_cards: List[VideoCard] = []

        # 分页相关
        self.page_size = 10  # 每页显示10条
        self.current_page = 1  # 当前页码（从1开始）
        self.total_pages = 0  # 总页数

        self._create_ui()
        self._check_ffmpeg()

    def _create_ui(self):
        """创建UI"""
        # 顶部工具栏
        toolbar = ttk.Frame(self, padding="10")
        toolbar.pack(fill="x", side="top")

        # 选择目录按钮
        select_btn = ttk.Button(
            toolbar,
            text="选择缓存目录",
            command=self._select_directory
        )
        select_btn.pack(side="left", padx=(0, 10))

        # 刷新按钮
        refresh_btn = ttk.Button(
            toolbar,
            text="刷新",
            command=self._refresh_videos
        )
        refresh_btn.pack(side="left", padx=(0, 10))

        # 状态标签
        self.status_label = ttk.Label(toolbar, text="请选择缓存目录")
        self.status_label.pack(side="left", padx=(10, 0))

        # 分隔线
        separator = ttk.Separator(self, orient="horizontal")
        separator.pack(fill="x", padx=10, pady=5)

        # 分页控制栏
        pagination_top = ttk.Frame(self, padding="5")
        pagination_top.pack(fill="x", padx=10)

        self.page_info_label = ttk.Label(pagination_top, text="")
        self.page_info_label.pack(side="left")

        pagination_buttons = ttk.Frame(pagination_top)
        pagination_buttons.pack(side="right")

        self.first_page_btn = ttk.Button(
            pagination_buttons,
            text="首页",
            command=self._first_page,
            width=6
        )
        self.first_page_btn.pack(side="left", padx=2)

        self.prev_page_btn = ttk.Button(
            pagination_buttons,
            text="上一页",
            command=self._prev_page,
            width=8
        )
        self.prev_page_btn.pack(side="left", padx=2)

        self.page_entry = ttk.Entry(pagination_buttons, width=5)
        self.page_entry.pack(side="left", padx=2)
        self.page_entry.bind("<Return>", lambda e: self._goto_page())

        ttk.Button(
            pagination_buttons,
            text="跳转",
            command=self._goto_page,
            width=6
        ).pack(side="left", padx=2)

        self.next_page_btn = ttk.Button(
            pagination_buttons,
            text="下一页",
            command=self._next_page,
            width=8
        )
        self.next_page_btn.pack(side="left", padx=2)

        self.last_page_btn = ttk.Button(
            pagination_buttons,
            text="末页",
            command=self._last_page,
            width=6
        )
        self.last_page_btn.pack(side="left", padx=2)

        # 视频列表容器（带滚动条）
        list_container = ttk.Frame(self)
        list_container.pack(fill="both", expand=True, padx=10, pady=10)

        # 创建Canvas和滚动条
        canvas = tk.Canvas(list_container, highlightthickness=0)
        scrollbar = ttk.Scrollbar(list_container, orient="vertical", command=canvas.yview)
        self.video_list_frame = ttk.Frame(canvas)

        # 配置canvas
        canvas.configure(yscrollcommand=scrollbar.set)

        # 布局
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        # 创建窗口
        canvas_window = canvas.create_window((0, 0), window=self.video_list_frame, anchor="nw")

        # 更新滚动区域
        def update_scroll_region(event=None):
            canvas.configure(scrollregion=canvas.bbox("all"))

        self.video_list_frame.bind("<Configure>", update_scroll_region)

        # 调整canvas窗口宽度
        def on_canvas_configure(event):
            canvas.itemconfig(canvas_window, width=event.width)

        canvas.bind("<Configure>", on_canvas_configure)

        # 鼠标滚轮支持
        def on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind_all("<MouseWheel>", on_mousewheel)

        self.canvas = canvas

        # 当前目录
        self.current_directory: Optional[Path] = None

    def _check_ffmpeg(self):
        """检查FFmpeg"""
        if not self.ffmpeg_manager.is_available():
            result = messagebox.askyesno(
                "FFmpeg未找到",
                "未检测到FFmpeg，需要下载吗？\n"
                "（FFmpeg用于合并音视频文件）\n\n"
                "大小约60MB，下载可能需要几分钟。",
                icon="warning"
            )
            if result:
                self._download_ffmpeg()

    def _download_ffmpeg(self):
        """下载FFmpeg"""
        # 创建进度窗口
        progress_window = tk.Toplevel(self)
        progress_window.title("下载FFmpeg")
        progress_window.geometry("400x150")
        progress_window.transient(self)
        progress_window.grab_set()

        # 进度条
        ttk.Label(progress_window, text="正在下载FFmpeg...", padding=20).pack()
        progress_bar = ttk.Progressbar(
            progress_window,
            mode="determinate",
            length=300
        )
        progress_bar.pack(pady=10)

        status_label = ttk.Label(progress_window, text="准备中...")
        status_label.pack(pady=10)

        # 进度回调
        def progress_callback(current, total, msg):
            progress_bar["value"] = current
            progress_bar["maximum"] = total
            status_label["text"] = msg
            progress_window.update()

        # 在新线程中下载
        def download_thread():
            success = self.ffmpeg_manager.download_ffmpeg(progress_callback)
            progress_window.after(100, lambda: self._on_ffmpeg_downloaded(progress_window, success))

        thread = threading.Thread(target=download_thread, daemon=True)
        thread.start()

    def _on_ffmpeg_downloaded(self, window, success):
        """FFmpeg下载完成"""
        window.destroy()
        if success:
            messagebox.showinfo("成功", "FFmpeg下载完成！")
        else:
            messagebox.showerror(
                "下载失败",
                "FFmpeg下载失败。\n"
                "您可以手动安装FFmpeg并添加到系统PATH中。"
            )

    def _select_directory(self):
        """选择目录"""
        directory = filedialog.askdirectory(title="选择B站缓存目录")
        if directory:
            self.current_directory = Path(directory)
            self._scan_videos()

    def _refresh_videos(self):
        """刷新视频列表"""
        if self.current_directory:
            self._scan_videos()
        else:
            messagebox.showwarning("提示", "请先选择缓存目录")

    def _scan_videos(self):
        """扫描视频"""
        if not self.current_directory:
            return

        self.status_label["text"] = "扫描中..."
        self.update()

        # 扫描视频
        self.videos = BilibiliCacheParser.scan_directory(self.current_directory)

        # 计算总页数
        self.total_pages = (len(self.videos) + self.page_size - 1) // self.page_size if self.videos else 0
        self.current_page = 1

        # 更新状态
        self.status_label["text"] = f"找到 {len(self.videos)} 个缓存视频"

        # 显示第一页
        self._display_current_page()

    def _display_current_page(self):
        """显示当前页的视频"""
        # 清空现有列表
        for card in self.video_cards:
            card.destroy()
        self.video_cards.clear()

        # 如果没有找到视频
        if not self.videos:
            no_video_label = ttk.Label(
                self.video_list_frame,
                text="未找到缓存视频\n请确认目录是否正确",
                foreground="gray",
                font=("Arial", 12)
            )
            no_video_label.pack(pady=50)
            self._update_pagination_ui()
            return

        # 计算当前页的视频范围
        start_idx = (self.current_page - 1) * self.page_size
        end_idx = min(start_idx + self.page_size, len(self.videos))

        # 创建当前页的视频卡片
        for video in self.videos[start_idx:end_idx]:
            card = VideoCard(
                self.video_list_frame,
                video,
                on_play=self._play_video,
                on_export=self._export_video
            )
            card.pack(fill="x", pady=5, padx=5)
            self.video_cards.append(card)

        # 更新分页UI
        self._update_pagination_ui()

    def _update_pagination_ui(self):
        """更新分页UI状态"""
        if self.total_pages == 0:
            self.page_info_label["text"] = ""
            self.first_page_btn["state"] = "disabled"
            self.prev_page_btn["state"] = "disabled"
            self.next_page_btn["state"] = "disabled"
            self.last_page_btn["state"] = "disabled"
            self.page_entry.delete(0, tk.END)
            return

        # 更新页码信息
        start_idx = (self.current_page - 1) * self.page_size + 1
        end_idx = min(self.current_page * self.page_size, len(self.videos))
        self.page_info_label["text"] = f"第 {self.current_page}/{self.total_pages} 页 (显示 {start_idx}-{end_idx}，共 {len(self.videos)} 个)"

        # 更新按钮状态
        self.first_page_btn["state"] = "normal" if self.current_page > 1 else "disabled"
        self.prev_page_btn["state"] = "normal" if self.current_page > 1 else "disabled"
        self.next_page_btn["state"] = "normal" if self.current_page < self.total_pages else "disabled"
        self.last_page_btn["state"] = "normal" if self.current_page < self.total_pages else "disabled"

        # 更新页码输入框
        self.page_entry.delete(0, tk.END)
        self.page_entry.insert(0, str(self.current_page))

    def _first_page(self):
        """跳转到首页"""
        if self.current_page != 1:
            self.current_page = 1
            self._display_current_page()

    def _last_page(self):
        """跳转到末页"""
        if self.current_page != self.total_pages:
            self.current_page = self.total_pages
            self._display_current_page()

    def _prev_page(self):
        """上一页"""
        if self.current_page > 1:
            self.current_page -= 1
            self._display_current_page()

    def _next_page(self):
        """下一页"""
        if self.current_page < self.total_pages:
            self.current_page += 1
            self._display_current_page()

    def _goto_page(self):
        """跳转到指定页"""
        try:
            page = int(self.page_entry.get())
            if 1 <= page <= self.total_pages:
                self.current_page = page
                self._display_current_page()
            else:
                messagebox.showwarning("提示", f"请输入1-{self.total_pages}之间的页码")
                self.page_entry.delete(0, tk.END)
                self.page_entry.insert(0, str(self.current_page))
        except ValueError:
            messagebox.showwarning("提示", "请输入有效的页码")
            self.page_entry.delete(0, tk.END)
            self.page_entry.insert(0, str(self.current_page))

    def _play_video(self, video: BilibiliVideo, quality: VideoQuality):
        """播放视频"""
        if not self.ffmpeg_manager.is_available():
            messagebox.showerror("错误", "FFmpeg不可用，无法播放视频")
            return

        # 创建临时文件
        temp_dir = Path(tempfile.gettempdir()) / "bilibili_cache_player"
        temp_dir.mkdir(exist_ok=True)

        # 生成临时文件名
        temp_filename = f"{video.bvid}_P{video.page_index}_{quality.quality_desc}.mp4"
        temp_file = temp_dir / temp_filename

        # 如果临时文件已存在，直接播放
        if temp_file.exists():
            self._open_with_default_player(str(temp_file))
            return

        # 显示进度窗口
        progress_window = tk.Toplevel(self)
        progress_window.title("合并视频")
        progress_window.geometry("400x120")
        progress_window.transient(self)
        progress_window.grab_set()

        ttk.Label(progress_window, text="正在合并音视频...", padding=20).pack()
        progress_bar = ttk.Progressbar(progress_window, mode="indeterminate", length=300)
        progress_bar.pack(pady=10)
        progress_bar.start(10)

        status_label = ttk.Label(progress_window, text="处理中...")
        status_label.pack()

        # 在新线程中处理视频
        def process_thread():
            # 根据格式类型选择不同的处理方式
            if quality.format_type == 'BLV':
                # BLV格式：直接转换
                success = self.ffmpeg_manager.convert_blv(
                    quality.video_path,
                    str(temp_file)
                )
            else:
                # M4S格式：合并音视频
                success = self.ffmpeg_manager.merge_video(
                    quality.audio_path,
                    quality.video_path,
                    str(temp_file)
                )
            progress_window.after(100, lambda: self._on_merge_complete(
                progress_window, success, str(temp_file)
            ))

        thread = threading.Thread(target=process_thread, daemon=True)
        thread.start()

    def _on_merge_complete(self, window, success, file_path):
        """合并完成"""
        window.destroy()
        if success:
            self._open_with_default_player(file_path)
        else:
            messagebox.showerror("错误", "视频合并失败")

    def _open_with_default_player(self, file_path):
        """使用系统默认播放器打开"""
        try:
            if platform.system() == "Windows":
                os.startfile(file_path)
            elif platform.system() == "Darwin":  # macOS
                subprocess.run(["open", file_path])
            else:  # Linux
                subprocess.run(["xdg-open", file_path])
        except Exception as e:
            messagebox.showerror("错误", f"无法打开播放器: {e}")

    def _export_video(self, video: BilibiliVideo, quality: VideoQuality):
        """导出视频"""
        if not self.ffmpeg_manager.is_available():
            messagebox.showerror("错误", "FFmpeg不可用，无法导出视频")
            return

        # 建议的文件名
        suggested_name = f"{video.title}_P{video.page_index}_{video.page_title}_{quality.quality_desc}.mp4"
        # 移除文件名中的非法字符
        suggested_name = "".join(c for c in suggested_name if c not in r'\/:*?"<>|')

        # 选择保存位置
        output_file = filedialog.asksaveasfilename(
            title="导出视频",
            defaultextension=".mp4",
            initialfile=suggested_name,
            filetypes=[("MP4文件", "*.mp4"), ("所有文件", "*.*")]
        )

        if not output_file:
            return

        # 显示进度窗口
        progress_window = tk.Toplevel(self)
        progress_window.title("导出视频")
        progress_window.geometry("400x120")
        progress_window.transient(self)
        progress_window.grab_set()

        ttk.Label(progress_window, text="正在导出视频...", padding=20).pack()
        progress_bar = ttk.Progressbar(progress_window, mode="indeterminate", length=300)
        progress_bar.pack(pady=10)
        progress_bar.start(10)

        status_label = ttk.Label(progress_window, text="处理中...")
        status_label.pack()

        # 在新线程中导出
        def export_thread():
            # 根据格式类型选择不同的处理方式
            if quality.format_type == 'BLV':
                # BLV格式：直接转换
                success = self.ffmpeg_manager.convert_blv(
                    quality.video_path,
                    output_file
                )
            else:
                # M4S格式：合并音视频
                success = self.ffmpeg_manager.merge_video(
                    quality.audio_path,
                    quality.video_path,
                    output_file
                )
            progress_window.after(100, lambda: self._on_export_complete(
                progress_window, success, output_file
            ))

        thread = threading.Thread(target=export_thread, daemon=True)
        thread.start()

    def _on_export_complete(self, window, success, file_path):
        """导出完成"""
        window.destroy()
        if success:
            result = messagebox.askyesno(
                "成功",
                f"视频已导出到:\n{file_path}\n\n是否打开文件所在位置？"
            )
            if result:
                # 打开文件所在目录
                if platform.system() == "Windows":
                    subprocess.run(["explorer", "/select,", file_path])
                elif platform.system() == "Darwin":
                    subprocess.run(["open", "-R", file_path])
                else:
                    subprocess.run(["xdg-open", str(Path(file_path).parent)])
        else:
            messagebox.showerror("错误", "视频导出失败")


def main():
    """主函数"""
    app = BilibiliCacheManager()
    app.mainloop()


if __name__ == "__main__":
    main()
