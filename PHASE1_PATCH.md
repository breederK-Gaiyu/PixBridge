# PixBridge v1.6 Phase 1: 文件检测功能补丁

这个文件说明如何将 v1.5 升级到 v1.6 Phase 1（文件检测功能）

## 🎯 Phase 1 目标
- 检测剪贴板中的文件（图片/视频/音频）
- 识别文件类型
- 支持多文件检测

## 📝 需要修改的部分

### 1. 添加导入
在文件顶部添加：
```python
from pathlib import Path
import shutil
```

### 2. 添加文件格式配置（在 VERSION 之后）
```python
# --- 支持的文件格式 ---
SUPPORTED_FORMATS = {
    'image': {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.webp', '.heic'},
    'video': {'.mp4', '.mov', '.avi', '.mkv', '.flv', '.wmv', '.m4v', '.mpg', '.mpeg', '.3gp'},
    'audio': {'.mp3', '.wav', '.aac', '.flac', '.m4a', '.ogg', '.wma', '.aiff', '.alac'}
}

# --- 媒体文件夹配置 ---
MEDIA_FOLDERS = {
    'image': 'Clipboard_Images',
    'video': 'Clipboard_Videos',
    'audio': 'Clipboard_Audios'
}
```

### 3. 在 PixBridge 类中添加新方法

在 `check_resolve_connection()` 方法之后添加：

```python
    def detect_media_type(self, file_path):
        """
        根据文件扩展名判断媒体类型

        Args:
            file_path: Path 对象或字符串路径

        Returns:
            str: 'image', 'video', 'audio' 或 None
        """
        if isinstance(file_path, str):
            file_path = Path(file_path)

        ext = file_path.suffix.lower()

        for media_type, extensions in SUPPORTED_FORMATS.items():
            if ext in extensions:
                return media_type

        return None

    def detect_clipboard_files(self):
        """
        检测剪贴板中的文件列表

        Returns:
            list: 文件信息字典列表，每个包含 'path' 和 'type'
        """
        if not self.pb:
            return []

        try:
            # 获取文件 URL 列表（macOS 特有）
            file_urls = self.pb.propertyListForType_(AppKit.NSFilenamesPboardType)

            if not file_urls:
                return []

            files = []
            for url in file_urls:
                file_path = Path(url)

                # 检查文件是否存在
                if not file_path.exists():
                    continue

                # 判断媒体类型
                media_type = self.detect_media_type(file_path)

                if media_type:
                    files.append({
                        'path': file_path,
                        'type': media_type,
                        'name': file_path.name,
                        'size': file_path.stat().st_size
                    })

            return files

        except Exception as e:
            self.log(f"⚠️ 检测文件失败: {e}")
            return []

    def calculate_file_hash(self, file_path):
        """
        计算文件的MD5哈希值

        Args:
            file_path: 文件路径

        Returns:
            str: 文件的MD5哈希值
        """
        try:
            hash_md5 = hashlib.md5()
            with open(file_path, "rb") as f:
                # 分块读取以处理大文件
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception as e:
            self.log(f"⚠️ 计算文件哈希失败: {e}")
            return None
```

### 4. 修改 monitor_loop() 方法

找到 `monitor_loop()` 方法，在检测图片的部分之后添加文件检测：

```python
    def monitor_loop(self):
        """剪贴板监控循环（在后台线程运行）"""
        if not self.pb:
            return

        # 初始化：记录启动时的剪贴板状态
        last_count = self.pb.changeCount()
        self.last_processed_change_count = last_count
        self.log("👀 开始监控剪贴板变化...")
        self.log("💡 只有在按下 Cmd+C 或右键复制后才会导入")

        while self.is_running:
            try:
                current_count = self.pb.changeCount()

                # 检测到剪贴板变化（新的复制操作）
                if current_count != last_count:
                    # 获取剪贴板内容类型
                    types = [str(t) for t in self.pb.types()]

                    # 优先检查文件（新增）
                    if AppKit.NSFilenamesPboardType in self.pb.types():
                        files = self.detect_clipboard_files()

                        if files:
                            self.log(f"📦 检测到 {len(files)} 个文件")
                            for f in files:
                                size_mb = f['size'] / (1024 * 1024)
                                self.log(f"  - {f['name']} ({f['type']}, {size_mb:.2f} MB)")

                            # 稍微延迟
                            time.sleep(0.3)

                            # TODO: 在 Phase 3 实现批量导入
                            # QTimer.singleShot(0, lambda: self.batch_import(files))
                            self.log("ℹ️ 批量导入功能将在 Phase 3 实现")

                    # 检查图片（原有功能保留）
                    elif any("tiff" in t.lower() or "png" in t.lower() or
                           "jpeg" in t.lower() or "image" in t.lower() for t in types):

                        self.log("🖼️ 检测到新的复制操作，正在检查图片...")

                        # 稍微延迟以确保剪贴板数据完全就绪
                        time.sleep(0.3)

                        # 在主线程执行导入操作
                        QTimer.singleShot(0, self.do_import)

                    last_count = current_count

                # 检查间隔
                time.sleep(0.5)

            except Exception as e:
                self.log(f"⚠️ 监控循环错误: {e}")
                time.sleep(1)
```

## ✅ Phase 1 完成后的功能

运行升级后的脚本，你应该能看到：
1. 复制图片文件时，显示文件信息（类型、大小）
2. 复制视频文件时，识别为 video 类型
3. 复制音频文件时，识别为 audio 类型
4. 支持同时复制多个文件

## 🧪 测试方法

1. **测试图片文件**：
   - 在 Finder 中复制一个 .jpg 文件
   - 应该看到：`📦 检测到 1 个文件` 和 `- xxx.jpg (image, 0.50 MB)`

2. **测试视频文件**：
   - 复制一个 .mp4 文件
   - 应该看到：`- xxx.mp4 (video, 15.30 MB)`

3. **测试批量文件**：
   - 同时选中多个文件（图片+视频）并复制
   - 应该列出所有文件

## 📋 下一步

Phase 1 完成后，我们将实现：
- Phase 2: 类型选择器 UI（复选框）
- Phase 3: 批量导入功能

---

**注意**：这个补丁只是检测文件，还不会导入。完整的导入功能将在 Phase 3 实现。
