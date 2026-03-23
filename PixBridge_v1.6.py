#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PixBridge v1.6
==============
一个用于达芬奇（DaVinci Resolve）的剪贴板多媒体自动导入工具

主要功能：
1. 支持图片、视频、音频三种媒体类型
2. 可选择性监控特定媒体类型
3. 自动分类导入到不同的媒体文件夹
4. 批量导入多个文件
5. 文件预览面板
6. 格式过滤器
7. 完整的导入历史记录

作者: wukaiyu
版本: 1.6
日期: 2026-03-23
"""

import os
import sys
import time
import threading
import hashlib
import json
from io import BytesIO
from datetime import datetime
from PIL import ImageGrab, Image
from pathlib import Path

try:
    import AppKit
except ImportError:
    AppKit = None

from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QPushButton, QLineEdit, QFileDialog,
                             QTextEdit, QFrame, QMessageBox, QCheckBox,
                             QGroupBox, QScrollArea, QListWidget, QListWidgetItem,
                             QTableWidget, QTableWidgetItem, QHeaderView,
                             QTabWidget, QSplitter)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject, QSize
from PyQt6.QtGui import QFont, QColor, QPalette, QCursor, QPixmap

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

# --- 媒体文件夹配置 ---
MEDIA_FOLDERS = {
    'image': 'Clipboard_Images',
    'video': 'Clipboard_Videos',
    'audio': 'Clipboard_Audios'
}

# --- 支持的文件格式 ---
SUPPORTED_FORMATS = {
    'image': {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.webp', '.heic'},
    'video': {'.mp4', '.mov', '.avi', '.mkv', '.flv', '.wmv', '.m4v', '.mpg', '.mpeg'},
    'audio': {'.mp3', '.wav', '.aac', '.flac', '.m4a', '.ogg', '.wma', '.aiff'}
}

# --- 深色主题样式表 ---
DARK_THEME_STYLE = """
    QWidget {
        background-color: #121212;
        color: #FFFFFF;
        font-family: 'SF Pro', 'Inter', 'Helvetica Neue', 'Arial';
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

    QCheckBox {
        color: #FFFFFF;
        font-size: 13px;
        spacing: 8px;
    }
    QCheckBox::indicator {
        width: 18px;
        height: 18px;
        border-radius: 4px;
        border: 2px solid #444444;
        background-color: #000000;
    }
    QCheckBox::indicator:checked {
        background-color: #007AFF;
        border-color: #007AFF;
    }
    QCheckBox::indicator:hover {
        border-color: #007AFF;
    }

    QGroupBox {
        color: #FFFFFF;
        border: 1px solid #383838;
        border-radius: 8px;
        margin-top: 10px;
        padding-top: 10px;
        font-weight: 600;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        left: 10px;
        padding: 0 5px;
    }

    QTableWidget {
        background-color: #0A0A0A;
        border: 1px solid #222222;
        border-radius: 8px;
        color: #CCCCCC;
        gridline-color: #333333;
    }
    QTableWidget::item {
        padding: 5px;
    }
    QTableWidget::item:selected {
        background-color: #007AFF;
    }
    QHeaderView::section {
        background-color: #1E1E1E;
        color: #FFFFFF;
        padding: 8px;
        border: none;
        border-bottom: 1px solid #333333;
        font-weight: 600;
    }

    QTabWidget::pane {
        border: 1px solid #383838;
        border-radius: 8px;
        background-color: #1E1E1E;
    }
    QTabBar::tab {
        background-color: #1E1E1E;
        color: #888888;
        padding: 10px 20px;
        border: 1px solid #383838;
        border-bottom: none;
        border-top-left-radius: 8px;
        border-top-right-radius: 8px;
    }
    QTabBar::tab:selected {
        background-color: #007AFF;
        color: #FFFFFF;
    }
    QTabBar::tab:hover:!selected {
        background-color: #2A2A2A;
        color: #FFFFFF;
    }

    QLabel {
        color: #FFFFFF !important;
    }
"""


class SignalHandler(QObject):
    """信号处理器，用于线程安全的UI更新"""
    log_signal = pyqtSignal(str)
    import_success_signal = pyqtSignal(str, str)  # filename, media_type
    update_preview_signal = pyqtSignal(list)  # file_list


class MediaTypeSelector(QGroupBox):
    """媒体类型选择器组件"""

    def __init__(self, parent=None):
        super().__init__("📂 媒体类型选择", parent)
        self.setup_ui()

    def setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 20, 15, 15)
        layout.setSpacing(20)

        # 图片选择
        self.cb_image = QCheckBox("🖼️ 图片")
        self.cb_image.setChecked(True)

        # 视频选择
        self.cb_video = QCheckBox("🎬 视频")
        self.cb_video.setChecked(False)

        # 音频选择
        self.cb_audio = QCheckBox("🎵 音频")
        self.cb_audio.setChecked(False)

        # 全选按钮
        self.btn_select_all = QPushButton("全选")
        self.btn_select_all.setObjectName("SecondaryButton")
        self.btn_select_all.clicked.connect(self.select_all)

        # 取消全选
        self.btn_deselect_all = QPushButton("取消全选")
        self.btn_deselect_all.setObjectName("SecondaryButton")
        self.btn_deselect_all.clicked.connect(self.deselect_all)

        layout.addWidget(self.cb_image)
        layout.addWidget(self.cb_video)
        layout.addWidget(self.cb_audio)
        layout.addStretch()
        layout.addWidget(self.btn_select_all)
        layout.addWidget(self.btn_deselect_all)

    def select_all(self):
        """全选"""
        self.cb_image.setChecked(True)
        self.cb_video.setChecked(True)
        self.cb_audio.setChecked(True)

    def deselect_all(self):
        """取消全选"""
        self.cb_image.setChecked(False)
        self.cb_video.setChecked(False)
        self.cb_audio.setChecked(False)

    def get_selected_types(self):
        """获取选中的媒体类型"""
        types = []
        if self.cb_image.isChecked():
            types.append('image')
        if self.cb_video.isChecked():
            types.append('video')
        if self.cb_audio.isChecked():
            types.append('audio')
        return types


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
        self.resize(900, 750)

        # 应用深色主题
        self.force_dark_palette()
        self.setStyleSheet(DARK_THEME_STYLE)

        # 默认保存路径
        self.save_dir = os.path.expanduser(f"~/Downloads/Clipboard_Assets")

        # 运行状态
        self.is_running = False

        # 剪贴板监控
        self.pb = AppKit.NSPasteboard.generalPasteboard() if AppKit else None

        # 统计信息
        self.import_count = {
            'image': 0,
            'video': 0,
            'audio': 0
        }

        # 图片去重：记录已处理过的文件哈希值
        self.processed_hashes = set()

        # 最后处理的剪贴板计数
        self.last_processed_change_count = None

        # 导入历史记录
        self.import_history = []

        # 初始化UI
        self.setup_ui()

        # 启动时检查达芬奇连接
        self.check_resolve_connection()

        # 加载历史记录
        self.load_history()

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
        layout.setSpacing(15)

        # === 标题栏 ===
        header = QHBoxLayout()
        icon = QLabel("🖼️")
        icon.setFont(QFont("Apple Color Emoji", 26))

        title_container = QVBoxLayout()
        title = QLabel(f"{APP_NAME}")
        title.setObjectName("TitleLabel")

        version_label = QLabel(f"v{VERSION} - 多媒体剪贴板自动导入工具")
        version_label.setObjectName("VersionLabel")

        title_container.addWidget(title)
        title_container.addWidget(version_label)
        title_container.setSpacing(2)

        header.addWidget(icon)
        header.addLayout(title_container)
        header.addStretch()
        layout.addLayout(header)

        # === 媒体类型选择器 ===
        self.media_selector = MediaTypeSelector()
        layout.addWidget(self.media_selector)

        # === 主内容区（使用 Tab）===
        self.tab_widget = QTabWidget()

        # Tab 1: 主控制面板
        self.setup_main_tab()

        # Tab 2: 导入历史
        self.setup_history_tab()

        layout.addWidget(self.tab_widget)

        # === 控制按钮 ===
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

        # 初始日志
        self.log(f"🎉 <b>{APP_NAME} v{VERSION}</b> 已启动")
        self.log(f"💾 默认保存路径: <code>{self.save_dir}</code>")

    def setup_main_tab(self):
        """设置主控制标签页"""
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(15)

        # 路径设置区
        path_card = QFrame()
        path_card.setObjectName("CardView")
        p_layout = QVBoxLayout(path_card)
        p_layout.setContentsMargins(15, 15, 15, 15)
        p_layout.setSpacing(10)

        path_label = QLabel("📁 本地保存路径")
        path_label.setStyleSheet("font-weight: 600; font-size: 13px;")

        path_input_layout = QHBoxLayout()
        folder_icon = QLabel("📂")
        self.path_input = QLineEdit(self.save_dir)
        self.path_input.setPlaceholderText("选择文件保存位置...")

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
        main_layout.addWidget(path_card)

        # 状态信息区
        status_card = QFrame()
        status_card.setObjectName("CardView")
        s_layout = QVBoxLayout(status_card)
        s_layout.setContentsMargins(15, 15, 15, 15)
        s_layout.setSpacing(8)

        status_title = QLabel("📊 状态信息")
        status_title.setStyleSheet("font-weight: 600; font-size: 13px;")

        self.status_label = QLabel("⏸️ 服务未启动")
        self.status_label.setStyleSheet("color: #888888; font-size: 12px;")

        # 分类型统计
        stats_layout = QHBoxLayout()
        self.image_count_label = QLabel(f"🖼️ 图片: 0")
        self.video_count_label = QLabel(f"🎬 视频: 0")
        self.audio_count_label = QLabel(f"🎵 音频: 0")

        for label in [self.image_count_label, self.video_count_label, self.audio_count_label]:
            label.setStyleSheet("color: #888888; font-size: 12px;")
            stats_layout.addWidget(label)
        stats_layout.addStretch()

        self.cache_label = QLabel(f"缓存记录: 0 个")
        self.cache_label.setStyleSheet("color: #888888; font-size: 12px;")

        s_layout.addWidget(status_title)
        s_layout.addWidget(self.status_label)
        s_layout.addLayout(stats_layout)
        s_layout.addWidget(self.cache_label)
        main_layout.addWidget(status_card)

        # 日志输出区
        log_label = QLabel("📝 运行日志")
        log_label.setStyleSheet("font-weight: 600; font-size: 13px;")
        main_layout.addWidget(log_label)

        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setMaximumHeight(200)
        main_layout.addWidget(self.log_area)

        # 帮助信息
        help_text = QLabel("💡 提示: 选择媒体类型后，复制文件即可自动导入")
        help_text.setStyleSheet("color: #666666; font-size: 11px; font-style: italic;")
        help_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(help_text)

        self.tab_widget.addTab(main_widget, "主控制面板")

    def setup_history_tab(self):
        """设置导入历史标签页"""
        history_widget = QWidget()
        history_layout = QVBoxLayout(history_widget)
        history_layout.setContentsMargins(10, 10, 10, 10)

        # 历史记录表格
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(5)
        self.history_table.setHorizontalHeaderLabels(["时间", "文件名", "类型", "大小", "状态"])

        # 设置列宽
        header = self.history_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)

        history_layout.addWidget(self.history_table)

        # 历史操作按钮
        history_btn_layout = QHBoxLayout()

        btn_export = QPushButton("📤 导出历史")
        btn_export.setObjectName("SecondaryButton")
        btn_export.clicked.connect(self.export_history)

        btn_clear_history = QPushButton("🗑️ 清空历史")
        btn_clear_history.setObjectName("SecondaryButton")
        btn_clear_history.clicked.connect(self.clear_history)

        history_btn_layout.addStretch()
        history_btn_layout.addWidget(btn_export)
        history_btn_layout.addWidget(btn_clear_history)

        history_layout.addLayout(history_btn_layout)

        self.tab_widget.addTab(history_widget, "导入历史")

    # ... (继续在下一个文件中实现其他方法)

