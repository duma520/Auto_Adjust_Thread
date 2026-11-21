import os
import sys
import time
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont, ImageGrab
import win32gui
import win32process
import psutil
import pygetwindow as gw
from PyQt5.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QLabel, QComboBox, QWidget, 
                             QMessageBox, QDialog, QListWidget, QDialogButtonBox,
                             QSlider, QCheckBox, QGroupBox, QColorDialog, QInputDialog,
                             QLineEdit, QProgressDialog, QDoubleSpinBox, QScrollArea,
                             QSizePolicy)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal, QEvent
from PyQt5.QtGui import QImage, QPixmap, QColor, QIcon
from mss import mss
import sqlite3

class ProjectInfo:
    """项目信息元数据"""
    VERSION = "2.9.0"  # 版本号更新
    BUILD_DATE = "2025-06-15"
    AUTHOR = "AI Assistant"
    LICENSE = "MIT"
    NAME = "智能场景色彩还原工具"
    DESCRIPTION = "用于捕获窗口画面并智能还原各种场景下真实色彩的工具"
    
    # 扩展色彩模式定义
    COLOR_MODES = {
        "自动": {
            "description": "自动分析图像并智能还原真实色彩",
            "params": {
                "auto_white_balance": True,
                "auto_contrast": True,
                "auto_saturation": True,
                "skin_tone_correction": True,
                "scene_detection": True
            },
            "recommended_for": ["未知场景", "混合光照环境"]
        },
        "标准": {
            "description": "不做特殊处理，保持原始色彩",
            "params": {
                "red_balance": 1.0,
                "green_balance": 1.0,
                "blue_balance": 1.0,
                "brightness": 0,
                "contrast": 0,
                "saturation": 0
            },
            "recommended_for": ["正常光照", "专业摄影"]
        },
        "夜场": {
            "description": "针对夜场蓝紫色灯光环境的色彩还原",
            "params": {
                "red_balance": 1.3,
                "green_balance": 0.9,
                "blue_balance": 0.6,
                "brightness": 15,
                "contrast": 20,
                "saturation": 15,
                "skin_tone_correction": True,
                "dominant_color_reduction": ["blue", "purple"],
                "target_skin_tone": [180, 140, 110]  # BGR格式的目标肤色
            },
            "recommended_for": ["夜店", "酒吧", "KTV"]
        },
        "KTV": {
            "description": "针对KTV多彩旋转灯光的色彩校正",
            "params": {
                "red_balance": 1.2,
                "green_balance": 0.8,
                "blue_balance": 0.7,
                "brightness": 10,
                "contrast": 25,
                "saturation": 20,
                "skin_tone_correction": True,
                "dynamic_lighting_adjustment": True
            },
            "recommended_for": ["KTV", "歌舞厅"]
        },
        "演唱会": {
            "description": "针对舞台强光和多色灯光的色彩还原",
            "params": {
                "red_balance": 1.1,
                "green_balance": 0.95,
                "blue_balance": 0.9,
                "brightness": 20,
                "contrast": 30,
                "saturation": 25,
                "spotlight_compensation": True,
                "high_contrast_optimization": True
            },
            "recommended_for": ["演唱会", "舞台表演"]
        },
        "办公室": {
            "description": "针对办公室荧光灯环境的自然色彩还原",
            "params": {
                "red_balance": 1.05,
                "green_balance": 0.95,
                "blue_balance": 1.1,
                "brightness": 10,
                "contrast": 15,
                "saturation": 5,
                "fluorescent_light_correction": True
            },
            "recommended_for": ["办公室", "会议室"]
        },
        "自然光": {
            "description": "模拟自然光照下的色彩表现",
            "params": {
                "red_balance": 1.1,
                "green_balance": 1.05,
                "blue_balance": 0.95,
                "brightness": 10,
                "contrast": 10,
                "saturation": 10,
                "natural_light_simulation": True
            },
            "recommended_for": ["户外", "窗户旁"]
        },
        "日光灯": {
            "description": "校正日光灯造成的偏绿色调",
            "params": {
                "red_balance": 1.15,
                "green_balance": 0.85,
                "blue_balance": 1.05,
                "brightness": 5,
                "contrast": 10,
                "saturation": 5,
                "green_tone_reduction": True
            },
            "recommended_for": ["超市", "医院", "学校"]
        },
        "白炽灯": {
            "description": "校正白炽灯造成的偏黄色调",
            "params": {
                "red_balance": 0.9,
                "green_balance": 1.05,
                "blue_balance": 1.2,
                "brightness": 5,
                "contrast": 5,
                "saturation": 5,
                "warm_tone_reduction": True
            },
            "recommended_for": ["家庭", "餐厅"]
        },
        "水下": {
            "description": "校正水下摄影的蓝绿色调",
            "params": {
                "red_balance": 1.5,
                "green_balance": 0.8,
                "blue_balance": 0.6,
                "brightness": 20,
                "contrast": 25,
                "saturation": 30,
                "underwater_correction": True
            },
            "recommended_for": ["水下摄影", "泳池"]
        },
        "霓虹灯": {
            "description": "减少霓虹灯造成的色彩污染",
            "params": {
                "red_balance": 0.8,
                "green_balance": 0.7,
                "blue_balance": 0.9,
                "brightness": -10,
                "contrast": 35,
                "saturation": 40,
                "neon_light_compensation": True
            },
            "recommended_for": ["霓虹灯街道", "夜市"]
        }
    }

    # 获取所有模式名称的列表
    @classmethod
    def get_mode_names(cls):
        return list(cls.COLOR_MODES.keys())

    # 获取模式的详细描述
    @classmethod
    def get_mode_description(cls, mode_name):
        mode = cls.COLOR_MODES.get(mode_name)
        return mode.get("description", "无描述") if mode else "无描述"

    # 获取推荐使用场景
    @classmethod
    def get_recommended_scenes(cls, mode_name):
        mode = cls.COLOR_MODES.get(mode_name)
        return mode.get("recommended_for", []) if mode else []

    # 获取模式参数
    @classmethod
    def get_mode_params(cls, mode_name):
        mode = cls.COLOR_MODES.get(mode_name)
        return mode.get("params", {}) if mode else {}



