#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PixBridge v1.6
==============
一个用于达芬奇（DaVinci Resolve）的剪贴板图片自动导入工具

主要功能：
1. 实时监控系统剪贴板图片变化
2. 自动保存剪贴板图片到本地预设文件夹
3. 自动导入图片到达芬奇媒体池的 Clipboard_Assets 文件夹
4. 支持从浏览器直接复制图片导入
5. 🆕 支持批量选择多张图片导入
6. 提供友好的GUI界面和实时日志

作者: wukaiyu
版本: 1.6
日期: 2026-03-24
"""

import os
import sys
import time
import threading
import hashlib
from io import BytesIO
from pathlib import Path
from PIL import Image, ImageGrab

try:
    import AppKit
except ImportError:
    AppKit = None

from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QPushButton, QLineEdit, QFileDialog,
                             QTextEdit, QFrame, QMessageBox)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt6.QtGui import QFont, QColor, QPalette, QCursor

# --- 达芬奇 API 导入 ---
RESOLVE_SCRIPT_API = "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Modules/"
if RESOLVE_SCRIPT_API not in sys.path:
    sys.path.append(RESOLVE_SCRIPT_API)

try:
    import DaVinciResolveScript as dvr
except ImportError:
    dvr = None

# --- 版本信息 ---
VERSION = "1.6"
APP_NAME = "PixBridge"
MEDIA_FOLDER_NAME = "Clipboard_Assets"  # 达芬奇媒体池文件夹名称

# --- 支持的图片格式 ---
SUPPORTED_IMAGE_FORMATS = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.webp', '.heic'}

# --- 深色主题样式表 ---
DARK_THEME_STYLE = """
    QWidget {
        background-color: #121212;
        color: #FFFFFF;
        font-family: 'SF Pro', 'Inter', 'Helvetica Neue', 'Arial';
    }

    #MainContainer {
        border: 1px solid #333333;
        border-radius: 12px;
    }

    #TitleLabel {
        color: #FFFFFF !important;
        font-weight: 700;
        font-size: 22px;
        letter-spacing: -0.5px;
    }

    #VersionLabel {
        color: #888888;
        font-size: 11px;
        font-weight: 400;
    }

    #CardView {
        background-color: #1E1E1E;
        border: 1px solid #383838;
        border-radius: 12px;
    }

    QLineEdit {
        background-color: #000000;
        border: 1px solid #444444;
        border-radius: 8px;
        padding: 8px 12px;
        color: #FFFFFF !important;
        font-size: 13px;
        selection-background-color: #007AFF;
    }

    QLineEdit:focus {
        border: 1px solid #007AFF;
    }

    QPushButton#SecondaryButton {
        background-color: #333333;
        color: #E0E0E0;
        border: 1px solid #444444;
        border-radius: 6px;
        padding: 5px 12px;
        font-size: 12px;
    }
    QPushButton#SecondaryButton:hover {
        background-color: #444444;
        border: 1px solid #555555;
    }
    QPushButton#SecondaryButton:pressed {
        background-color: #222222;
    }

    QPushButton#ToggleButton {
        background-color: #007AFF;
        color: #FFFFFF;
        border: none;
        border-radius: 10px;
        padding: 12px 25px;
        font-size: 15px;
        font-weight: 700;
    }
    QPushButton#ToggleButton:hover {
        background-color: #0066DD;
    }
    QPushButton#ToggleButton[running="true"] {
        background-color: #E02020;
    }
    QPushButton#ToggleButton[running="true"]:hover {
        background-color: #C01818;
    }

    QTextEdit {
        background-color: #0A0A0A;
        border: 1px solid #222222;
        border-radius: 10px;
        color: #AAAAAA !important;
        font-family: 'Monaco', 'Menlo', 'Consolas', 'Courier New';
        font-size: 11px;
        padding: 10px;
    }

    QLabel {
        color: #FFFFFF !important;
    }
