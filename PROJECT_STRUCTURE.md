# 项目结构说明

## 文件组织

```
new-parse/
├── bilibili_cache_manager.py    # 主程序（GUI）
├── bilibili_cache_parser.py     # 缓存解析模块
├── ffmpeg_manager.py             # FFmpeg管理模块
├── test_parser.py                # 测试脚本
├── run.bat                       # Windows启动脚本
├── README.md                     # 项目说明
├── USAGE.md                      # 使用指南
├── PROJECT_STRUCTURE.md          # 本文件
├── requirements.txt              # 依赖说明
├── c_549206412/                  # 示例缓存目录
│   ├── entry.json
│   ├── danmaku.xml
│   └── 32/
│       ├── audio.m4s
│       ├── video.m4s
│       └── index.json
└── ffmpeg/                       # FFmpeg程序（自动下载）
    └── bin/
        └── ffmpeg.exe
```

## 核心模块说明

### 1. bilibili_cache_manager.py（主程序）

**职责**：GUI界面和用户交互

**主要类**：
- `BilibiliCacheManager`：主窗口类
  - 目录选择
  - 视频列表展示
  - FFmpeg检测和下载
  - 播放/导出控制

- `VideoCard`：视频卡片组件
  - 封面图片显示（支持本地和在线加载）
  - 视频信息展示
  - 画质选择
  - 操作按钮

**关键方法**：
```python
_select_directory()      # 选择目录
_scan_videos()           # 扫描视频
_play_video()            # 播放视频
_export_video()          # 导出视频
_check_ffmpeg()          # 检查FFmpeg
_download_ffmpeg()       # 下载FFmpeg
```

### 2. bilibili_cache_parser.py（解析模块）

**职责**：解析B站缓存目录结构

**主要类**：
- `BilibiliVideo`：视频数据类
  - cid, title, owner_name, bvid
  - page_index, page_title
  - cover_url, cover_path（封面信息）
  - qualities（画质列表）

- `VideoQuality`：画质数据类
  - quality_code, quality_desc
  - audio_path, video_path
  - total_size

- `BilibiliCacheParser`：解析器类
  - `parse_cache_dir()`：解析单个缓存目录
  - `scan_directory()`：递归扫描目录
  - `_get_quality_desc()`：获取画质描述

**数据流**：
```
缓存目录 → entry.json → BilibiliVideo (title, owner_name, bvid, cover_url等)
         → cover.jpg → cover_path
         → 32/audio.m4s → VideoQuality
         → 32/video.m4s
```

### 3. ffmpeg_manager.py（FFmpeg管理）

**职责**：FFmpeg检测、下载和使用

**主要类**：
- `FFmpegManager`
  - `is_available()`：检查FFmpeg是否可用
  - `get_version()`：获取FFmpeg版本
  - `download_ffmpeg()`：下载FFmpeg
  - `merge_video()`：合并音视频

**检测顺序**：
1. 系统PATH中的ffmpeg
2. 项目目录下的ffmpeg/bin/ffmpeg.exe
3. 提示下载

**合并命令**：
```bash
ffmpeg -i video.m4s -i audio.m4s -c copy output.mp4
```

### 4. test_parser.py（测试脚本）

**职责**：功能测试和验证

**测试内容**：
- 单个缓存目录解析
- 目录扫描功能
- FFmpeg检测

## 数据模型

### BilibiliVideo

```python
@dataclass
class BilibiliVideo:
    cid: str                          # 549206412
    title: str                        # 视频标题
    owner_name: str                   # UP主名称
    bvid: str                         # BV1QZ4y1z7UT
    page_index: int                   # 分P索引（1, 2, 3...）
    page_title: str                   # 分P标题
    cache_dir: str                    # 缓存目录路径
    qualities: List[VideoQuality]     # 画质列表
    cover_url: str                    # 封面图URL（从entry.json获取）
    cover_path: str                   # 本地封面图路径（cover.jpg）
```

### VideoQuality

```python
@dataclass
class VideoQuality:
    quality_code: str      # "32", "64", "80"
    quality_desc: str      # "480P", "720P", "1080P"
    audio_path: str        # 音频文件绝对路径
    video_path: str        # 视频文件绝对路径
    total_size: int        # 总大小（字节）
```

## 工作流程

### 启动流程

```
启动程序
  ↓
检查FFmpeg
  ├─ 已安装 → 继续
  └─ 未安装 → 提示下载
      ├─ 用户确认 → 下载并安装
      └─ 用户取消 → 继续（功能受限）
  ↓
显示主界面
```

### 扫描流程

```
用户选择目录
  ↓
递归查找c_*目录
  ↓
解析每个entry.json
  ↓
扫描画质子目录
  ↓
检查audio.m4s和video.m4s
  ↓
创建BilibiliVideo对象
  ↓
显示视频卡片列表
```

### 播放流程

```
用户选择画质并点击播放
  ↓
检查临时目录是否有缓存
  ├─ 有缓存 → 直接打开
  └─ 无缓存 ↓
      合并音视频到临时文件
        ↓
      调用系统默认播放器
```

### 导出流程

```
用户选择画质并点击导出
  ↓
选择保存位置
  ↓
使用FFmpeg合并音视频
  ↓
保存到指定位置
  ↓
提示是否打开文件位置
```

## 技术特点

### 1. 模块化设计
- 解析、管理、GUI分离
- 高内聚、低耦合
- 便于测试和维护

### 2. 异步处理
- 使用线程处理耗时操作
- 避免UI冻结
- 提供进度反馈

### 3. 跨平台支持
- 使用pathlib处理路径
- 平台判断（Windows/macOS/Linux）
- 系统默认播放器调用

### 4. 错误处理
- try-except包装关键操作
- 用户友好的错误提示
- 日志输出便于调试

### 5. 用户体验
- 直观的卡片式UI
- 自动化工具检测
- 临时文件缓存

## 扩展建议

如果需要增强功能，可以考虑：

1. **数据库支持**：缓存扫描结果，加快启动速度
2. **弹幕支持**：读取danmaku.xml并嵌入视频
3. **批量操作**：批量导出、批量播放
4. **搜索过滤**：按标题、UP主、时间筛选
5. **封面显示**：从cover URL下载并显示缩略图
6. **进度显示**：FFmpeg实时进度条
7. **配置文件**：保存用户偏好设置
8. **多语言**：国际化支持

## 性能优化

当前实现的性能考虑：

1. **懒加载**：只在需要时合并视频
2. **临时文件缓存**：避免重复合并
3. **流复制模式**：FFmpeg不重新编码
4. **异步操作**：耗时任务使用线程

## 安全性

1. **路径验证**：防止路径遍历攻击
2. **输入清理**：文件名非法字符过滤
3. **超时控制**：FFmpeg执行超时保护
4. **错误隔离**：单个视频错误不影响整体

## 维护建议

1. **定期测试**：运行test_parser.py验证核心功能
2. **日志监控**：查看控制台输出发现问题
3. **版本管理**：使用Git追踪代码变更
4. **用户反馈**：收集使用问题并改进
