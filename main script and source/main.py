from __future__ import annotations

import gzip
import hashlib
import json
import math
import os
import random
import shutil
import struct
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, BinaryIO, Dict, List, Optional, Tuple
from uuid import UUID

import psutil
import PyQt5
from PyQt5.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    QRect,
    QRectF,
    QSize,
    Qt,
    QThread,
    QTimer,
    pyqtSignal,
)
from PyQt5.QtGui import (
    QBrush,
    QColor,
    QDesktopServices,
    QFont,
    QIcon,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFrame,
    QGraphicsOpacityEffect,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSpacerItem,
    QStackedWidget,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from PyQt5.QtCore import QUrl

from minecraft_launcher_lib.command import get_minecraft_command
from minecraft_launcher_lib.install import install_minecraft_version
from minecraft_launcher_lib.utils import get_installed_versions, get_minecraft_directory, get_version_list
from random_username.generate import generate_username



os.environ["QT_PLUGIN_PATH"] = os.path.join(
    os.path.dirname(PyQt5.__file__), "Qt5", "plugins"
)

APP_NAME = "FRESKMID Launcher"
APP_VERSION = "4.1.1"
ACCOUNTS_FILE = "accounts.json"
SETTINGS_FILE = "launcher_settings.json"

VVITTOX_SERVER_NAME = "VVITTOX LAND"
VVITTOX_SERVER_VERSION = "1.12.2"
VVITTOX_SERVER_HOST = "188.127.229.111"
VVITTOX_SERVER_PORT = "30346"
VVITTOX_SERVER_ADDRESS = f"{VVITTOX_SERVER_HOST}:{VVITTOX_SERVER_PORT}"
VVITTOX_BANNER_FILE = "VL BG.jpg"

BUNDLE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
DATA_DIR = (
    Path(sys.executable).resolve().parent
    if getattr(sys, "frozen", False)
    else Path(__file__).resolve().parent
)
ASSETS_DIR = DATA_DIR / "assets"
if not ASSETS_DIR.exists():
    ASSETS_DIR = BUNDLE_DIR / "assets"

_default_minecraft_dir = Path(get_minecraft_directory())
minecraft_directory = str(_default_minecraft_dir.with_name("FRESKMID"))


THEMES = {
    "Классическая": {
        "primary": "#d6b928",
        "secondary": "#9f8619",
        "dark": "#201b0d",
        "background": "#15120c",
        "panel": "#201d17",
        "panel_alt": "#2a261e",
        "text": "#fff8dc",
        "muted": "#b8ad88",
        "success": "#78c850",
    },
    "Аква": {
        "primary": "#4da3ff",
        "secondary": "#2874bd",
        "dark": "#0c2035",
        "background": "#08131f",
        "panel": "#10283f",
        "panel_alt": "#173650",
        "text": "#eef8ff",
        "muted": "#9bb8cf",
        "success": "#55d6be",
    },
    "Незер": {
        "primary": "#ff6a55",
        "secondary": "#b9382c",
        "dark": "#35100d",
        "background": "#1c0908",
        "panel": "#32110e",
        "panel_alt": "#451713",
        "text": "#fff0ec",
        "muted": "#d0a39b",
        "success": "#f5b942",
    },
    "Энд": {
        "primary": "#b875ff",
        "secondary": "#7140a7",
        "dark": "#21102f",
        "background": "#100817",
        "panel": "#261336",
        "panel_alt": "#342048",
        "text": "#f8edff",
        "muted": "#bda5ca",
        "success": "#86e3ce",
    },
}


def asset_path(filename: str) -> str:
    return str(ASSETS_DIR / filename)


def get_max_ram() -> int:
    total_gb = max(2, int(psutil.virtual_memory().total / (1024**3)))
    return max(2, total_gb - 2)


def offline_uuid(username: str) -> str:
    """Создаёт стабильный UUID, совместимый с форматом OfflinePlayer."""
    digest = bytearray(hashlib.md5(f"OfflinePlayer:{username}".encode("utf-8")).digest())
    digest[6] = (digest[6] & 0x0F) | 0x30
    digest[8] = (digest[8] & 0x3F) | 0x80
    return str(UUID(bytes=bytes(digest)))


def hex_to_rgba(hex_color: str, alpha: int) -> str:
    color = QColor(hex_color)
    return f"rgba({color.red()}, {color.green()}, {color.blue()}, {alpha})"



NBTValue = Tuple[int, Any]


class NBTError(Exception):
    pass


def _read_exact(stream: BinaryIO, size: int) -> bytes:
    data = stream.read(size)
    if len(data) != size:
        raise NBTError("Неожиданный конец NBT-файла")
    return data


def _read_string(stream: BinaryIO) -> str:
    length = struct.unpack(">H", _read_exact(stream, 2))[0]
    return _read_exact(stream, length).decode("utf-8")


def _read_payload(stream: BinaryIO, tag_type: int) -> Any:
    if tag_type == 1:
        return struct.unpack(">b", _read_exact(stream, 1))[0]
    if tag_type == 2:
        return struct.unpack(">h", _read_exact(stream, 2))[0]
    if tag_type == 3:
        return struct.unpack(">i", _read_exact(stream, 4))[0]
    if tag_type == 4:
        return struct.unpack(">q", _read_exact(stream, 8))[0]
    if tag_type == 5:
        return struct.unpack(">f", _read_exact(stream, 4))[0]
    if tag_type == 6:
        return struct.unpack(">d", _read_exact(stream, 8))[0]
    if tag_type == 7:
        length = struct.unpack(">i", _read_exact(stream, 4))[0]
        if length < 0:
            raise NBTError("Некорректная длина TAG_Byte_Array")
        return _read_exact(stream, length)
    if tag_type == 8:
        return _read_string(stream)
    if tag_type == 9:
        element_type = struct.unpack(">B", _read_exact(stream, 1))[0]
        length = struct.unpack(">i", _read_exact(stream, 4))[0]
        if length < 0:
            raise NBTError("Некорректная длина TAG_List")
        return element_type, [_read_payload(stream, element_type) for _ in range(length)]
    if tag_type == 10:
        result: Dict[str, NBTValue] = {}
        while True:
            child_type = struct.unpack(">B", _read_exact(stream, 1))[0]
            if child_type == 0:
                break
            name = _read_string(stream)
            result[name] = (child_type, _read_payload(stream, child_type))
        return result
    if tag_type == 11:
        length = struct.unpack(">i", _read_exact(stream, 4))[0]
        if length < 0:
            raise NBTError("Некорректная длина TAG_Int_Array")
        return [struct.unpack(">i", _read_exact(stream, 4))[0] for _ in range(length)]
    if tag_type == 12:
        length = struct.unpack(">i", _read_exact(stream, 4))[0]
        if length < 0:
            raise NBTError("Некорректная длина TAG_Long_Array")
        return [struct.unpack(">q", _read_exact(stream, 8))[0] for _ in range(length)]
    raise NBTError(f"Неизвестный тип NBT: {tag_type}")


def _write_string(stream: BinaryIO, value: str) -> None:
    encoded = value.encode("utf-8")
    if len(encoded) > 65535:
        raise NBTError("Слишком длинная строка NBT")
    stream.write(struct.pack(">H", len(encoded)))
    stream.write(encoded)


def _write_payload(stream: BinaryIO, tag_type: int, value: Any) -> None:
    if tag_type == 1:
        stream.write(struct.pack(">b", int(value)))
    elif tag_type == 2:
        stream.write(struct.pack(">h", int(value)))
    elif tag_type == 3:
        stream.write(struct.pack(">i", int(value)))
    elif tag_type == 4:
        stream.write(struct.pack(">q", int(value)))
    elif tag_type == 5:
        stream.write(struct.pack(">f", float(value)))
    elif tag_type == 6:
        stream.write(struct.pack(">d", float(value)))
    elif tag_type == 7:
        raw = bytes(value)
        stream.write(struct.pack(">i", len(raw)))
        stream.write(raw)
    elif tag_type == 8:
        _write_string(stream, str(value))
    elif tag_type == 9:
        element_type, items = value
        stream.write(struct.pack(">B", int(element_type)))
        stream.write(struct.pack(">i", len(items)))
        for item in items:
            _write_payload(stream, int(element_type), item)
    elif tag_type == 10:
        for name, (child_type, child_value) in value.items():
            stream.write(struct.pack(">B", int(child_type)))
            _write_string(stream, name)
            _write_payload(stream, int(child_type), child_value)
        stream.write(b"\x00")
    elif tag_type == 11:
        stream.write(struct.pack(">i", len(value)))
        for item in value:
            stream.write(struct.pack(">i", int(item)))
    elif tag_type == 12:
        stream.write(struct.pack(">i", len(value)))
        for item in value:
            stream.write(struct.pack(">q", int(item)))
    else:
        raise NBTError(f"Неизвестный тип NBT: {tag_type}")


def load_nbt_compound(path: Path) -> Dict[str, NBTValue]:
    try:
        with gzip.open(path, "rb") as stream:
            root_type = struct.unpack(">B", _read_exact(stream, 1))[0]
            if root_type != 10:
                raise NBTError("Корневой тег servers.dat не является TAG_Compound")
            _read_string(stream)  
            return _read_payload(stream, 10)
    except (OSError, EOFError, struct.error) as exc:
        raise NBTError(str(exc)) from exc


def save_nbt_compound(path: Path, root: Dict[str, NBTValue]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with gzip.open(temporary, "wb", compresslevel=6) as stream:
        stream.write(b"\x0a")
        _write_string(stream, "")
        _write_payload(stream, 10, root)
    os.replace(temporary, path)


def ensure_vvittox_server(minecraft_dir: str) -> bool:
    """
    Добавляет сервер в servers.dat.

    Возвращает True, если пришлось восстановить повреждённый/неподдерживаемый файл
    из нового списка. Исходный файл при этом сохраняется как резервная копия.
    """
    server_file = Path(minecraft_dir) / "servers.dat"
    recovered = False

    if server_file.exists():
        try:
            root = load_nbt_compound(server_file)
        except Exception:
            backup = server_file.with_name("servers.dat.freskmid_backup")
            if not backup.exists():
                shutil.copy2(server_file, backup)
            root = {}
            recovered = True
    else:
        root = {}

    servers_tag = root.get("servers")
    if not servers_tag or servers_tag[0] != 9:
        entries: List[Dict[str, NBTValue]] = []
        root["servers"] = (9, (10, entries))
    else:
        element_type, entries = servers_tag[1]
        if element_type != 10:
            entries = []
            root["servers"] = (9, (10, entries))

    found = False
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        ip_tag = entry.get("ip")
        if ip_tag and ip_tag[0] == 8 and str(ip_tag[1]).lower() == VVITTOX_SERVER_ADDRESS.lower():
            entry["name"] = (8, VVITTOX_SERVER_NAME)
            entry["ip"] = (8, VVITTOX_SERVER_ADDRESS)
            found = True
            break

    if not found:
        entries.insert(
            0,
            {
                "name": (8, VVITTOX_SERVER_NAME),
                "ip": (8, VVITTOX_SERVER_ADDRESS),
                "hideAddress": (1, 0),
            },
        )

    save_nbt_compound(server_file, root)
    return recovered



class ThemeManager:
    def __init__(self) -> None:
        self.current_theme = "Классическая"

    def get_theme(self, theme_name: Optional[str] = None) -> Dict[str, str]:
        return THEMES.get(theme_name or self.current_theme, THEMES["Классическая"])

    def set_theme(self, theme_name: str) -> bool:
        if theme_name not in THEMES:
            return False
        self.current_theme = theme_name
        return True


class FadeInWidget(QWidget):
    """Короткое появление без постоянного off-screen эффекта Qt."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.opacity_effect: Optional[QGraphicsOpacityEffect] = None
        self.fade_animation: Optional[QPropertyAnimation] = None

    def showEvent(self, event) -> None:
        if self.fade_animation is not None:
            self.fade_animation.stop()

        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.opacity_effect.setOpacity(0.0)
        self.setGraphicsEffect(self.opacity_effect)

        self.fade_animation = QPropertyAnimation(
            self.opacity_effect, b"opacity", self
        )
        self.fade_animation.setDuration(350)
        self.fade_animation.setStartValue(0.0)
        self.fade_animation.setEndValue(1.0)
        self.fade_animation.setEasingCurve(QEasingCurve.OutCubic)
        self.fade_animation.finished.connect(
            lambda: QTimer.singleShot(0, self._clear_fade_effect)
        )
        self.fade_animation.start()
        super().showEvent(event)

    def _clear_fade_effect(self) -> None:

        if self.graphicsEffect() is self.opacity_effect:
            self.setGraphicsEffect(None)
        self.opacity_effect = None
        self.fade_animation = None


class MinecraftParticlesBackground(QWidget):
    """Анимированный фон из исходной идеи лаунчера."""

    def __init__(self, theme_manager: ThemeManager) -> None:
        super().__init__()
        self.theme_manager = theme_manager
        self.particles: List[Dict[str, Any]] = []
        self.floating_blocks: List[Dict[str, Any]] = []
        self.time_value = 0.0
        self.reset_visuals()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_scene)
        self.timer.start(45)

    def reset_visuals(self) -> None:
        self.particles.clear()
        self.floating_blocks.clear()
        theme = self.theme_manager.get_theme()
        base = QColor(theme["primary"])
        secondary = QColor(theme["secondary"])

        width = max(self.width(), 1000)
        height = max(self.height(), 650)

        for _ in range(75):
            color = QColor(base if random.random() > 0.35 else secondary)
            color.setAlpha(random.randint(35, 125))
            self.particles.append(
                {
                    "x": random.uniform(0, width),
                    "y": random.uniform(-height, height),
                    "size": random.randint(2, 6),
                    "speed": random.uniform(0.35, 1.15),
                    "drift": random.uniform(-0.20, 0.20),
                    "rotation": random.uniform(0, 360),
                    "rotation_speed": random.uniform(-1.4, 1.4),
                    "color": color,
                }
            )

        for _ in range(10):
            color = QColor(base)
            color.setAlpha(random.randint(20, 55))
            self.floating_blocks.append(
                {
                    "x": random.uniform(0, width),
                    "y": random.uniform(-height, height),
                    "size": random.randint(18, 46),
                    "speed": random.uniform(0.15, 0.42),
                    "rotation": random.uniform(0, 360),
                    "rotation_speed": random.uniform(-0.25, 0.25),
                    "wave": random.uniform(0, math.tau),
                    "color": color,
                }
            )
        self.update()

    def update_scene(self) -> None:
        self.time_value += 0.04
        width = max(self.width(), 1)
        height = max(self.height(), 1)

        for particle in self.particles:
            particle["y"] += particle["speed"]
            particle["x"] += particle["drift"]
            particle["rotation"] += particle["rotation_speed"]
            if particle["y"] > height + 20:
                particle["y"] = random.uniform(-160, -20)
                particle["x"] = random.uniform(0, width)

        for block in self.floating_blocks:
            block["y"] += block["speed"]
            block["rotation"] += block["rotation_speed"]
            block["x"] += math.sin(self.time_value + block["wave"]) * 0.08
            if block["y"] > height + 70:
                block["y"] = random.uniform(-220, -60)
                block["x"] = random.uniform(0, width)

        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        theme = self.theme_manager.get_theme()

        top = QColor(theme["panel_alt"])
        bottom = QColor(theme["background"])
        gradient = QLinearGradient(0, 0, self.width(), self.height())
        gradient.setColorAt(0.0, top.darker(115))
        gradient.setColorAt(0.45, QColor(theme["background"]))
        gradient.setColorAt(1.0, bottom.darker(145))
        painter.fillRect(self.rect(), gradient)

        grid_color = QColor(theme["primary"])
        grid_color.setAlpha(14)
        painter.setPen(QPen(grid_color, 1))
        for x in range(0, self.width(), 32):
            painter.drawLine(x, 0, x, self.height())
        for y in range(0, self.height(), 32):
            painter.drawLine(0, y, self.width(), y)

        for block in self.floating_blocks:
            painter.save()
            painter.translate(block["x"], block["y"])
            painter.rotate(block["rotation"])
            painter.setPen(QPen(QColor(theme["primary"]), 1))
            painter.setBrush(QBrush(block["color"]))
            size = block["size"]
            painter.drawRect(QRect(-size // 2, -size // 2, size, size))
            painter.restore()

        for particle in self.particles:
            painter.save()
            painter.translate(particle["x"], particle["y"])
            painter.rotate(particle["rotation"])
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(particle["color"]))
            size = particle["size"]
            painter.drawRect(QRect(-size // 2, -size // 2, size, size))
            painter.restore()


class AccountManager:
    """Хранит только никнеймы. Пароли офлайн-лаунчеру не нужны."""

    def __init__(self) -> None:
        self.path = DATA_DIR / ACCOUNTS_FILE

    def load_accounts(self) -> List[str]:
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return [str(item) for item in data if str(item).strip()]
            if isinstance(data, dict):  
                return [str(name) for name in data.keys() if str(name).strip()]
        except (OSError, ValueError):
            pass
        return []

    def remember(self, username: str) -> None:
        accounts = self.load_accounts()
        if username not in accounts:
            accounts.insert(0, username)
        self.path.write_text(
            json.dumps(accounts[:12], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


class MinecraftButton(QPushButton):
    def __init__(
        self,
        text: str,
        theme_manager: ThemeManager,
        role: str = "primary",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(text, parent)
        self.theme_manager = theme_manager
        self.role = role
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(42)
        self.refresh_style()

    def refresh_style(self) -> None:
        theme = self.theme_manager.get_theme()
        if self.role == "primary":
            background = theme["primary"]
            hover = QColor(theme["primary"]).lighter(116).name()
            text = "#15120c"
            border = theme["secondary"]
        elif self.role == "success":
            background = theme["success"]
            hover = QColor(theme["success"]).lighter(115).name()
            text = "#10150d"
            border = QColor(theme["success"]).darker(145).name()
        else:
            background = theme["panel_alt"]
            hover = QColor(theme["panel_alt"]).lighter(122).name()
            text = theme["text"]
            border = hex_to_rgba(theme["primary"], 95)

        self.setStyleSheet(
            f"""
            QPushButton {{
                background: {background};
                color: {text};
                border: 1px solid {border};
                border-radius: 5px;
                padding: 9px 16px;
                font-size: 14px;
                font-weight: 800;
                font-family: 'Segoe UI', Arial, sans-serif;
            }}
            QPushButton:hover {{
                background: {hover};
                border: 1px solid {theme['primary']};
            }}
            QPushButton:pressed {{
                padding-top: 11px;
                padding-bottom: 7px;
            }}
            QPushButton:disabled {{
                background: #4a4a4a;
                color: #929292;
                border-color: #555555;
            }}
            """
        )


class NavigationButton(QPushButton):
    def __init__(self, text: str, theme_manager: ThemeManager) -> None:
        super().__init__(text)
        self.theme_manager = theme_manager
        self.active = False
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(46)
        self.refresh_style()

    def set_active(self, active: bool) -> None:
        self.active = active
        self.refresh_style()

    def refresh_style(self) -> None:
        theme = self.theme_manager.get_theme()
        background = hex_to_rgba(theme["primary"], 45) if self.active else "transparent"
        left = theme["primary"] if self.active else "transparent"
        self.setStyleSheet(
            f"""
            QPushButton {{
                background: {background};
                color: {theme['text']};
                border: none;
                border-left: 3px solid {left};
                border-radius: 5px;
                text-align: left;
                padding: 10px 14px;
                font-size: 14px;
                font-weight: 700;
                font-family: 'Segoe UI', Arial, sans-serif;
            }}
            QPushButton:hover {{
                background: {hex_to_rgba(theme['primary'], 28)};
                color: white;
            }}
            """
        )


class FeaturedServerBanner(QPushButton):
    """Стабильный баннер без вложенного QGraphicsEffect.

    Вложенная тень конфликтовала с opacity-анимацией родительского экрана и
    могла пропадать при постоянной перерисовке анимированного фона.
    """

    def __init__(self, main_window: "MainWindow") -> None:
        super().__init__()
        self.main_window = main_window
        self.hovered = False
        self.banner = QPixmap()
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(190)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setToolTip("Установить Minecraft 1.12.2 и войти на VVITTOX LAND")
        self.setAttribute(Qt.WA_OpaquePaintEvent, True)
        self.setAutoFillBackground(False)
        self.reload_banner()

    def enterEvent(self, event) -> None:
        self.hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self.hovered = False
        self.update()
        super().leaveEvent(event)

    def reload_banner(self) -> None:
        loaded = QPixmap(asset_path(VVITTOX_BANNER_FILE))
        self.banner = loaded.copy() if not loaded.isNull() else QPixmap()
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        theme = self.main_window.theme_manager.get_theme()
        full_rect = self.rect()
        rect = full_rect.adjusted(1, 1, -1, -1)
        radius = 7

 
        painter.fillRect(full_rect, QColor(theme["panel_alt"]))

        clip_path = QPainterPath()
        clip_path.addRoundedRect(QRectF(rect), radius, radius)
        painter.save()
        painter.setClipPath(clip_path)

        if not self.banner.isNull():
            scaled = self.banner.scaled(
                rect.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation
            )
            source_x = max(0, (scaled.width() - rect.width()) // 2)
            source_y = max(0, (scaled.height() - rect.height()) // 2)
            cropped = scaled.copy(source_x, source_y, rect.width(), rect.height())
            painter.drawPixmap(rect, cropped)
        else:
            fallback = QLinearGradient(rect.topLeft(), rect.bottomRight())
            fallback.setColorAt(0.0, QColor(theme["primary"]).darker(145))
            fallback.setColorAt(0.55, QColor(theme["panel_alt"]))
            fallback.setColorAt(1.0, QColor(theme["dark"]))
            painter.fillRect(rect, fallback)

            grid = QColor(theme["primary"])
            grid.setAlpha(35)
            painter.setPen(QPen(grid, 1))
            for x in range(rect.left(), rect.right(), 22):
                painter.drawLine(x, rect.top(), x, rect.bottom())
            for y in range(rect.top(), rect.bottom(), 22):
                painter.drawLine(rect.left(), y, rect.right(), y)

        overlay = QLinearGradient(rect.left(), rect.top(), rect.right(), rect.top())
        overlay.setColorAt(0.0, QColor(5, 7, 8, 230))
        overlay.setColorAt(0.62, QColor(5, 7, 8, 115))
        overlay.setColorAt(1.0, QColor(5, 7, 8, 35))
        painter.fillRect(rect, overlay)
        painter.restore()

        border = QColor(theme["primary"])
        border.setAlpha(240 if self.hovered else 130)
        painter.setPen(QPen(border, 2 if self.hovered else 1))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(rect, radius, radius)

        painter.setPen(QColor("white"))
        painter.setFont(QFont("Segoe UI", 23, QFont.Black))
        painter.drawText(
            rect.adjusted(28, 24, -20, -20),
            Qt.AlignLeft | Qt.AlignTop,
            VVITTOX_SERVER_NAME,
        )

        painter.setFont(QFont("Segoe UI", 10, QFont.DemiBold))
        painter.setPen(QColor(230, 235, 240))
        painter.drawText(
            rect.adjusted(30, 72, -20, -20),
            Qt.AlignLeft | Qt.AlignTop,
            f"Minecraft {VVITTOX_SERVER_VERSION} • SMP • Ванилла",
        )

        badge_rect = QRect(rect.left() + 29, rect.bottom() - 56, 250, 33)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(theme["success"]))
        painter.drawRoundedRect(badge_rect, 5, 5)
        painter.setPen(QColor(15, 20, 13))
        painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
        painter.drawText(badge_rect, Qt.AlignCenter, "УСТАНОВИТЬ 1.12.2 И ЗАЙТИ")

        painter.setPen(QColor(230, 235, 240))
        painter.setFont(QFont("Segoe UI", 9, QFont.DemiBold))
        painter.drawText(
            rect.adjusted(300, 0, -22, -24),
            Qt.AlignRight | Qt.AlignBottom,
            VVITTOX_SERVER_ADDRESS,
        )

        if self.banner.isNull():
            painter.setPen(QColor(theme["muted"]))
            painter.setFont(QFont("Segoe UI", 8))
            painter.drawText(
                rect.adjusted(300, 18, -20, -20),
                Qt.AlignRight | Qt.AlignTop,
                f"assets/{VVITTOX_BANNER_FILE}",
            )


class LaunchThread(QThread):
    progress_update_signal = pyqtSignal(int, int, str)
    state_update_signal = pyqtSignal(bool)
    error_signal = pyqtSignal(str)
    info_signal = pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__()
        self.version_id = ""
        self.username = ""
        self.settings: Dict[str, Any] = {}
        self.direct_server = False
        self.progress = 0
        self.progress_max = 0
        self.progress_label = ""

    def configure(
        self,
        version_id: str,
        username: str,
        settings: Dict[str, Any],
        direct_server: bool = False,
    ) -> None:
        self.version_id = version_id
        self.username = username.strip()
        self.settings = dict(settings)
        self.direct_server = direct_server

    def update_progress_label(self, value: str) -> None:
        self.progress_label = str(value)
        self.progress_update_signal.emit(self.progress, self.progress_max, self.progress_label)

    def update_progress(self, value: int) -> None:
        self.progress = int(value)
        self.progress_update_signal.emit(self.progress, self.progress_max, self.progress_label)

    def update_progress_max(self, value: int) -> None:
        self.progress_max = int(value)
        self.progress_update_signal.emit(self.progress, self.progress_max, self.progress_label)

    def _callback(self) -> Dict[str, Any]:
        return {
            "setStatus": self.update_progress_label,
            "setProgress": self.update_progress,
            "setMax": self.update_progress_max,
        }

    def _install_and_resolve_version(self) -> str:
        """Устанавливает и возвращает только выбранную ванильную версию Minecraft."""
        install_minecraft_version(
            version=self.version_id,
            minecraft_directory=minecraft_directory,
            callback=self._callback(),
        )
        return self.version_id

    def run(self) -> None:
        self.state_update_signal.emit(True)
        try:
            Path(minecraft_directory).mkdir(parents=True, exist_ok=True)

            if self.direct_server:
                self.update_progress_label("Добавляю VVITTOX LAND в список серверов…")
                recovered = ensure_vvittox_server(minecraft_directory)
                if recovered:
                    self.info_signal.emit(
                        "Старый servers.dat не удалось прочитать. Он сохранён как "
                        "servers.dat.freskmid_backup, а новый список создан автоматически."
                    )
                self.version_id = VVITTOX_SERVER_VERSION

            launch_version = self._install_and_resolve_version()

            username = self.username or generate_username()[0]
            selected_ram = min(max(2, int(self.settings.get("ram", 4))), get_max_ram())

            options: Dict[str, Any] = {
                "username": username,
                "uuid": offline_uuid(username),
                "token": "",
                "launcherName": "FRESKMID",
                "launcherVersion": APP_VERSION,
                "gameDirectory": minecraft_directory,
                "jvmArguments": [f"-Xmx{selected_ram}G", "-Xms1G"],
            }

            if self.direct_server:
                options["server"] = VVITTOX_SERVER_HOST
                options["port"] = VVITTOX_SERVER_PORT

            self.update_progress_label("Подготавливаю запуск Minecraft…")
            command = get_minecraft_command(
                version=launch_version,
                minecraft_directory=minecraft_directory,
                options=options,
            )

            self.progress_update_signal.emit(1, 1, "Minecraft запускается…")
            subprocess.run(command, cwd=minecraft_directory, check=False)
        except Exception as exc:
            self.error_signal.emit(str(exc))
        finally:
            self.state_update_signal.emit(False)


class LoginScreen(FadeInWidget):
    def __init__(self, main_window: "MainWindow") -> None:
        super().__init__()
        self.main_window = main_window
        self.account_manager = AccountManager()
        self.init_ui()
        self.refresh_theme()

    def init_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(45, 35, 45, 35)
        outer.addStretch()

        self.card = QFrame()
        self.card.setMinimumWidth(520)
        self.card.setMaximumWidth(590)
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(42, 30, 42, 32)
        card_layout.setSpacing(16)

        logo = QLabel()
        logo.setAlignment(Qt.AlignCenter)
        logo.setMinimumHeight(145)
        logo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        pixmap = QPixmap(asset_path("freskmid logo.png"))
        if not pixmap.isNull():
            logo.setPixmap(pixmap.scaled(445, 140, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            logo.setText("FRESKMID")
            logo.setFont(QFont("Segoe UI", 30, QFont.Black))

        subtitle = QLabel("Вход в лаунчер")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setObjectName("loginSubtitle")

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Введите никнейм Freskmid")
        self.username_input.setMinimumHeight(48)
        self.username_input.returnPressed.connect(self.login)

        accounts = self.account_manager.load_accounts()
        self.saved_accounts = QComboBox()
        self.saved_accounts.addItem("Сохранённые Аккаунты Freskmid ")
        self.saved_accounts.addItems(accounts)
        self.saved_accounts.currentTextChanged.connect(self.select_account)
        self.saved_accounts.setVisible(bool(accounts))

        note = QLabel("Пароль не требуется: текущий режим запуска использует офлайн-никнейм.")
        note.setWordWrap(True)
        note.setObjectName("mutedLabel")

        self.remember_check = QCheckBox("Запомнить Аккаунт")
        self.remember_check.setChecked(True)

        self.login_button = MinecraftButton("Войти", self.main_window.theme_manager)
        self.login_button.clicked.connect(self.login)

        card_layout.addWidget(logo)
        card_layout.addWidget(subtitle)
        card_layout.addSpacing(5)
        card_layout.addWidget(self.username_input)
        card_layout.addWidget(self.saved_accounts)
        card_layout.addWidget(note)
        card_layout.addWidget(self.remember_check)
        card_layout.addWidget(self.login_button)

        outer.addWidget(self.card, alignment=Qt.AlignCenter)
        outer.addStretch()

    def select_account(self, value: str) -> None:
        if value and value != "Сохранённые Аккаунты Freskmid":
            self.username_input.setText(value)

    def login(self) -> None:
        username = self.username_input.text().strip()
        if not username:
            QMessageBox.warning(self, "Никнейм", "Введите никнейм Freskmid.")
            return
        if self.remember_check.isChecked():
            self.account_manager.remember(username)
        self.main_window.show_main_screen(username)

    def refresh_theme(self) -> None:
        theme = self.main_window.theme_manager.get_theme()
        self.card.setStyleSheet(
            f"""
            QFrame {{
                background: {hex_to_rgba(theme['panel'], 242)};
                border: 1px solid {hex_to_rgba(theme['primary'], 95)};
                border-radius: 6px;
            }}
            QLabel#loginSubtitle {{
                color: {theme['text']};
                font-size: 20px;
                font-weight: 800;
                border: none;
            }}
            QLabel#mutedLabel {{
                color: {theme['muted']};
                font-size: 12px;
                border: none;
            }}
            """
        )
        self.username_input.setStyleSheet(self.main_window.input_style())
        self.saved_accounts.setStyleSheet(self.main_window.combo_style())
        self.remember_check.setStyleSheet(
            f"color: {theme['muted']}; font-size: 13px; border: none;"
        )
        self.login_button.refresh_style()


class MainScreen(FadeInWidget):
    def __init__(self, main_window: "MainWindow") -> None:
        super().__init__()
        self.main_window = main_window
        self.init_ui()
        self.refresh_theme()

    def init_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(18)

        self.sidebar = QFrame()
        self.sidebar.setFixedWidth(225)
        side = QVBoxLayout(self.sidebar)
        side.setContentsMargins(15, 20, 15, 18)
        side.setSpacing(8)

        logo = QLabel()
        logo.setAlignment(Qt.AlignCenter)
        logo.setMinimumHeight(84)
        logo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        pixmap = QPixmap(asset_path("freskmid logo.png"))
        if not pixmap.isNull():
            logo.setPixmap(pixmap.scaled(195, 82, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            logo.setText("FRESKMID")
            logo.setFont(QFont("Segoe UI", 20, QFont.Black))

        self.nav_home = NavigationButton("Главная", self.main_window.theme_manager)
        self.nav_home.set_active(True)
        self.nav_settings = NavigationButton("Настройки", self.main_window.theme_manager)
        self.nav_folder = NavigationButton("Папка игры", self.main_window.theme_manager)
        self.nav_logout = NavigationButton("Сменить аккаунт", self.main_window.theme_manager)

        self.nav_settings.clicked.connect(self.main_window.show_settings)
        self.nav_folder.clicked.connect(self.open_game_folder)
        self.nav_logout.clicked.connect(self.main_window.show_login)

        self.profile_card = QFrame()
        profile_layout = QVBoxLayout(self.profile_card)
        profile_layout.setContentsMargins(12, 12, 12, 12)
        profile_layout.setSpacing(3)
        self.profile_caption = QLabel("ПРОФИЛЬ")
        self.profile_caption.setObjectName("caption")
        self.profile_name = QLabel("Игрок")
        self.profile_name.setWordWrap(True)
        self.profile_name.setObjectName("profileName")
        profile_layout.addWidget(self.profile_caption)
        profile_layout.addWidget(self.profile_name)

        side.addWidget(logo)
        side.addSpacing(16)
        side.addWidget(self.nav_home)
        side.addWidget(self.nav_settings)
        side.addWidget(self.nav_folder)
        side.addStretch()
        side.addWidget(self.profile_card)
        side.addWidget(self.nav_logout)

        content = QVBoxLayout()
        content.setSpacing(14)

        header_layout = QHBoxLayout()
        title_box = QVBoxLayout()
        self.page_title = QLabel("Главная")
        self.page_title.setObjectName("pageTitle")
        self.welcome_label = QLabel("Добро пожаловать")
        self.welcome_label.setObjectName("muted")
        title_box.addWidget(self.page_title)
        title_box.addWidget(self.welcome_label)
        header_layout.addLayout(title_box)
        header_layout.addStretch()

        self.server_banner = FeaturedServerBanner(self.main_window)
        self.server_banner.clicked.connect(self.main_window.launch_vvittox_land)

        self.launch_card = QFrame()
        launch_layout = QGridLayout(self.launch_card)
        launch_layout.setContentsMargins(20, 18, 20, 18)
        launch_layout.setHorizontalSpacing(13)
        launch_layout.setVerticalSpacing(9)

        version_label = QLabel("Версия игры")
        version_label.setObjectName("fieldLabel")
        nickname_label = QLabel("Никнейм")
        nickname_label.setObjectName("fieldLabel")

        self.version_select = QComboBox()
        self.version_select.setMinimumHeight(43)
        self.load_versions()

        self.username = QLineEdit()
        self.username.setPlaceholderText("Никнейм")
        self.username.setMinimumHeight(43)

        self.start_button = MinecraftButton("ИГРАТЬ", self.main_window.theme_manager, "primary")
        self.start_button.setMinimumWidth(180)
        self.start_button.clicked.connect(self.main_window.launch_game)

        self.folder_button = MinecraftButton("ПАПКА", self.main_window.theme_manager, "secondary")
        self.folder_button.setFixedWidth(82)
        self.folder_button.clicked.connect(self.open_game_folder)

        launch_layout.addWidget(version_label, 0, 0)
        launch_layout.addWidget(nickname_label, 0, 1)
        launch_layout.addWidget(self.version_select, 1, 0)
        launch_layout.addWidget(self.username, 1, 1)
        launch_layout.addWidget(self.start_button, 1, 2)
        launch_layout.addWidget(self.folder_button, 1, 3)
        launch_layout.setColumnStretch(0, 2)
        launch_layout.setColumnStretch(1, 2)

        self.progress_card = QFrame()
        progress_layout = QVBoxLayout(self.progress_card)
        progress_layout.setContentsMargins(16, 11, 16, 11)
        progress_layout.setSpacing(7)
        self.start_progress_label = QLabel("")
        self.start_progress_label.setObjectName("progressLabel")
        self.start_progress = QProgressBar()
        self.start_progress.setTextVisible(True)
        self.start_progress.setMinimumHeight(20)
        progress_layout.addWidget(self.start_progress_label)
        progress_layout.addWidget(self.start_progress)
        self.progress_card.setVisible(False)

        hint = QLabel(
            "Нажатие на баннер VVITTOX LAND автоматически добавит сервер, "
            "установит чистую Minecraft 1.12.2 и запустит игру с прямым подключением."
        )
        hint.setWordWrap(True)
        hint.setObjectName("hint")

        content.addLayout(header_layout)
        content.addWidget(self.server_banner)
        content.addWidget(self.launch_card)
        content.addWidget(self.progress_card)
        content.addWidget(hint)
        content.addStretch()

        root.addWidget(self.sidebar)
        root.addLayout(content, 1)

    def load_versions(self) -> None:
        self.version_select.clear()

        ids: List[str] = []
        try:
            ids = [item["id"] for item in get_version_list()]
        except Exception:
            ids = [VVITTOX_SERVER_VERSION]

        if VVITTOX_SERVER_VERSION not in ids:
            ids.insert(0, VVITTOX_SERVER_VERSION)


        self.version_select.addItem(
            f"VVITTOX LAND — Vanilla {VVITTOX_SERVER_VERSION}",
            VVITTOX_SERVER_VERSION,
        )
        for version_id in ids:
            if version_id != VVITTOX_SERVER_VERSION:
                self.version_select.addItem(f"Vanilla {version_id}", version_id)

        self.version_select.setCurrentIndex(0)

    def open_game_folder(self) -> None:
        Path(minecraft_directory).mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(minecraft_directory))

    def set_username(self, username: str) -> None:
        self.username.setText(username)
        self.profile_name.setText(username or "Гость")
        self.welcome_label.setText(
            f"Добро пожаловать, {username}" if username else "Выберите версию и начните игру"
        )

    def set_busy(self, busy: bool) -> None:
        self.start_button.setDisabled(busy)
        self.server_banner.setDisabled(busy)
        self.version_select.setDisabled(busy)
        self.progress_card.setVisible(busy)
        if not busy:
            self.start_button.setText("ИГРАТЬ")

    def refresh_theme(self) -> None:
        theme = self.main_window.theme_manager.get_theme()
        panel_style = f"""
            QFrame {{
                background: {hex_to_rgba(theme['panel'], 235)};
                border: 1px solid {hex_to_rgba(theme['primary'], 55)};
                border-radius: 5px;
            }}
        """
        self.sidebar.setStyleSheet(
            panel_style
            + f"""
            QLabel {{ border: none; color: {theme['text']}; }}
            QFrame {{ background: {hex_to_rgba(theme['panel'], 242)}; }}
            """
        )
        self.profile_card.setStyleSheet(
            f"""
            QFrame {{
                background: {theme['panel_alt']};
                border: 1px solid {hex_to_rgba(theme['primary'], 50)};
                border-radius: 6px;
            }}
            QLabel {{ border: none; }}
            QLabel#caption {{ color: {theme['muted']}; font-size: 10px; font-weight: 800; }}
            QLabel#profileName {{ color: {theme['text']}; font-size: 14px; font-weight: 800; }}
            """
        )
        self.launch_card.setStyleSheet(
            panel_style
            + f"""
            QLabel {{ border: none; }}
            QLabel#fieldLabel {{ color: {theme['muted']}; font-size: 11px; font-weight: 800; }}
            """
        )
        self.progress_card.setStyleSheet(panel_style)
        self.page_title.setStyleSheet(
            f"color: {theme['text']}; font-size: 27px; font-weight: 900;"
        )
        self.welcome_label.setStyleSheet(
            f"color: {theme['muted']}; font-size: 13px;"
        )
        self.start_progress_label.setStyleSheet(
            f"color: {theme['text']}; font-size: 12px; font-weight: 700; border: none;"
        )
        self.start_progress.setStyleSheet(self.main_window.progress_style())
        self.version_select.setStyleSheet(self.main_window.combo_style())
        self.username.setStyleSheet(self.main_window.input_style())
        self.start_button.refresh_style()
        self.folder_button.refresh_style()
        for button in (self.nav_home, self.nav_settings, self.nav_folder, self.nav_logout):
            button.refresh_style()
        self.server_banner.update()


class SettingsScreen(FadeInWidget):
    def __init__(self, main_window: "MainWindow") -> None:
        super().__init__()
        self.main_window = main_window
        self.init_ui()
        self.refresh_theme()

    def init_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(70, 35, 70, 35)
        root.setSpacing(15)

        header = QHBoxLayout()
        title = QLabel("Настройки")
        title.setObjectName("settingsTitle")
        back = MinecraftButton("НАЗАД", self.main_window.theme_manager, "secondary")
        back.setFixedWidth(130)
        back.clicked.connect(lambda: self.main_window.show_main_screen(self.main_window.current_username))
        header.addWidget(title)
        header.addStretch()
        header.addWidget(back)
        self.back_button = back

        self.tabs = QTabWidget()
        self.general_tab = QWidget()
        self.about_tab = QWidget()
        self.tabs.addTab(self.general_tab, "Основные")
        self.tabs.addTab(self.about_tab, "О проекте")

        general_layout = QVBoxLayout(self.general_tab)
        general_layout.setContentsMargins(22, 22, 22, 22)
        general_layout.setSpacing(17)

        theme_group = QGroupBox("Оформление")
        theme_layout = QVBoxLayout(theme_group)
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(THEMES.keys())
        self.theme_combo.setCurrentText(self.main_window.theme_manager.current_theme)
        self.theme_combo.currentTextChanged.connect(self.change_theme)
        theme_layout.addWidget(QLabel("Цветовая тема лаунчера"))
        theme_layout.addWidget(self.theme_combo)

        performance_group = QGroupBox("Производительность")
        perf_layout = QGridLayout(performance_group)
        self.ram_slider = QSlider(Qt.Horizontal)
        self.ram_slider.setMinimum(2)
        self.ram_slider.setMaximum(get_max_ram())
        self.ram_slider.setValue(min(int(self.main_window.settings.get("ram", 4)), get_max_ram()))
        self.ram_value = QLabel(f"{self.ram_slider.value()} GB")
        self.ram_slider.valueChanged.connect(lambda value: self.ram_value.setText(f"{value} GB"))
        perf_layout.addWidget(QLabel("Оперативная память"), 0, 0)
        perf_layout.addWidget(self.ram_slider, 0, 1)
        perf_layout.addWidget(self.ram_value, 0, 2)


        general_layout.addWidget(theme_group)
        general_layout.addWidget(performance_group)
        general_layout.addStretch()

        about_layout = QVBoxLayout(self.about_tab)
        about_text = QTextEdit()
        about_text.setReadOnly(True)
        about_text.setHtml(
            f"""
            <h2>FRESKMID</h2>
            <p><b>Версия:</b> {APP_VERSION}</p>
            <p><b>Freskmid лаунчер от</b> VVITTOX</p>
            <p><b>Удобный и стабильный лаунчер для слабых пк.</p>
            <p><b>оффициальный сайт: https://sites.google.com/view/vvittox/vvittox 
            <p><b>Дискорд:  https://discord.gg/XUjfd7uucj
            """
        )
        about_layout.addWidget(about_text)
        self.about_text = about_text

        root.addLayout(header)
        root.addWidget(self.tabs)

    def change_theme(self, theme_name: str) -> None:
        if self.main_window.theme_manager.set_theme(theme_name):
            self.main_window.apply_theme()

    def get_settings(self) -> Dict[str, Any]:
        return {"ram": self.ram_slider.value()}

    def refresh_theme(self) -> None:
        theme = self.main_window.theme_manager.get_theme()
        self.setStyleSheet(
            f"""
            QLabel#settingsTitle {{
                color: {theme['text']};
                font-size: 28px;
                font-weight: 900;
            }}
            QGroupBox {{
                color: {theme['text']};
                font-size: 14px;
                font-weight: 800;
                border: 1px solid {hex_to_rgba(theme['primary'], 75)};
                border-radius: 5px;
                margin-top: 12px;
                padding: 18px 14px 14px 14px;
                background: {hex_to_rgba(theme['panel'], 228)};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
            }}
            QLabel {{ color: {theme['muted']}; }}
            QTabWidget::pane {{
                border: 1px solid {hex_to_rgba(theme['primary'], 55)};
                border-radius: 5px;
                background: {hex_to_rgba(theme['panel'], 235)};
                top: -1px;
            }}
            QTabBar::tab {{
                background: {theme['panel_alt']};
                color: {theme['muted']};
                padding: 10px 22px;
                border: none;
                margin-right: 4px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                font-weight: 700;
            }}
            QTabBar::tab:selected {{
                background: {theme['primary']};
                color: #15120c;
            }}
            """
        )
        self.theme_combo.setStyleSheet(self.main_window.combo_style())
        self.ram_slider.setStyleSheet(self.main_window.slider_style())
        self.about_text.setStyleSheet(
            f"background: {theme['panel_alt']}; color: {theme['text']}; border: none; padding: 14px;"
        )
        self.back_button.refresh_style()


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1060, 650)
        self.setMinimumSize(930, 570)
        self.current_username = ""
        self.settings: Dict[str, Any] = {"ram": min(4, get_max_ram())}
        self.theme_manager = ThemeManager()
        self.load_settings()

        icon = QIcon(asset_path("freskmid icon.png"))
        if not icon.isNull():
            self.setWindowIcon(icon)

        self.background = MinecraftParticlesBackground(self.theme_manager)
        self.setCentralWidget(self.background)
        background_layout = QVBoxLayout(self.background)
        background_layout.setContentsMargins(0, 0, 0, 0)

        self.stacked_widget = QStackedWidget()
        self.stacked_widget.setStyleSheet("background: transparent;")
        background_layout.addWidget(self.stacked_widget)

        self.login_screen = LoginScreen(self)
        self.main_screen = MainScreen(self)
        self.settings_screen = SettingsScreen(self)
        self.stacked_widget.addWidget(self.login_screen)
        self.stacked_widget.addWidget(self.main_screen)
        self.stacked_widget.addWidget(self.settings_screen)
        self.stacked_widget.setCurrentWidget(self.login_screen)

        self.launch_thread = LaunchThread()
        self.launch_thread.state_update_signal.connect(self.state_update)
        self.launch_thread.progress_update_signal.connect(self.update_progress)
        self.launch_thread.error_signal.connect(self.show_error)
        self.launch_thread.info_signal.connect(self.show_info)

        self.apply_theme()

    def load_settings(self) -> None:
        path = DATA_DIR / SETTINGS_FILE
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            theme_name = data.get("theme")
            if theme_name in THEMES:
                self.theme_manager.set_theme(theme_name)
            ram = int(data.get("ram", self.settings["ram"]))
            self.settings["ram"] = min(max(2, ram), get_max_ram())
        except (OSError, ValueError, TypeError):
            pass

    def save_settings(self) -> None:
        data = {
            "theme": self.theme_manager.current_theme,
            "ram": int(self.settings.get("ram", 4)),
        }
        try:
            (DATA_DIR / SETTINGS_FILE).write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except OSError:
            pass

    def closeEvent(self, event) -> None:
        self.settings = self.settings_screen.get_settings()
        self.save_settings()
        super().closeEvent(event)

    def input_style(self) -> str:
        theme = self.theme_manager.get_theme()
        return f"""
            QLineEdit {{
                background: {theme['panel_alt']};
                color: {theme['text']};
                border: 1px solid {hex_to_rgba(theme['primary'], 55)};
                border-radius: 5px;
                padding: 9px 12px;
                font-size: 14px;
                selection-background-color: {theme['primary']};
            }}
            QLineEdit:focus {{ border: 1px solid {theme['primary']}; }}
            QLineEdit:disabled {{ color: #777777; background: #292929; }}
        """

    def combo_style(self) -> str:
        theme = self.theme_manager.get_theme()
        return f"""
            QComboBox {{
                background: {theme['panel_alt']};
                color: {theme['text']};
                border: 1px solid {hex_to_rgba(theme['primary'], 55)};
                border-radius: 5px;
                padding: 8px 12px;
                font-size: 13px;
            }}
            QComboBox:hover, QComboBox:focus {{ border-color: {theme['primary']}; }}
            QComboBox::drop-down {{ border: none; width: 30px; }}
            QComboBox QAbstractItemView {{
                background: {theme['panel_alt']};
                color: {theme['text']};
                border: 1px solid {theme['primary']};
                selection-background-color: {theme['secondary']};
                padding: 5px;
            }}
        """

    def progress_style(self) -> str:
        theme = self.theme_manager.get_theme()
        return f"""
            QProgressBar {{
                background: {theme['panel_alt']};
                color: {theme['text']};
                border: 1px solid {hex_to_rgba(theme['primary'], 45)};
                border-radius: 5px;
                text-align: center;
                font-size: 11px;
                font-weight: 800;
            }}
            QProgressBar::chunk {{
                background: {theme['primary']};
                border-radius: 5px;
            }}
        """

    def slider_style(self) -> str:
        theme = self.theme_manager.get_theme()
        return f"""
            QSlider::groove:horizontal {{
                height: 8px;
                background: {theme['panel_alt']};
                border-radius: 4px;
            }}
            QSlider::sub-page:horizontal {{
                background: {theme['primary']};
                border-radius: 4px;
            }}
            QSlider::handle:horizontal {{
                width: 18px;
                margin: -5px 0;
                background: {theme['text']};
                border: 2px solid {theme['primary']};
                border-radius: 9px;
            }}
        """

    def apply_theme(self) -> None:
        theme = self.theme_manager.get_theme()
        self.setStyleSheet(
            f"""
            QMainWindow, QWidget {{
                font-family: 'Segoe UI', Arial, sans-serif;
                color: {theme['text']};
            }}
            QToolTip {{
                background: {theme['panel_alt']};
                color: {theme['text']};
                border: 1px solid {theme['primary']};
                padding: 5px;
            }}
            """
        )
        self.background.reset_visuals()
        self.login_screen.refresh_theme()
        self.main_screen.refresh_theme()
        self.settings_screen.refresh_theme()
        self.save_settings()

    def show_main_screen(self, username: str = "") -> None:
        if username:
            self.current_username = username
        self.main_screen.set_username(self.current_username)
        self.stacked_widget.setCurrentWidget(self.main_screen)

    def show_login(self) -> None:
        if self.launch_thread.isRunning():
            return
        self.stacked_widget.setCurrentWidget(self.login_screen)

    def show_settings(self) -> None:
        if self.launch_thread.isRunning():
            return
        self.settings = self.settings_screen.get_settings()
        self.stacked_widget.setCurrentWidget(self.settings_screen)

    def reload_server_banner(self) -> None:
        self.main_screen.server_banner.reload_banner()
        QMessageBox.information(
            self,
            "Баннер",
            f"Баннер перечитан из assets/{VVITTOX_BANNER_FILE}",
        )

    def _validated_username(self) -> Optional[str]:
        username = self.main_screen.username.text().strip()
        if not username:
            QMessageBox.warning(self, "Никнейм", "Введите никнейм Minecraft.")
            return None
        self.current_username = username
        self.main_screen.set_username(username)
        return username

    def _start_launch(self, version_id: str, direct_server: bool) -> None:
        if self.launch_thread.isRunning():
            return
        username = self._validated_username()
        if username is None:
            return

        self.settings = self.settings_screen.get_settings()
        self.save_settings()
        self.launch_thread.configure(version_id, username, self.settings, direct_server)
        self.main_screen.start_button.setText(
            "ПОДГОТОВКА…" if not direct_server else "VVITTOX LAND…"
        )
        self.launch_thread.start()

    def launch_game(self) -> None:
        selected = self.main_screen.version_select.currentData()
        self._start_launch(str(selected or self.main_screen.version_select.currentText()), False)

    def launch_vvittox_land(self) -> None:
        index = self.main_screen.version_select.findData(VVITTOX_SERVER_VERSION)
        if index >= 0:
            self.main_screen.version_select.setCurrentIndex(index)
        self._start_launch(VVITTOX_SERVER_VERSION, True)

    def state_update(self, busy: bool) -> None:
        self.main_screen.set_busy(busy)

    def update_progress(self, progress: int, maximum: int, label: str) -> None:
        safe_maximum = max(1, int(maximum))
        self.main_screen.start_progress.setMaximum(safe_maximum)
        self.main_screen.start_progress.setValue(min(int(progress), safe_maximum))
        self.main_screen.start_progress_label.setText(label or "Подготовка…")

    def show_error(self, error_message: str) -> None:
        QMessageBox.critical(
            self,
            "Ошибка запуска",
            "Не удалось установить или запустить Minecraft:\n\n" + error_message,
        )

    def show_info(self, message: str) -> None:
        QMessageBox.information(self, "FRESKMID", message)


if __name__ == "__main__":
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())