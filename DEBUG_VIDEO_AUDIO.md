# 视频和音频导入问题调试指南

## 🐛 问题描述

用户测试后发现：
- ✅ 图片文件可以正常导入到达芬奇媒体池
- ❌ 视频文件无法导入到达芬奇媒体池
- ❌ 音频文件无法导入到达芬奇媒体池

## 🔍 已添加的调试日志

v1.6 代码已更新，添加了详细的调试日志：

### 本地文件夹创建日志
```
📁 检查本地文件夹: /path/to/folder
📁 创建本地文件夹: Clipboard_Videos
✅ 本地文件夹已存在: Clipboard_Videos
```

### 达芬奇导入详细日志
```
📤 准备导入 X 个 video 文件到达芬奇...
🔍 在达芬奇中查找文件夹: Clipboard_Videos
✅ 找到现有文件夹: Clipboard_Videos
📂 已设置当前文件夹为: Clipboard_Videos
⏳ 正在导入文件到达芬奇...
   媒体类型: video
   文件数量: 2
   目标文件夹: Clipboard_Videos
   [1] /Users/.../clip_xxx_video.mp4
   [2] /Users/.../clip_xxx_video2.mov
📊 达芬奇返回值类型: <class 'NoneType'>
📊 达芬奇返回值: None
⚠️ 达芬奇返回: ImportMedia 返回 None 或空列表
   可能原因:
   1. 文件格式不被达芬奇支持
   2. 文件编码不兼容
   3. 文件损坏或无法读取
   4. 达芬奇项目设置不支持该分辨率/帧率
```

## 🧪 测试步骤

### 1. 运行更新后的代码
```bash
cd /Users/wukaiyu/Documents/03\ Coding/CursorCoding/claude/DR_PixBridge
python3 PixBridge_v1.6.py
```

### 2. 测试视频导入
1. 打开达芬奇，确保有一个打开的项目
2. 在 PixBridge 中勾选 🎬 视频
3. 点击 "▶️ 开启实时监听"
4. 在 Finder 中复制一个 `.mp4` 视频文件
5. **复制完整的日志输出**

### 3. 检查日志中的关键信息

需要特别关注：
- 文件路径是否正确？
- 文件是否存在？（是否有"❌ 警告: X 个文件不存在!"）
- 达芬奇返回值类型是什么？（NoneType / list / 其他）
- 达芬奇返回值内容是什么？

## 🔧 可能的问题和解决方案

### 问题 1: 文件编码不兼容
**症状:** 达芬奇返回 None 或空列表

**解决方案:**
- 确保视频文件使用达芬奇支持的编码（H.264, ProRes, DNxHD 等）
- 可以用 VLC 或 MediaInfo 查看视频编码信息
- 尝试用 HandBrake 或 FFmpeg 转码为 H.264 编码的 MP4

### 问题 2: 项目设置不兼容
**症状:** 达芬奇返回 None

**解决方案:**
- 检查达芬奇项目设置（分辨率、帧率）
- 如果项目是 1920x1080 25fps，导入 4K 60fps 视频可能失败
- 尝试创建一个"自定义"项目，不限制分辨率和帧率

### 问题 3: 文件路径或权限问题
**症状:** 日志显示文件不存在

**解决方案:**
- 检查保存路径是否有特殊字符
- 检查文件夹权限
- 尝试更改保存路径到 ~/Desktop

### 问题 4: DaVinci Resolve API 限制
**症状:** 图片可以导入，视频/音频不行

**可能原因:**
- 达芬奇免费版可能对某些格式有限制
- 需要 Studio 版本才能导入某些高级格式

## 📝 收集调试信息

请运行测试并提供以下信息：

1. **完整的日志输出**（从点击"开启监听"到导入结束）

2. **视频文件信息**
   - 文件格式: `.mp4` / `.mov` / 其他
   - 文件大小:
   - 编码格式: （用 VLC 或 MediaInfo 查看）
   - 分辨率和帧率:

3. **达芬奇版本**
   - 免费版 / Studio 版
   - 版本号:

4. **达芬奇项目设置**
   - 分辨率:
   - 帧率:
   - 时间线格式:

5. **本地文件夹检查**
   - 打开 `~/Downloads/Clipboard_Assets/`
   - 确认是否有以下文件夹：
     - [ ] Clipboard_Images/
     - [ ] Clipboard_Videos/
     - [ ] Clipboard_Audios/
   - 确认视频文件是否成功复制到 `Clipboard_Videos/` 文件夹

6. **达芬奇媒体池检查**
   - 打开达芬奇媒体池
   - 确认是否有以下文件夹：
     - [ ] Clipboard_Images
     - [ ] Clipboard_Videos
     - [ ] Clipboard_Audios
   - 文件夹里是否有素材？

## 🚀 临时解决方案

如果自动导入失败，可以尝试手动导入：

1. 文件会保存到本地文件夹（`~/Downloads/Clipboard_Assets/Clipboard_Videos/`）
2. 在达芬奇中，右键媒体池 → "Import Media"
3. 手动选择保存的视频文件

## 📊 预期的正常日志

如果一切正常，应该看到：

```
[时间] 📦 检测到 1 个已选择类型的文件
[时间]   - video.mp4 (video, 15.30 MB)
[时间] 🚀 开始批量导入 1 个文件...
[时间] 📂 处理 1 个 video 文件...
[时间] 📁 检查本地文件夹: /Users/.../Clipboard_Videos
[时间] 📁 创建本地文件夹: Clipboard_Videos
[时间] 💾 已保存: clip_xxx_video.mp4 (15.30 MB)
[时间] 📤 准备导入 1 个 video 文件到达芬奇...
[时间] 🔍 在达芬奇中查找文件夹: Clipboard_Videos
[时间] 📁 已创建达芬奇媒体文件夹: Clipboard_Videos
[时间] 📂 已设置当前文件夹为: Clipboard_Videos
[时间] ⏳ 正在导入文件到达芬奇...
[时间]    媒体类型: video
[时间]    文件数量: 1
[时间]    目标文件夹: Clipboard_Videos
[时间]    [1] /Users/.../clip_xxx_video.mp4
[时间] 📊 达芬奇返回值类型: <class 'list'>
[时间] 📊 达芬奇返回值: [<MediaPoolItem object>]
[时间] 🎉 成功导入 1 个 video 素材到达芬奇
[时间] 🎉 批量导入完成！
```

关键点：
- 达芬奇返回值类型应该是 `<class 'list'>`
- 达芬奇返回值应该包含 MediaPoolItem 对象
- 如果是 `<class 'NoneType'>` 或 `[]`，说明导入失败

---

**下一步：请运行测试并提供完整的日志输出！**