class CaptureThread(QThread):
    frame_captured = pyqtSignal(np.ndarray)
    error_occurred = pyqtSignal(str)
    
    def __init__(self, capture_method, hwnd=None):
        super().__init__()
        self.capture_method = capture_method
        self.hwnd = hwnd
        self.running = False
        self.mss_instance = mss() if capture_method == "MSS" else None
    
    def run(self):
        self.running = True
        while self.running:
            try:
                frame = self.capture_frame()
                if frame is not None:
                    self.frame_captured.emit(frame)
                time.sleep(0.05)  # 20 FPS
            except Exception as e:
                self.error_occurred.emit(str(e))
    
    def stop(self):
        self.running = False
        if self.mss_instance:
            self.mss_instance.close()
    
    def capture_frame(self):
        if self.capture_method == "MSS":
            return self.capture_with_mss()
        elif self.capture_method == "PIL截图":
            return self.capture_with_pil()
        return None
    
    def capture_with_mss(self):
        if not self.hwnd:
            return None
            
        try:
            rect = win32gui.GetWindowRect(self.hwnd)
            if rect[0] < 0 and rect[1] < 0 and rect[2] < 0 and rect[3] < 0:
                return None
                
            monitor = {
                "left": rect[0],
                "top": rect[1],
                "width": rect[2] - rect[0],
                "height": rect[3] - rect[1],
                "mon": 0
            }
            
            with mss() as sct:
                sct_img = sct.grab(monitor)
                img = np.array(sct_img)
                img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            return img
        except Exception as e:
            print(f"MSS捕获失败: {str(e)}")
            return None
    
    def capture_with_pil(self):
        if not self.hwnd:
            return None
            
        try:
            rect = win32gui.GetWindowRect(self.hwnd)
            if rect[0] < 0 and rect[1] < 0 and rect[2] < 0 and rect[3] < 0:
                return None
            
            img = ImageGrab.grab(bbox=rect)
            img = np.array(img)
            img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
            return img
        except Exception as e:
            print(f"PIL捕获失败: {str(e)}")
            return None

class ProcessSelectionDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("选择目标窗口")
        self.setFixedSize(400, 500)
        
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)
        
        self.process_list = QListWidget()
        self.layout.addWidget(self.process_list)
        
        self.refresh_button = QPushButton("刷新列表")
        self.refresh_button.clicked.connect(self.populate_process_list)
        self.layout.addWidget(self.refresh_button)
        
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.layout.addWidget(self.button_box)
        
        self.selected_pid = None
        self.selected_title = None
        self.selected_hwnd = None
        
        self.populate_process_list()
    
    def populate_process_list(self):
        self.process_list.clear()
        processes = {}
        for proc in psutil.process_iter(['pid', 'name']):
            processes[proc.info['pid']] = proc.info['name']
        
        windows = []
        for window in gw.getAllWindows():
            try:
                if window.title.strip() and getattr(window, 'visible', False):
                    try:
                        pid = window._hWnd
                        _, found_pid = win32process.GetWindowThreadProcessId(pid)
                        exe_name = processes.get(found_pid, "未知进程")
                        window_info = f"{window.title} (PID: {found_pid}, 进程: {exe_name})"
                        windows.append((window.title, found_pid, window_info, window._hWnd))
                    except:
                        continue
            except:
                continue
        
        windows.sort(key=lambda x: x[0].lower())
        
        for title, pid, info, hwnd in windows:
            self.process_list.addItem(info)
            self.process_list.item(self.process_list.count()-1).setData(Qt.UserRole, (pid, title, hwnd))
    
    def get_selected_process(self):
        selected_items = self.process_list.selectedItems()
        if selected_items:
            pid, title, hwnd = selected_items[0].data(Qt.UserRole)
            return pid, title, hwnd
        return None, None, None

class ColorRestorationApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.auto_scale_images = True  # 默认启用自动缩放
        self._auto_restore_colors = True  # 默认启用自动还原色彩
       
        # 初始化属性
        self.captured_image = None
        self.restored_image = None
        self.capture_thread = None
        self.selected_hwnd = None
        
        # 初始化数据库
        self.init_db()
        
        # 设置窗口属性
        self.setWindowTitle(f"{ProjectInfo.NAME} {ProjectInfo.VERSION}")
        self.setMinimumSize(800, 600)
        
        # 处理图标
        self.setup_icon()
        
        # 创建主界面
        self.main_widget = QWidget()
        self.setCentralWidget(self.main_widget)
        
        # 主布局
        self.main_layout = QHBoxLayout(self.main_widget)
        
        # 创建控制面板和图像显示区域
        self.create_control_panel()
        self.create_image_display()
        
        # 加载保存设置
        self.load_settings()

    
    def setup_icon(self):
        """处理程序图标"""
        icon_path = "icon.ico"
        if not os.path.exists(icon_path):
            try:
                img = Image.new('RGBA', (256, 256), (70, 130, 180, 255))
                draw = ImageDraw.Draw(img)
                try:
                    font = ImageFont.truetype("arial.ttf", 120)
                except:
                    font = ImageFont.load_default()
                draw.text((50, 50), "CR", font=font, fill=(255, 255, 255, 255))
                img.save(icon_path, format='ICO', sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
            except Exception as e:
                print(f"无法生成图标: {str(e)}")
        
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
    
    def init_db(self):
        """初始化数据库"""
        self.db_conn = sqlite3.connect('color_restore.db')
        self.db_cursor = self.db_conn.cursor()
        self.db_cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT UNIQUE,
            value TEXT
        )
        ''')
        self.db_cursor.execute('''
        CREATE TABLE IF NOT EXISTS presets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            red_balance REAL,
            green_balance REAL,
            blue_balance REAL,
            brightness REAL,
            contrast REAL,
            saturation REAL
        )
        ''')
        self.db_conn.commit()
    
    def create_control_panel(self):
        """创建左侧控制面板"""
        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        
        # 创建控制面板容器
        control_container = QWidget()
        control_layout = QVBoxLayout(control_container)
        
        # 控制面板内容
        control_panel = QGroupBox("控制面板")
        panel_layout = QVBoxLayout()
        
        # 窗口选择部分
        window_group = QGroupBox("窗口选择")
        window_layout = QVBoxLayout()
        
        self.window_combo = QComboBox()
        self.refresh_windows_btn = QPushButton("刷新窗口列表")
        self.refresh_windows_btn.clicked.connect(self.refresh_window_list)
        
        window_layout.addWidget(QLabel("选择目标窗口:"))
        window_layout.addWidget(self.window_combo)
        window_layout.addWidget(self.refresh_windows_btn)
        window_group.setLayout(window_layout)
        
        # 捕获方法选择
        self.capture_method_combo = QComboBox()
        self.capture_method_combo.addItems(["MSS", "PIL截图"])
        
        # 捕获按钮
        self.capture_btn = QPushButton("捕获窗口画面")
        self.capture_btn.clicked.connect(self.capture_window)

        # 色彩调整部分
        color_group = QGroupBox("色彩调整")
        color_layout = QVBoxLayout()

        # 色彩模式选择
        self.color_mode_combo = QComboBox()
        self.color_mode_combo.addItems(ProjectInfo.get_mode_names())
        self.color_mode_combo.setCurrentText("自动")
        self.color_mode_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.color_mode_combo.currentTextChanged.connect(self.apply_color_mode)
        
        color_layout.addWidget(QLabel("色彩模式:"))
        color_layout.addWidget(self.color_mode_combo)

        # 颜色平衡
        self.red_balance = QDoubleSpinBox()
        self.red_balance.setRange(0.1, 5.0)
        self.red_balance.setSingleStep(0.1)
        self.red_balance.setValue(1.0)
        self.red_balance.valueChanged.connect(self.update_restoration_param)
        
        self.green_balance = QDoubleSpinBox()
        self.green_balance.setRange(0.1, 5.0)
        self.green_balance.setSingleStep(0.1)
        self.green_balance.setValue(1.0)
        self.green_balance.valueChanged.connect(self.update_restoration_param)
        
        self.blue_balance = QDoubleSpinBox()
        self.blue_balance.setRange(0.1, 5.0)
        self.blue_balance.setSingleStep(0.1)
        self.blue_balance.setValue(1.0)
        self.blue_balance.valueChanged.connect(self.update_restoration_param)
        
        color_layout.addWidget(QLabel("红色平衡:"))
        color_layout.addWidget(self.red_balance)
        color_layout.addWidget(QLabel("绿色平衡:"))
        color_layout.addWidget(self.green_balance)
        color_layout.addWidget(QLabel("蓝色平衡:"))
        color_layout.addWidget(self.blue_balance)
        
        # 亮度对比度饱和度
        self.brightness = QDoubleSpinBox()
        self.brightness.setRange(-100, 100)
        self.brightness.setSingleStep(1)
        self.brightness.setValue(0)
        self.brightness.valueChanged.connect(self.update_restoration_param)
        
        self.contrast = QDoubleSpinBox()
        self.contrast.setRange(-100, 100)
        self.contrast.setSingleStep(1)
        self.contrast.setValue(0)
        self.contrast.valueChanged.connect(self.update_restoration_param)
        
        self.saturation = QDoubleSpinBox()
        self.saturation.setRange(-100, 100)
        self.saturation.setSingleStep(1)
        self.saturation.setValue(0)
        self.saturation.valueChanged.connect(self.update_restoration_param)
        
        color_layout.addWidget(QLabel("亮度:"))
        color_layout.addWidget(self.brightness)
        color_layout.addWidget(QLabel("对比度:"))
        color_layout.addWidget(self.contrast)
        color_layout.addWidget(QLabel("饱和度:"))
        color_layout.addWidget(self.saturation)
        
        color_group.setLayout(color_layout)
        
        # 预设管理
        preset_group = QGroupBox("预设管理")
        preset_layout = QVBoxLayout()
        
        self.preset_combo = QComboBox()
        self.load_preset_btn = QPushButton("加载预设")
        self.save_preset_btn = QPushButton("保存预设")
        self.delete_preset_btn = QPushButton("删除预设")
        
        self.load_preset_btn.clicked.connect(self.load_preset)
        self.save_preset_btn.clicked.connect(self.save_preset)
        self.delete_preset_btn.clicked.connect(self.delete_preset)
        
        preset_layout.addWidget(QLabel("预设:"))
        preset_layout.addWidget(self.preset_combo)
        preset_layout.addWidget(self.load_preset_btn)
        preset_layout.addWidget(self.save_preset_btn)
        preset_layout.addWidget(self.delete_preset_btn)
        preset_group.setLayout(preset_layout)
        
        # 自动功能控制
        auto_group = QGroupBox("自动功能")
        auto_layout = QVBoxLayout()
        
        # 自动缩放复选框
        self.auto_scale_check = QCheckBox("自动缩放图像")
        self.auto_scale_check.setChecked(True)
        self.auto_scale_check.stateChanged.connect(self.toggle_auto_scale)
        auto_layout.addWidget(self.auto_scale_check)

        # 自动还原色彩复选框
        self.auto_restore_check = QCheckBox("自动还原色彩")
        self.auto_restore_check.setChecked(True)
        self.auto_restore_check.stateChanged.connect(self.toggle_auto_restore)
        auto_layout.addWidget(self.auto_restore_check)
        
        auto_group.setLayout(auto_layout)

        # 操作按钮
        self.restore_btn = QPushButton("还原色彩")
        self.restore_btn.setEnabled(False)
        self.restore_btn.clicked.connect(self.restore_colors)
        self.save_btn = QPushButton("保存结果")
        self.save_btn.setEnabled(False)
        self.save_btn.clicked.connect(self.save_result)
        
        # 将控制面板添加到容器布局中
        panel_layout.addWidget(window_group)
        panel_layout.addWidget(QLabel("捕获方法:"))
        panel_layout.addWidget(self.capture_method_combo)
        panel_layout.addWidget(self.capture_btn)
        panel_layout.addWidget(color_group)
        panel_layout.addWidget(preset_group)
        panel_layout.addWidget(auto_group)  # 添加自动功能组
        panel_layout.addWidget(self.restore_btn)
        panel_layout.addWidget(self.save_btn)
        panel_layout.addStretch()
        
        control_panel.setLayout(panel_layout)
        
        # 将控制面板添加到容器中
        control_layout.addWidget(control_panel)
        control_layout.addStretch()
        
        # 设置滚动区域的widget
        scroll_area.setWidget(control_container)
        
        # 将滚动区域添加到主布局
        self.main_layout.addWidget(scroll_area, stretch=1)
        
        # 刷新窗口列表和预设列表
        self.refresh_window_list()
        self.refresh_preset_list()


    def apply_color_mode(self, mode_name):
        """应用选定的色彩模式"""
        mode_info = ProjectInfo.COLOR_MODES.get(mode_name, ProjectInfo.COLOR_MODES["自动"])
        mode_params = mode_info.get("params", {})
        
        # 暂时断开信号连接，避免多次触发
        self.red_balance.valueChanged.disconnect()
        self.green_balance.valueChanged.disconnect()
        self.blue_balance.valueChanged.disconnect()
        self.brightness.valueChanged.disconnect()
        self.contrast.valueChanged.disconnect()
        self.saturation.valueChanged.disconnect()
        
        # 应用模式参数
        if "red_balance" in mode_params:
            self.red_balance.setValue(mode_params["red_balance"])
        if "green_balance" in mode_params:
            self.green_balance.setValue(mode_params["green_balance"])
        if "blue_balance" in mode_params:
            self.blue_balance.setValue(mode_params["blue_balance"])
        if "brightness" in mode_params:
            self.brightness.setValue(mode_params["brightness"])
        if "contrast" in mode_params:
            self.contrast.setValue(mode_params["contrast"])
        if "saturation" in mode_params:
            self.saturation.setValue(mode_params["saturation"])
        
        # 重新连接信号
        self.red_balance.valueChanged.connect(self.update_restoration_param)
        self.green_balance.valueChanged.connect(self.update_restoration_param)
        self.blue_balance.valueChanged.connect(self.update_restoration_param)
        self.brightness.valueChanged.connect(self.update_restoration_param)
        self.contrast.valueChanged.connect(self.update_restoration_param)
        self.saturation.valueChanged.connect(self.update_restoration_param)
        
        # 立即应用更改
        if self.captured_image is not None:
            self.restore_colors()



    def create_image_display(self):
        """创建右侧图像显示区域"""
        image_panel = QGroupBox("图像预览")
        image_layout = QVBoxLayout()
        
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        
        self.image_container = QWidget()
        self.image_container_layout = QVBoxLayout(self.image_container)
        self.image_container_layout.setContentsMargins(0, 0, 0, 0)  # 移除边距
        self.image_container_layout.setSpacing(0)  # 移除间距
        
        # 创建两个等高的容器
        self.original_container = QWidget()
        self.original_container_layout = QVBoxLayout(self.original_container)
        self.original_container_layout.setContentsMargins(0, 0, 0, 0)
        
        self.restored_container = QWidget()
        self.restored_container_layout = QVBoxLayout(self.restored_container)
        self.restored_container_layout.setContentsMargins(0, 0, 0, 0)
        
        # 设置标签属性
        self.original_label = QLabel("原始图像")
        self.original_label.setAlignment(Qt.AlignCenter)
        self.original_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.original_label.setMinimumSize(100, 100)
        
        self.restored_label = QLabel("还原后图像")
        self.restored_label.setAlignment(Qt.AlignCenter)
        self.restored_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.restored_label.setMinimumSize(100, 100)
        
        # 将标签添加到各自的容器
        self.original_container_layout.addWidget(self.original_label)
        self.restored_container_layout.addWidget(self.restored_label)
        
        # 将两个容器添加到主布局，并设置拉伸因子
        self.image_container_layout.addWidget(self.original_container, 1)  # 1:1的比例
        self.image_container_layout.addWidget(self.restored_container, 1)
        
        scroll_area.setWidget(self.image_container)
        image_layout.addWidget(scroll_area)
        
        image_panel.setLayout(image_layout)
        self.main_layout.addWidget(image_panel, stretch=2)

        # 添加窗口大小变化事件
        self.image_container.installEventFilter(self)



    def refresh_window_list(self):
        """刷新窗口列表"""
        self.window_combo.clear()
        
        def callback(hwnd, extra):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if title:
                    self.window_combo.addItem(title, hwnd)
        
        win32gui.EnumWindows(callback, None)
    
    def refresh_preset_list(self):
        """刷新预设列表"""
        self.preset_combo.clear()
        self.db_cursor.execute("SELECT name FROM presets ORDER BY name")
        presets = self.db_cursor.fetchall()
        for preset in presets:
            self.preset_combo.addItem(preset[0])
    
    def capture_window(self):
        """捕获选定窗口的图像"""
        if self.window_combo.count() == 0:
            QMessageBox.warning(self, "错误", "没有可用的窗口")
            return
        
        hwnd = self.window_combo.currentData()
        if not hwnd:
            QMessageBox.warning(self, "错误", "无效的窗口句柄")
            return
        
        # 停止现有的捕获线程
        if self.capture_thread:
            self.capture_thread.stop()
            self.capture_thread.quit()
            self.capture_thread.wait()
        
        # 创建新的捕获线程
        capture_method = self.capture_method_combo.currentText()
        self.capture_thread = CaptureThread(capture_method, hwnd)
        self.capture_thread.frame_captured.connect(self.update_captured_image)
        self.capture_thread.error_occurred.connect(self.handle_capture_error)
        self.capture_thread.start()
        
        self.capture_btn.setEnabled(False)
        self.restore_btn.setEnabled(True)
    
    def update_captured_image(self, frame):
        """更新捕获的图像"""
        self.captured_image = frame
        self.display_image(self.captured_image, self.original_label)
        
        # 如果启用了自动还原色彩，立即处理图像
        if self._auto_restore_colors:
            self.restore_colors()
        
        # 保存当前窗口设置
        hwnd = self.window_combo.currentData()
        self.save_setting('last_window', str(hwnd))

    
    def handle_capture_error(self, error_msg):
        """处理捕获错误"""
        QMessageBox.critical(self, "捕获错误", f"捕获过程中发生错误:\n{error_msg}")
        self.capture_btn.setEnabled(True)
        self.restore_btn.setEnabled(False)
    
    def display_image(self, image, label):
        """在QLabel中显示图像，自动缩放以适应标签大小"""
        if image is None:
            return
        
        height, width, channel = image.shape
        bytes_per_line = 3 * width
        
        if image.dtype != np.uint8:
            image = image.astype(np.uint8)
        
        q_img = QImage(image.data, width, height, bytes_per_line, QImage.Format_RGB888).rgbSwapped()
        
        # 获取标签的可用大小（减去边距）
        label_size = label.size()
        available_width = label_size.width()
        available_height = label_size.height()
        
        # 计算保持宽高比的缩放尺寸
        if width > 0 and height > 0:
            width_ratio = available_width / width
            height_ratio = available_height / height
            scale_ratio = min(width_ratio, height_ratio)
            
            scaled_width = int(width * scale_ratio)
            scaled_height = int(height * scale_ratio)
            
            # 确保缩放后的尺寸不小于最小限制
            scaled_width = max(scaled_width, 10)
            scaled_height = max(scaled_height, 10)
        else:
            scaled_width = available_width
            scaled_height = available_height
        
        # 创建并设置缩放后的图像
        scaled_pixmap = QPixmap.fromImage(q_img).scaled(
            scaled_width, scaled_height, 
            Qt.KeepAspectRatio, Qt.SmoothTransformation)
        label.setPixmap(scaled_pixmap)


    
    def restore_colors(self):
        """应用色彩还原"""
        if self.captured_image is None:
            QMessageBox.warning(self, "错误", "没有可处理的图像")
            return
        
        try:
            # 获取当前色彩模式
            mode_name = self.color_mode_combo.currentText()
            mode_info = ProjectInfo.COLOR_MODES.get(mode_name, ProjectInfo.COLOR_MODES["自动"])
            mode_params = mode_info["params"]
            
            # 复制原始图像
            img = self.captured_image.copy()
            
            # 自动模式处理
            if mode_name == "自动":
                img = self.auto_restore_colors(img)
            else:
                # 手动模式处理
                img = img.astype(np.float32) / 255.0
                
                # 应用颜色平衡
                img[:, :, 2] *= self.red_balance.value()    # 红色通道
                img[:, :, 1] *= self.green_balance.value()  # 绿色通道
                img[:, :, 0] *= self.blue_balance.value()   # 蓝色通道
                
                # 裁剪到0-1范围
                img = np.clip(img, 0, 1)
                
                # 转换为HSV色彩空间
                hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
                
                # 调整亮度 (V通道)
                hsv[:, :, 2] = np.clip(hsv[:, :, 2] * (1 + self.brightness.value()/100), 0, 1)
                
                # 调整饱和度 (S通道)
                hsv[:, :, 1] = np.clip(hsv[:, :, 1] * (1 + self.saturation.value()/100), 0, 1)
                
                # 转换回BGR
                img = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
                
                # 调整对比度
                if self.contrast.value() != 0:
                    alpha = 1 + self.contrast.value()/100
                    img = (img - 0.5) * alpha + 0.5
                    img = np.clip(img, 0, 1)
                
                # 转换为8位图像
                img = (img * 255).astype(np.uint8)
            
            # 特定模式处理 - 如夜场模式的肤色修正
            if mode_params.get("skin_tone_correction", False):
                img = self.detect_and_correct_skin_tone(img)
            
            # 保存处理后的图像
            self.restored_image = img
            
            # 显示结果
            self.display_image(self.restored_image, self.restored_label)
            self.save_btn.setEnabled(True)
            
        except Exception as e:
            print(f"色彩还原时出错: {str(e)}")
            QMessageBox.critical(self, "错误", f"色彩还原时出错: {str(e)}")


    
    def save_result(self):
        """保存处理后的图像"""
        if self.restored_image is None:
            QMessageBox.warning(self, "错误", "没有可保存的图像")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存图像", "", "PNG图像 (*.png);;JPEG图像 (*.jpg *.jpeg);;所有文件 (*)")
        
        if file_path:
            try:
                if file_path.lower().endswith('.png'):
                    cv2.imwrite(file_path, self.restored_image, [cv2.IMWRITE_PNG_COMPRESSION, 9])
                elif file_path.lower().endswith(('.jpg', '.jpeg')):
                    cv2.imwrite(file_path, self.restored_image, [cv2.IMWRITE_JPEG_QUALITY, 95])
                else:
                    if not file_path.lower().endswith('.png'):
                        file_path += '.png'
                    cv2.imwrite(file_path, self.restored_image, [cv2.IMWRITE_PNG_COMPRESSION, 9])
                
                QMessageBox.information(self, "成功", "图像已保存")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"保存图像时出错: {str(e)}")
    
    def load_preset(self):
        """加载预设"""
        preset_name = self.preset_combo.currentText()
        if not preset_name:
            QMessageBox.warning(self, "错误", "请选择要加载的预设")
            return
        
        try:
            self.db_cursor.execute(
                "SELECT red_balance, green_balance, blue_balance, brightness, contrast, saturation "
                "FROM presets WHERE name = ?", (preset_name,))
            preset = self.db_cursor.fetchone()
            
            if preset:
                self.red_balance.setValue(preset[0])
                self.green_balance.setValue(preset[1])
                self.blue_balance.setValue(preset[2])
                self.brightness.setValue(preset[3])
                self.contrast.setValue(preset[4])
                self.saturation.setValue(preset[5])
                
                QMessageBox.information(self, "成功", f"预设 '{preset_name}' 已加载")
            else:
                QMessageBox.warning(self, "错误", f"找不到预设 '{preset_name}'")
                
        except Exception as e:
            QMessageBox.critical(self, "错误", f"加载预设时出错: {str(e)}")

    def update_color_mode(self, mode_name):
        """根据选择的色彩模式自动调整参数"""
        mode = ProjectInfo.COLOR_MODES.get(mode_name, "auto")
        
        if mode == "auto":
            # 自动模式，不改变参数
            return
        elif mode == "standard":
            # 标准模式 - 重置所有参数
            self.red_balance.setValue(1.0)
            self.green_balance.setValue(1.0)
            self.blue_balance.setValue(1.0)
            self.brightness.setValue(0)
            self.contrast.setValue(0)
            self.saturation.setValue(0)
        elif mode == "night_club":
            # 夜场模式 - 减少红色，增强蓝色
            self.red_balance.setValue(0.8)
            self.green_balance.setValue(0.9)
            self.blue_balance.setValue(1.2)
            self.brightness.setValue(-10)
            self.contrast.setValue(15)
            self.saturation.setValue(20)
        elif mode == "ktv":
            # KTV模式 - 增强红色和蓝色
            self.red_balance.setValue(1.3)
            self.green_balance.setValue(0.9)
            self.blue_balance.setValue(1.2)
            self.brightness.setValue(5)
            self.contrast.setValue(10)
            self.saturation.setValue(15)
        elif mode == "bar":
            # 酒吧模式 - 暖色调
            self.red_balance.setValue(1.2)
            self.green_balance.setValue(0.9)
            self.blue_balance.setValue(0.8)
            self.brightness.setValue(-5)
            self.contrast.setValue(5)
            self.saturation.setValue(10)
        elif mode == "concert":
            # 演唱会模式 - 高对比度
            self.red_balance.setValue(1.1)
            self.green_balance.setValue(1.1)
            self.blue_balance.setValue(1.1)
            self.brightness.setValue(5)
            self.contrast.setValue(30)
            self.saturation.setValue(25)
        elif mode == "office":
            # 办公室模式 - 中性色调
            self.red_balance.setValue(1.0)
            self.green_balance.setValue(1.0)
            self.blue_balance.setValue(1.0)
            self.brightness.setValue(10)
            self.contrast.setValue(5)
            self.saturation.setValue(5)
        elif mode == "natural_light":
            # 自然光模式 - 增强绿色
            self.red_balance.setValue(0.9)
            self.green_balance.setValue(1.1)
            self.blue_balance.setValue(0.9)
            self.brightness.setValue(5)
            self.contrast.setValue(5)
            self.saturation.setValue(10)
        elif mode == "fluorescent":
            # 日光灯模式 - 减少绿色
            self.red_balance.setValue(1.0)
            self.green_balance.setValue(0.8)
            self.blue_balance.setValue(1.1)
            self.brightness.setValue(5)
            self.contrast.setValue(5)
            self.saturation.setValue(5)
        elif mode == "incandescent":
            # 白炽灯模式 - 暖色调
            self.red_balance.setValue(1.2)
            self.green_balance.setValue(0.9)
            self.blue_balance.setValue(0.7)
            self.brightness.setValue(5)
            self.contrast.setValue(5)
            self.saturation.setValue(5)
        
        # 应用新的参数
        self.restore_colors()

    def auto_restore_colors(self, img):
        """自动色彩还原算法"""
        # 转换为浮点型以便处理
        img = img.astype(np.float32) / 255.0
        
        # 1. 自动白平衡 (灰度世界算法)
        avg_b = np.mean(img[:, :, 0])
        avg_g = np.mean(img[:, :, 1])
        avg_r = np.mean(img[:, :, 2])
        
        avg_gray = (avg_b + avg_g + avg_r) / 3.0
        
        # 计算各通道增益
        b_gain = avg_gray / (avg_b + 1e-6)
        g_gain = avg_gray / (avg_g + 1e-6)
        r_gain = avg_gray / (avg_r + 1e-6)
        
        # 应用自动白平衡
        img[:, :, 0] = np.clip(img[:, :, 0] * b_gain, 0, 1)
        img[:, :, 1] = np.clip(img[:, :, 1] * g_gain, 0, 1)
        img[:, :, 2] = np.clip(img[:, :, 2] * r_gain, 0, 1)
        
        # 2. 自动对比度增强 (直方图均衡化)
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        hsv[:, :, 2] = cv2.equalizeHist((hsv[:, :, 2] * 255).astype(np.uint8)) / 255.0
        img = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
        
        # 3. 自动饱和度调整
        hsv[:, :, 1] = np.clip(hsv[:, :, 1] * 1.2, 0, 1)
        img = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
        
        # 4. 肤色检测与修正
        img = (img * 255).astype(np.uint8)
        img = self.detect_and_correct_skin_tone(img)
        
        return img



    def save_preset(self):
        """保存当前设置为预设"""
        preset_name, ok = QInputDialog.getText(
            self, "保存预设", "输入预设名称:", QLineEdit.Normal)
        
        if ok and preset_name:
            try:
                self.db_cursor.execute(
                    "SELECT COUNT(*) FROM presets WHERE name = ?", (preset_name,))
                count = self.db_cursor.fetchone()[0]
                
                if count > 0:
                    reply = QMessageBox.question(
                        self, "确认", f"预设 '{preset_name}' 已存在，是否覆盖?",
                        QMessageBox.Yes | QMessageBox.No)
                    
                    if reply == QMessageBox.No:
                        return
                    
                    self.db_cursor.execute(
                        "UPDATE presets SET red_balance = ?, green_balance = ?, blue_balance = ?, "
                        "brightness = ?, contrast = ?, saturation = ? WHERE name = ?",
                        (self.red_balance.value(), self.green_balance.value(), self.blue_balance.value(),
                         self.brightness.value(), self.contrast.value(), self.saturation.value(),
                         preset_name))
                else:
                    self.db_cursor.execute(
                        "INSERT INTO presets (name, red_balance, green_balance, blue_balance, "
                        "brightness, contrast, saturation) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (preset_name, self.red_balance.value(), self.green_balance.value(),
                         self.blue_balance.value(), self.brightness.value(), self.contrast.value(),
                         self.saturation.value()))
                
                self.db_conn.commit()
                self.refresh_preset_list()
                
                QMessageBox.information(self, "成功", f"预设 '{preset_name}' 已保存")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"保存预设时出错: {str(e)}")
    
    def delete_preset(self):
        """删除预设"""
        preset_name = self.preset_combo.currentText()
        if not preset_name:
            QMessageBox.warning(self, "错误", "请选择要删除的预设")
            return
        
        reply = QMessageBox.question(
            self, "确认", f"确定要删除预设 '{preset_name}' 吗?",
            QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            try:
                self.db_cursor.execute(
                    "DELETE FROM presets WHERE name = ?", (preset_name,))
                self.db_conn.commit()
                self.refresh_preset_list()
                
                QMessageBox.information(self, "成功", f"预设 '{preset_name}' 已删除")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"删除预设时出错: {str(e)}")
    
    def save_setting(self, key, value):
        """保存设置到数据库"""
        try:
            self.db_cursor.execute(
                "SELECT COUNT(*) FROM settings WHERE key = ?", (key,))
            count = self.db_cursor.fetchone()[0]
            
            if count > 0:
                self.db_cursor.execute(
                    "UPDATE settings SET value = ? WHERE key = ?",
                    (value, key))
            else:
                self.db_cursor.execute(
                    "INSERT INTO settings (key, value) VALUES (?, ?)",
                    (key, value))
            
            self.db_conn.commit()
        except Exception as e:
            print(f"保存设置时出错: {str(e)}")
    
    def load_setting(self, key, default=None):
        """从数据库加载设置"""
        try:
            self.db_cursor.execute(
                "SELECT value FROM settings WHERE key = ?", (key,))
            result = self.db_cursor.fetchone()
            
            if result:
                return result[0]
            return default
        except Exception as e:
            print(f"加载设置时出错: {str(e)}")
            return default
    
    def load_settings(self):
        """加载保存的设置"""
        last_window = self.load_setting('last_window')
        if last_window:
            for i in range(self.window_combo.count()):
                if str(self.window_combo.itemData(i)) == last_window:
                    self.window_combo.setCurrentIndex(i)
                    break
        
        red_balance = float(self.load_setting('red_balance', '1.0'))
        green_balance = float(self.load_setting('green_balance', '1.0'))
        blue_balance = float(self.load_setting('blue_balance', '1.0'))
        brightness = float(self.load_setting('brightness', '0'))
        contrast = float(self.load_setting('contrast', '0'))
        saturation = float(self.load_setting('saturation', '0'))
        auto_restore = bool(int(self.load_setting('auto_restore', '1')))
        
        self.red_balance.setValue(red_balance)
        self.green_balance.setValue(green_balance)
        self.blue_balance.setValue(blue_balance)
        self.brightness.setValue(brightness)
        self.contrast.setValue(contrast)
        self.saturation.setValue(saturation)
        self.auto_restore_check.setChecked(auto_restore)
        self._auto_restore_colors = auto_restore


    def detect_and_correct_skin_tone(self, img):
        """检测并修正肤色"""
        # 转换到YCrCb色彩空间，更适合肤色检测
        ycrcb = cv2.cvtColor(img, cv2.COLOR_BGR2YCrCb)
        
        # 定义肤色范围 (可以根据需要调整)
        lower_skin = np.array([0, 133, 77], dtype=np.uint8)
        upper_skin = np.array([255, 173, 127], dtype=np.uint8)
        
        # 创建肤色掩膜
        skin_mask = cv2.inRange(ycrcb, lower_skin, upper_skin)
        
        # 使用形态学操作改善掩膜
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        skin_mask = cv2.morphologyEx(skin_mask, cv2.MORPH_CLOSE, kernel, iterations=2)
        skin_mask = cv2.morphologyEx(skin_mask, cv2.MORPH_OPEN, kernel, iterations=2)
        
        # 计算肤色区域的平均颜色
        skin_mean = cv2.mean(img, mask=skin_mask)
        
        # 目标肤色 (中性亚洲肤色)
        target_skin = (180, 140, 110)  # BGR
        
        # 计算颜色差异并修正
        if skin_mask.sum() > 0:  # 如果有检测到肤色区域
            b_diff = target_skin[0] - skin_mean[0]
            g_diff = target_skin[1] - skin_mean[1]
            r_diff = target_skin[2] - skin_mean[2]
            
            # 只修正肤色区域
            img[skin_mask > 0, 0] = np.clip(img[skin_mask > 0, 0] + b_diff * 0.7, 0, 255)
            img[skin_mask > 0, 1] = np.clip(img[skin_mask > 0, 1] + g_diff * 0.7, 0, 255)
            img[skin_mask > 0, 2] = np.clip(img[skin_mask > 0, 2] + r_diff * 0.7, 0, 255)
        
        return img

    def toggle_auto_scale(self, enabled):
        """切换自动缩放功能"""
        self.auto_scale_images = enabled
        if enabled:
            # 如果启用自动缩放，立即刷新显示
            if self.captured_image is not None:
                self.display_image(self.captured_image, self.original_label)
            if self.restored_image is not None:
                self.display_image(self.restored_image, self.restored_label)



    def closeEvent(self, event):
        """窗口关闭事件"""
        if self.capture_thread:
            self.capture_thread.stop()
            self.capture_thread.quit()
            self.capture_thread.wait()
        
        # 修正后的代码 - 移除多余括号
        self.save_setting('red_balance', str(self.red_balance.value()))
        self.save_setting('green_balance', str(self.green_balance.value()))
        self.save_setting('blue_balance', str(self.blue_balance.value()))
        self.save_setting('brightness', str(self.brightness.value()))
        self.save_setting('contrast', str(self.contrast.value()))
        self.save_setting('saturation', str(self.saturation.value()))
        self.save_setting('auto_restore', str(int(self._auto_restore_colors)))
        
        self.db_cursor.close()
        self.db_conn.close()
        
        event.accept()



    def eventFilter(self, obj, event):
        """处理图像容器的大小变化事件"""
        if obj == self.image_container and event.type() == QEvent.Resize:
            if self.auto_scale_images:
                # 当容器大小变化时，重新显示图像
                if self.captured_image is not None:
                    self.display_image(self.captured_image, self.original_label)
                if self.restored_image is not None:
                    self.display_image(self.restored_image, self.restored_label)
        return super().eventFilter(obj, event)


    def update_restoration_param(self):
        """更新色彩恢复参数"""
        if self._auto_restore_colors and self.captured_image is not None:
            self.restore_colors()



    def toggle_auto_restore(self, enabled):
        """切换自动还原色彩功能"""
        self._auto_restore_colors = enabled  # 使用带下划线前缀的属性名
        if enabled and self.captured_image is not None:
            # 如果启用自动还原，立即应用当前设置
            self.restore_colors()


if __name__ == "__main__":
    # 必须在创建QApplication前设置高DPI缩放
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)

    app = QApplication(sys.argv)
    
    window = ColorRestorationApp()
    window.show()
    sys.exit(app.exec_())
    