"""


class SignalHandler(QObject):
    """信号处理器，用于线程安全的UI更新"""
    log_signal = pyqtSignal(str)
    import_success_signal = pyqtSignal(str)


class PixBridge(QWidget):
    """PixBridge 主窗口类"""

    def __init__(self):
        super().__init__()

        # 初始化信号处理器
        self.signal_handler = SignalHandler()
        self.signal_handler.log_signal.connect(self._append_log)
        self.signal_handler.import_success_signal.connect(self._on_import_success)

        # 窗口设置
        self.setWindowTitle(f"{APP_NAME} v{VERSION}")
        self.resize(550, 600)

        # 应用深色主题
        self.force_dark_palette()
        self.setStyleSheet(DARK_THEME_STYLE)

        # 默认保存路径
        self.save_dir = os.path.expanduser(f"~/Downloads/{MEDIA_FOLDER_NAME}")

        # 运行状态
        self.is_running = False

        # 剪贴板监控
        self.pb = AppKit.NSPasteboard.generalPasteboard() if AppKit else None

        # 统计信息
        self.import_count = 0

        # 图片去重：记录已处理过的图片哈希值
        self.processed_image_hashes = set()

        # 最后处理的剪贴板计数（用于检测新的复制操作）
        self.last_processed_change_count = None

        # 初始化UI
        self.setup_ui()

        # 启动时检查达芬奇连接
        self.check_resolve_connection()

    def force_dark_palette(self):
        """强制应用深色调色板"""
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(18, 18, 18))
        palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.Base, QColor(0, 0, 0))
        palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.Button, QColor(40, 40, 40))
        palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.white)
        QApplication.setPalette(palette)

    def setup_ui(self):
        """设置用户界面"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(25, 20, 25, 25)
        layout.setSpacing(20)

        # === 标题栏 ===
        header = QHBoxLayout()
        icon = QLabel("🖼️")
        icon.setFont(QFont("Apple Color Emoji", 26))

        title_container = QVBoxLayout()
        title = QLabel(f"{APP_NAME}")
        title.setObjectName("TitleLabel")

        version_label = QLabel(f"v{VERSION} - 达芬奇剪贴板图片导入工具")
        version_label.setObjectName("VersionLabel")

        title_container.addWidget(title)
        title_container.addWidget(version_label)
        title_container.setSpacing(2)

        header.addWidget(icon)
        header.addLayout(title_container)
        header.addStretch()
        layout.addLayout(header)

        # === 路径设置区 ===
        self.path_card = QFrame()
        self.path_card.setObjectName("CardView")
        p_layout = QVBoxLayout(self.path_card)
        p_layout.setContentsMargins(15, 15, 15, 15)
        p_layout.setSpacing(10)

        path_label = QLabel("📁 本地保存路径")
        path_label.setStyleSheet("font-weight: 600; font-size: 13px;")

        path_input_layout = QHBoxLayout()
        folder_icon = QLabel("📂")
        self.path_input = QLineEdit(self.save_dir)
        self.path_input.setPlaceholderText("选择图片保存位置...")

        btn_chg = QPushButton("浏览")
        btn_chg.setObjectName("SecondaryButton")
        btn_chg.clicked.connect(self.select_folder)

        btn_open = QPushButton("打开文件夹")
        btn_open.setObjectName("SecondaryButton")
        btn_open.clicked.connect(self.open_save_folder)

        path_input_layout.addWidget(folder_icon)
        path_input_layout.addWidget(self.path_input)
        path_input_layout.addWidget(btn_chg)
        path_input_layout.addWidget(btn_open)

        p_layout.addWidget(path_label)
        p_layout.addLayout(path_input_layout)
        layout.addWidget(self.path_card)

        # === 状态信息区 ===
        self.status_card = QFrame()
        self.status_card.setObjectName("CardView")
        s_layout = QVBoxLayout(self.status_card)
        s_layout.setContentsMargins(15, 15, 15, 15)
        s_layout.setSpacing(8)

        status_title = QLabel("📊 状态信息")
        status_title.setStyleSheet("font-weight: 600; font-size: 13px;")

        self.status_label = QLabel("⏸️ 服务未启动")
        self.status_label.setStyleSheet("color: #888888; font-size: 12px;")

        self.import_count_label = QLabel(f"已导入: {self.import_count} 张图片")
        self.import_count_label.setStyleSheet("color: #888888; font-size: 12px;")

        self.cache_label = QLabel(f"缓存记录: {len(self.processed_image_hashes)} 个")
        self.cache_label.setStyleSheet("color: #888888; font-size: 12px;")

        self.folder_info_label = QLabel(f"目标文件夹: {MEDIA_FOLDER_NAME}")
        self.folder_info_label.setStyleSheet("color: #888888; font-size: 12px;")

        s_layout.addWidget(status_title)
        s_layout.addWidget(self.status_label)
        s_layout.addWidget(self.import_count_label)
        s_layout.addWidget(self.cache_label)
        s_layout.addWidget(self.folder_info_label)
        layout.addWidget(self.status_card)

        # === 主控制按钮 ===
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)

        self.btn_toggle = QPushButton("▶️ 开启实时监听")
        self.btn_toggle.setObjectName("ToggleButton")
        self.btn_toggle.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_toggle.clicked.connect(self.toggle_service)

        self.btn_clear_cache = QPushButton("🗑️ 清除缓存")
        self.btn_clear_cache.setObjectName("SecondaryButton")
        self.btn_clear_cache.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_clear_cache.clicked.connect(self.clear_cache)

        button_layout.addStretch()
        button_layout.addWidget(self.btn_clear_cache)
        button_layout.addWidget(self.btn_toggle)
        button_layout.addStretch()

        layout.addLayout(button_layout)

        # === 日志输出区 ===
        log_label = QLabel("📝 运行日志")
        log_label.setStyleSheet("font-weight: 600; font-size: 13px; margin-top: 5px;")
        layout.addWidget(log_label)

        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setMaximumHeight(180)
        layout.addWidget(self.log_area)

        # 添加帮助信息
        help_text = QLabel("💡 提示: 从浏览器或任何应用复制图片后，会自动导入到达芬奇")
        help_text.setStyleSheet("color: #666666; font-size: 11px; font-style: italic;")
        help_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(help_text)

        # 初始日志
        self.log(f"🎉 <b>{APP_NAME} v{VERSION}</b> 已启动")
        self.log(f"💾 默认保存路径: <code>{self.save_dir}</code>")

    def log(self, message):
        """添加日志信息（线程安全）"""
        self.signal_handler.log_signal.emit(message)

    def _append_log(self, message):
        """实际添加日志到UI（在主线程执行）"""
        timestamp = time.strftime('%H:%M:%S')
        self.log_area.append(
            f'<span style="color:#666666;">[{timestamp}]</span> '
            f'<span style="color:#DDDDDD;">{message}</span>'
        )
        self.log_area.moveCursor(self.log_area.textCursor().MoveOperation.End)

    def check_resolve_connection(self):
        """检查达芬奇连接状态"""
        if not dvr:
            self.log("⚠️ <span style='color:#FFA500;'>无法加载达芬奇API模块</span>")
            return

        try:
            resolve = dvr.scriptapp("Resolve")
            if resolve:
                proj = resolve.GetProjectManager().GetCurrentProject()
                if proj:
                    self.log(f"✅ 已连接到达芬奇项目: <b>{proj.GetName()}</b>")
                else:
                    self.log("⚠️ <span style='color:#FFA500;'>达芬奇未打开项目</span>")
            else:
                self.log("⚠️ <span style='color:#FFA500;'>无法连接到达芬奇</span>")
        except Exception as e:
            self.log(f"❌ 连接达芬奇失败: {e}")

    def select_folder(self):
        """选择保存文件夹"""
        folder = QFileDialog.getExistingDirectory(
            self,
            "选择图片保存路径",
            self.save_dir
        )
        if folder:
            self.save_dir = folder
            self.path_input.setText(folder)
            self.log(f"📁 保存路径已更新: <code>{folder}</code>")

    def open_save_folder(self):
        """打开保存文件夹"""
        if not os.path.exists(self.save_dir):
            os.makedirs(self.save_dir)

        os.system(f'open "{self.save_dir}"')
        self.log(f"📂 已打开文件夹: <code>{self.save_dir}</code>")

    def clear_cache(self):
        """清除图片哈希缓存"""
        cache_count = len(self.processed_image_hashes)
        self.processed_image_hashes.clear()
        self.cache_label.setText(f"缓存记录: 0 个")
        self.log(f"🗑️ 已清除 {cache_count} 个缓存记录")

        # 提示用户
        QMessageBox.information(
            self,
            "缓存已清除",
            f"已清除 {cache_count} 个图片哈希记录。\n\n现在可以重新导入之前的图片了。"
        )

    def toggle_service(self):
        """切换监听服务状态"""
        if not self.is_running:
            # 启动前检查
            if not self.pb:
                QMessageBox.warning(
                    self,
                    "系统不兼容",
                    "当前系统不支持剪贴板监控功能\n(仅支持 macOS)"
                )
                return

            if not dvr:
                reply = QMessageBox.question(
                    self,
                    "达芬奇API未加载",
                    "无法连接到达芬奇API，图片只会保存到本地。\n是否继续？",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if reply == QMessageBox.StandardButton.No:
                    return

            # 启动服务
            self.is_running = True
            self.btn_toggle.setText("⏹️ 停止监听")
            self.btn_toggle.setProperty("running", "true")
            self.btn_toggle.style().polish(self.btn_toggle)

            self.status_label.setText("🟢 监听中...")
            self.status_label.setStyleSheet("color: #00FF00; font-size: 12px;")

            self.log("🚀 <b style='color:#007AFF;'>服务已启动，正在监控剪贴板...</b>")

            # 启动监控线程
            threading.Thread(target=self.monitor_loop, daemon=True).start()
        else:
            # 停止服务
            self.is_running = False
            self.btn_toggle.setText("▶️ 开启实时监听")
            self.btn_toggle.setProperty("running", "false")
            self.btn_toggle.style().polish(self.btn_toggle)

            self.status_label.setText("⏸️ 服务已停止")
            self.status_label.setStyleSheet("color: #888888; font-size: 12px;")

            self.log("🛑 监听服务已安全停止")

    def monitor_loop(self):
        """剪贴板监控循环（在后台线程运行）"""
        if not self.pb:
            return

        # 初始化：记录启动时的剪贴板状态
        last_count = self.pb.changeCount()
        self.last_processed_change_count = last_count
        self.log("👀 开始监控剪贴板变化...")
        self.log("💡 只有在按下 Cmd+C 或右键复制后才会导入新图片")

        while self.is_running:
            try:
                current_count = self.pb.changeCount()

                # 检测到剪贴板变化（新的复制操作）
                if current_count != last_count:
                    # 获取剪贴板内容类型
                    types = [str(t) for t in self.pb.types()]

                    # 检查是否包含图片
                    if any("tiff" in t.lower() or "png" in t.lower() or
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

    def calculate_image_hash(self, img):
        """
        计算图片的MD5哈希值，用于去重

        Args:
            img: PIL Image 对象

        Returns:
            str: 图片的MD5哈希值
        """
        try:
            # 将图片转换为字节流
            img_byte_arr = BytesIO()
            img.save(img_byte_arr, format='PNG')
            img_bytes = img_byte_arr.getvalue()

            # 计算MD5哈希
            return hashlib.md5(img_bytes).hexdigest()
        except Exception as e:
            self.log(f"⚠️ 计算图片哈希失败: {e}")
            return None

    def detect_clipboard_images(self):
        """
        检测剪贴板中的图片（支持单张和多张）

        Returns:
            list: 图片列表，每个元素是 PIL Image 对象或文件路径
        """
        images = []

        # 方法1: 检测文件路径（支持多文件）
        if AppKit:
            try:
                pasteboard = AppKit.NSPasteboard.generalPasteboard()
                file_urls = pasteboard.propertyListForType_(AppKit.NSFilenamesPboardType)

                if file_urls:
                    for url in file_urls:
                        file_path = Path(url)
                        if file_path.suffix.lower() in SUPPORTED_IMAGE_FORMATS:
                            images.append(('file', file_path))

                    if images:
                        return images
            except Exception as e:
                self.log(f"⚠️ 检测文件路径失败: {e}")

        # 方法2: 检测剪贴板图片数据（单张）
        img = ImageGrab.grabclipboard()
        if img:
            images.append(('clipboard', img))

        return images

    def do_import(self):
        """执行图片导入操作（在主线程运行）- v1.6 支持批量"""
        try:
            # 检测剪贴板中的图片（支持多张）
            images = self.detect_clipboard_images()

            if not images:
                self.log("⚠️ 剪贴板中没有有效的图片数据")
                return

            # 显示检测到的图片数量
            self.log(f"📦 检测到 {len(images)} 张图片")

            # 确保保存目录存在
            if not os.path.exists(self.save_dir):
                os.makedirs(self.save_dir)
                self.log(f"📁 创建保存目录: <code>{self.save_dir}</code>")

            # 批量处理图片
            saved_files = []
            skipped_count = 0

            for idx, (source_type, image_data) in enumerate(images, 1):
                try:
                    # 获取图片对象
                    if source_type == 'file':
                        # 从文件加载图片
                        img = Image.open(image_data)
                        original_name = image_data.name
                    else:  # clipboard
                        img = image_data
                        original_name = f"clipboard_{idx}.png"

                    # 计算图片哈希，检查是否已处理过
                    img_hash = self.calculate_image_hash(img)

                    if img_hash is None:
                        self.log(f"⚠️ 无法验证图片 {idx}，跳过")
                        continue

                    if img_hash in self.processed_image_hashes:
                        self.log(f"ℹ️ [{idx}/{len(images)}] 已导入过，跳过: {original_name}")
                        skipped_count += 1
                        continue

                    # 将哈希值加入已处理集合
                    self.processed_image_hashes.add(img_hash)

                    # 生成唯一文件名
                    timestamp = int(time.time() * 1000)
                    filename = f"clip_{timestamp}.png"
                    filepath = os.path.join(self.save_dir, filename)

                    # 保存图片到本地
                    img.save(filepath, "PNG")
                    file_size = os.path.getsize(filepath) / 1024  # KB

                    self.log(f"💾 [{idx}/{len(images)}] 已保存: <code>{filename}</code> ({file_size:.1f} KB)")

                    saved_files.append((filepath, filename))

                    # 稍微延迟避免文件名冲突
                    time.sleep(0.001)

                except Exception as e:
                    self.log(f"❌ 处理图片 {idx} 失败: {e}")
                    continue

            # 批量导入到达芬奇
            if saved_files:
                self.log(f"📤 开始导入 {len(saved_files)} 张图片到达芬奇...")
                success_count = self.batch_import_to_resolve(saved_files)

                if success_count > 0:
                    self.import_count += success_count
                    self.signal_handler.import_success_signal.emit(str(success_count))
                    self.log(f"✅ 成功导入 {success_count} 张图片到达芬奇")
                else:
                    self.log("⚠️ 导入到达芬奇失败")
            else:
                self.log(f"ℹ️ 没有新图片需要导入")

            # 总结
            if skipped_count > 0:
                self.log(f"📊 总结: 导入 {len(saved_files)} 张，跳过 {skipped_count} 张（已存在）")

        except Exception as e:
            self.log(f"❌ <span style='color:#FF4444;'>导入失败: {e}</span>")
            import traceback
            self.log(f"<span style='color:#FF4444;'>{traceback.format_exc()}</span>")

    def _on_import_success(self, filename):
        """导入成功后更新UI"""
        self.import_count_label.setText(f"已导入: {self.import_count} 张图片")
        self.cache_label.setText(f"缓存记录: {len(self.processed_image_hashes)} 个")

    def batch_import_to_resolve(self, files):
        """
        批量导入图片到达芬奇媒体池（v1.6 新增）

        Args:
            files: 文件列表，每个元素是 (filepath, filename) 元组

        Returns:
            int: 成功导入的文件数量
        """
        if not dvr:
            self.log("⚠️ 达芬奇API不可用，跳过导入")
            return 0

        try:
            # 获取达芬奇实例
            resolve = dvr.scriptapp("Resolve")
            if not resolve:
                self.log("❌ 无法连接到达芬奇")
                return 0

            # 获取当前项目
            project_manager = resolve.GetProjectManager()
            project = project_manager.GetCurrentProject()

            if not project:
                self.log("❌ 达芬奇未打开项目")
                return 0

            # 获取媒体池
            media_pool = project.GetMediaPool()
            root_folder = media_pool.GetRootFolder()

            # 查找或创建目标文件夹
            target_bin = None
            subfolders = root_folder.GetSubFolderList()

            for folder in subfolders:
                if folder.GetName() == MEDIA_FOLDER_NAME:
                    target_bin = folder
                    break

            # 如果文件夹不存在，创建它
            if not target_bin:
                target_bin = media_pool.AddSubFolder(root_folder, MEDIA_FOLDER_NAME)
                self.log(f"📁 已创建媒体文件夹: <b>{MEDIA_FOLDER_NAME}</b>")

            # 设置当前文件夹
            media_pool.SetCurrentFolder(target_bin)

            # 批量导入媒体文件
            file_paths = [filepath for filepath, filename in files]
            imported_clips = media_pool.ImportMedia(file_paths)

            if imported_clips:
                success_count = len(imported_clips) if isinstance(imported_clips, list) else 1
                self.log(f"🎞️ <b style='color:#00FF00;'>批量导入成功</b>: {success_count} 张图片")
                return success_count
            else:
                self.log(f"⚠️ 批量导入失败")
                return 0

        except Exception as e:
            self.log(f"❌ 达芬奇批量导入错误: {e}")
            import traceback
            self.log(f"<span style='color:#FF4444;'>{traceback.format_exc()}</span>")
            return 0

    def import_to_resolve(self, filepath, filename):
        """导入图片到达芬奇媒体池"""
        if not dvr:
            self.log("⚠️ 达芬奇API不可用，跳过导入")
            return False

        try:
            # 获取达芬奇实例
            resolve = dvr.scriptapp("Resolve")
            if not resolve:
                self.log("❌ 无法连接到达芬奇")
                return False

            # 获取当前项目
            project_manager = resolve.GetProjectManager()
            project = project_manager.GetCurrentProject()

            if not project:
                self.log("❌ 达芬奇未打开项目")
                return False

            # 获取媒体池
            media_pool = project.GetMediaPool()
            root_folder = media_pool.GetRootFolder()

            # 查找或创建目标文件夹
            target_bin = None
            subfolders = root_folder.GetSubFolderList()

            for folder in subfolders:
                if folder.GetName() == MEDIA_FOLDER_NAME:
                    target_bin = folder
                    break

            # 如果文件夹不存在，创建它
            if not target_bin:
                target_bin = media_pool.AddSubFolder(root_folder, MEDIA_FOLDER_NAME)
                self.log(f"📁 已创建媒体文件夹: <b>{MEDIA_FOLDER_NAME}</b>")

            # 设置当前文件夹
            media_pool.SetCurrentFolder(target_bin)

            # 导入媒体文件
            imported_clips = media_pool.ImportMedia([filepath])

            if imported_clips:
                self.log(f"🎞️ <b style='color:#00FF00;'>成功导入到达芬奇</b>: <code>{filename}</code>")
                return True
            else:
                self.log(f"⚠️ 导入到达芬奇失败: <code>{filename}</code>")
                return False

        except Exception as e:
            self.log(f"❌ 达芬奇导入错误: {e}")
            import traceback
            self.log(f"<span style='color:#FF4444;'>{traceback.format_exc()}</span>")
            return False


def main():
    """主函数"""
    app = QApplication(sys.argv)

    # 使用 Fusion 风格以获得更好的跨平台一致性
    app.setStyle("Fusion")

    # 创建并显示主窗口
    window = PixBridge()
    window.show()

    # 运行应用
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
