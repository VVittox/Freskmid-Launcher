from __future__ import annotations


import hashlib
import hmac
import json
import math
import os
import random
import secrets
import shlex
import shutil
import struct
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
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
    QPoint,
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
    QFileDialog,
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
APP_VERSION = "4.2.0"
ACCOUNTS_FILE = "accounts.json"
SETTINGS_FILE = "launcher_settings.json"

PROMO_TITLE = "VVittox Works"
PROMO_SUBTITLE = "Другие проекты VVittox, которые могут быть интересны."
PROMO_BANNER_FILE = "Its all VVittox Works.png"
CURSEFORGE_API_URL = "https://api.curseforge.com/v1"
CURSEFORGE_MINECRAFT_GAME_ID = 432
CURSEFORGE_MOD_CLASS_ID = 6
CURSEFORGE_API_KEY = os.environ.get("CURSEFORGE_API_KEY", "").strip()

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


def ensure_mods_folder() -> Path:
    mods_dir = Path(minecraft_directory) / "mods"
    mods_dir.mkdir(parents=True, exist_ok=True)
    return mods_dir


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
    """Локальная система профилей VVittox Works Accounts."""

    def __init__(self) -> None:
        self.path = DATA_DIR / ACCOUNTS_FILE

    def load_accounts(self) -> List[str]:
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return [str(item) for item in data if str(item).strip()]
            if isinstance(data, dict) and isinstance(data.get("profiles"), dict):
                return [str(name) for name in data["profiles"] if str(name).strip()]
            if isinstance(data, dict):
                return [str(name) for name in data.keys() if str(name).strip()]
        except (OSError, ValueError):
            pass
        return []

    def _load_profiles(self) -> Dict[str, Dict[str, Any]]:
        if not self.path.exists():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("profiles"), dict):
                return data["profiles"]
            if isinstance(data, dict):
                return {
                    str(name): {"username": str(name), "password": "", "salt": "", "skin": ""}
                    for name in data
                }
            if isinstance(data, list):
                return {
                    str(name): {"username": str(name), "password": "", "salt": "", "skin": ""}
                    for name in data
                }
        except (OSError, ValueError, TypeError):
            pass
        return {}

    def _save_profiles(self, profiles: Dict[str, Dict[str, Any]]) -> None:
        self.path.write_text(
            json.dumps({"profiles": profiles}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def get_profile(self, username: str) -> Dict[str, Any]:
        return dict(self._load_profiles().get(username, {"username": username, "skin": ""}))

    def register(self, username: str, password: str) -> Tuple[bool, str]:
        username = username.strip()
        profiles = self._load_profiles()
        if len(username) < 3:
            return False, "Никнейм должен содержать минимум 3 символа."
        if len(password) < 4:
            return False, "Пароль должен содержать минимум 4 символа."
        if username in profiles:
            return False, "Такой аккаунт уже существует."
        salt = secrets.token_hex(16)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 180000).hex()
        profiles[username] = {"username": username, "salt": salt, "password": digest, "skin": ""}
        self._save_profiles(profiles)
        return True, "Аккаунт создан."

    def authenticate(self, username: str, password: str) -> Tuple[bool, str]:
        profile = self._load_profiles().get(username.strip())
        if profile is None:
            return False, "Аккаунт не найден. Зарегистрируйтесь."
        if not profile.get("password"):
            return True, "Старый офлайн-профиль подключён. Пароль можно добавить в профиле."
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), str(profile.get("salt", "")).encode(), 180000
        ).hex()
        if not hmac.compare_digest(digest, str(profile.get("password", ""))):
            return False, "Неверный пароль."
        return True, "Вход выполнен."

    def update_profile(self, username: str, new_username: str, password: str, skin: str) -> Tuple[bool, str]:
        profiles = self._load_profiles()
        profile = profiles.get(username)
        if profile is None:
            return False, "Профиль не найден."
        new_username = new_username.strip()
        if len(new_username) < 3:
            return False, "Никнейм должен содержать минимум 3 символа."
        if new_username != username and new_username in profiles:
            return False, "Новый никнейм уже занят."
        profile["username"] = new_username
        profile["skin"] = skin
        if password:
            if len(password) < 4:
                return False, "Новый пароль должен содержать минимум 4 символа."
            salt = secrets.token_hex(16)
            profile["salt"] = salt
            profile["password"] = hashlib.pbkdf2_hmac(
                "sha256", password.encode(), salt.encode(), 180000
            ).hex()
        profiles.pop(username, None)
        profiles[new_username] = profile
        self._save_profiles(profiles)
        return True, new_username

    def remember(self, username: str) -> None:
        profiles = self._load_profiles()
        profiles.setdefault(username, {"username": username, "password": "", "salt": "", "skin": ""})
        self._save_profiles(profiles)


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
            QPushButton:pressed {{
                background: {hex_to_rgba(theme['secondary'], 70)};
                padding-left: 17px;
            }}
            """
        )


class PromoBanner(QPushButton):
    """Единый рекламный баннер со статичной картинкой проекта."""

    def __init__(self, main_window: "MainWindow") -> None:
        super().__init__()
        self.main_window = main_window
        self.hovered = False
        self.banner = QPixmap()
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(190)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setToolTip("Запустить выбранную версию Minecraft")
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
        loaded = QPixmap(asset_path(PROMO_BANNER_FILE))
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
            PROMO_TITLE,
        )

        painter.setFont(QFont("Segoe UI", 10, QFont.DemiBold))
        painter.setPen(QColor(230, 235, 240))
        painter.drawText(
            rect.adjusted(30, 72, -20, -20),
            Qt.AlignLeft | Qt.AlignTop,
            PROMO_SUBTITLE,
        )

        badge_rect = QRect(rect.left() + 29, rect.bottom() - 56, 250, 33)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(theme["success"]))
        painter.drawRoundedRect(badge_rect, 5, 5)
        painter.setPen(QColor(15, 20, 13))
        painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
        painter.drawText(badge_rect, Qt.AlignCenter, "ВЫБЕРИ ВЕРСИЮ И ЗАПУСТИ")

        if self.banner.isNull():
            painter.setPen(QColor(theme["muted"]))
            painter.setFont(QFont("Segoe UI", 8))
            painter.drawText(
                rect.adjusted(300, 18, -20, -20),
                Qt.AlignRight | Qt.AlignTop,
                f"assets/{PROMO_BANNER_FILE}",
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
        self.progress = 0
        self.progress_max = 0
        self.progress_label = ""

    def configure(
        self,
        version_id: str,
        username: str,
        settings: Dict[str, Any],
    ) -> None:
        self.version_id = version_id
        self.username = username.strip()
        self.settings = dict(settings)

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
            if self.settings.get("use_java_args"):
                custom_args = str(self.settings.get("java_args", "")).strip()
                if custom_args:
                    options["jvmArguments"].extend(shlex.split(custom_args))

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


class CurseForgeSearchThread(QThread):
    results_signal = pyqtSignal(list)
    error_signal = pyqtSignal(str)

    def __init__(self, query: str, version: str, loader: str) -> None:
        super().__init__()
        self.query = query
        self.version = version
        self.loader = loader

    def run(self) -> None:
        if not CURSEFORGE_API_KEY:
            self._search_modrinth()
            return

        params = {
            "gameId": CURSEFORGE_MINECRAFT_GAME_ID,
            "classId": CURSEFORGE_MOD_CLASS_ID,
            "searchFilter": self.query,
            "sortField": 2,
            "sortOrder": "desc",
            "pageSize": 24,
        }
        if self.version:
            params["gameVersion"] = self.version
        if self.loader and self.loader != "Авто":
            params["modLoaderType"] = {"Forge": 1, "Fabric": 4, "Quilt": 5}.get(self.loader, 0)

        request = urllib.request.Request(
            f"{CURSEFORGE_API_URL}/mods/search?{urllib.parse.urlencode(params)}",
            headers={"x-api-key": CURSEFORGE_API_KEY, "Accept": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=25) as response:
                payload = json.loads(response.read().decode("utf-8"))
            results = []
            for mod in payload.get("data", []):
                results.append(
                    {
                        "id": mod.get("id"),
                        "name": mod.get("name", "Без названия"),
                        "author": mod.get("authors", [{}])[0].get("name", "CurseForge"),
                        "summary": mod.get("summary", "").strip(),
                        "downloads": int(mod.get("downloadCount", 0)),
                        "icon": mod.get("logo", {}).get("url", ""),
                        "url": mod.get("links", {}).get("websiteUrl", ""),
                    }
                )
            self.results_signal.emit(results)
        except Exception as exc:
            self.error_signal.emit(f"CurseForge: {exc}")

    def _search_modrinth(self) -> None:
        params = {"query": self.query, "limit": 24, "index": "downloads"}
        if self.version:
            params["facets"] = json.dumps([["versions:" + self.version]])
        request = urllib.request.Request(
            "https://api.modrinth.com/v2/search?" + urllib.parse.urlencode(params),
            headers={"User-Agent": "FRESKMID Launcher"},
        )
        try:
            with urllib.request.urlopen(request, timeout=25) as response:
                payload = json.loads(response.read().decode("utf-8"))
            results = []
            for mod in payload.get("hits", []):
                results.append(
                    {
                        "id": str(mod.get("project_id", "")),
                        "source": "modrinth",
                        "name": mod.get("title", "Без названия"),
                        "author": mod.get("author", "Modrinth"),
                        "summary": mod.get("description", "").strip(),
                        "downloads": int(mod.get("downloads", 0)),
                        "icon": mod.get("icon_url", ""),
                        "url": "https://modrinth.com/mod/" + str(mod.get("slug", "")),
                    }
                )
            self.results_signal.emit(results)
        except Exception as exc:
            self.error_signal.emit(f"Каталог модов: {exc}")


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

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Пароль VVittox Works Accounts")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setMinimumHeight(48)
        self.password_input.returnPressed.connect(self.login)

        self.register_button = MinecraftButton("Создать аккаунт", self.main_window.theme_manager, "secondary")
        self.register_button.clicked.connect(self.register)

        self.login_button = MinecraftButton("Войти", self.main_window.theme_manager)
        self.login_button.clicked.connect(self.login)

        card_layout.addWidget(logo)
        card_layout.addWidget(subtitle)
        card_layout.addSpacing(5)
        card_layout.addWidget(self.username_input)
        card_layout.addWidget(self.password_input)
        card_layout.addWidget(self.saved_accounts)
        card_layout.addWidget(note)
        card_layout.addWidget(self.remember_check)
        card_layout.addWidget(self.login_button)
        card_layout.addWidget(self.register_button)

        outer.addWidget(self.card, alignment=Qt.AlignCenter)
        outer.addStretch()

    def select_account(self, value: str) -> None:
        if value and value != "Сохранённые Аккаунты Freskmid":
            self.username_input.setText(value)

    def login(self) -> None:
        username = self.username_input.text().strip()
        if not username:
            QMessageBox.warning(self, "Аккаунт", "Введите никнейм.")
            return
        ok, message = self.account_manager.authenticate(username, self.password_input.text())
        if not ok:
            QMessageBox.warning(self, "Вход", message)
            return
        if self.remember_check.isChecked():
            self.account_manager.remember(username)
        self.main_window.show_main_screen(username)

    def register(self) -> None:
        username = self.username_input.text().strip()
        ok, message = self.account_manager.register(username, self.password_input.text())
        if not ok:
            QMessageBox.warning(self, "Регистрация", message)
            return
        QMessageBox.information(self, "VVittox Works Accounts", message)
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
        self.password_input.setStyleSheet(self.main_window.input_style())
        self.saved_accounts.setStyleSheet(self.main_window.combo_style())
        self.remember_check.setStyleSheet(
            f"color: {theme['muted']}; font-size: 13px; border: none;"
        )
        self.login_button.refresh_style()
        self.register_button.refresh_style()


class Skin3DWidget(QWidget):
    def __init__(self, theme_manager: ThemeManager) -> None:
        super().__init__()
        self.theme_manager = theme_manager
        self.skin = QPixmap()
        self.yaw = -18.0
        self.zoom = 1.0
        self.dragging = False
        self.last_mouse = QPoint()
        self.setMinimumSize(340, 430)
        self.setCursor(Qt.OpenHandCursor)

    def set_skin(self, pixmap: QPixmap) -> None:
        self.skin = pixmap
        self.update()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.dragging = True
            self.last_mouse = event.pos()
            self.setCursor(Qt.ClosedHandCursor)

    def mouseMoveEvent(self, event) -> None:
        if self.dragging:
            self.yaw += (event.pos().x() - self.last_mouse.x()) * 0.8
            self.last_mouse = event.pos()
            self.update()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.dragging = False
            self.setCursor(Qt.OpenHandCursor)

    def wheelEvent(self, event) -> None:
        self.zoom = max(0.72, min(1.35, self.zoom + (0.08 if event.angleDelta().y() > 0 else -0.08)))
        self.update()

    def _color(self, x: int, y: int, width: int, height: int, fallback: str) -> QColor:
        if self.skin.isNull() or self.skin.width() < 64 or self.skin.height() < 32:
            return QColor(fallback)
        image = self.skin.toImage()
        red = green = blue = count = 0
        for px in range(x, min(x + width, image.width())):
            for py in range(y, min(y + height, image.height())):
                color = QColor(image.pixel(px, py))
                if color.alpha() == 0:
                    continue
                red += color.red()
                green += color.green()
                blue += color.blue()
                count += 1
        return QColor(red // count, green // count, blue // count) if count else QColor(fallback)

    def _project(self, point: Tuple[float, float, float], scale: float, center_x: float, ground: float) -> QPoint:
        x, y, z = point
        angle = math.radians(self.yaw)
        rotated_x = x * math.cos(angle) - z * math.sin(angle)
        rotated_z = x * math.sin(angle) + z * math.cos(angle)
        return QPoint(int(center_x + rotated_x * scale), int(ground - y * scale + rotated_z * scale * 0.28))

    def _cuboid(self, painter: QPainter, center: Tuple[float, float, float], size: Tuple[float, float, float], color: QColor, scale: float, center_x: float, ground: float) -> None:
        cx, cy, cz = center
        width, height, depth = size
        vertices = [
            (cx - width / 2, cy - height / 2, cz - depth / 2),
            (cx + width / 2, cy - height / 2, cz - depth / 2),
            (cx + width / 2, cy + height / 2, cz - depth / 2),
            (cx - width / 2, cy + height / 2, cz - depth / 2),
            (cx - width / 2, cy - height / 2, cz + depth / 2),
            (cx + width / 2, cy - height / 2, cz + depth / 2),
            (cx + width / 2, cy + height / 2, cz + depth / 2),
            (cx - width / 2, cy + height / 2, cz + depth / 2),
        ]
        faces = [
            ([0, 1, 2, 3], 0.84), ([4, 5, 6, 7], 1.0),
            ([0, 4, 7, 3], 0.72), ([1, 5, 6, 2], 0.9),
            ([3, 2, 6, 7], 1.08), ([0, 1, 5, 4], 0.58),
        ]
        projected = [self._project(vertex, scale, center_x, ground) for vertex in vertices]
        ordered = sorted(faces, key=lambda face: sum(vertices[index][2] for index in face[0]) / 4)
        for indices, brightness in ordered:
            shade = QColor(
                min(255, int(color.red() * brightness)),
                min(255, int(color.green() * brightness)),
                min(255, int(color.blue() * brightness)),
            )
            painter.setBrush(shade)
            painter.setPen(QPen(QColor(0, 0, 0, 55), 1))
            painter.drawPolygon([projected[index] for index in indices])

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        theme = self.theme_manager.get_theme()
        painter.fillRect(self.rect(), QColor(theme["panel_alt"]))

        scale = min(self.width() / 8.5, self.height() / 8.8) * self.zoom
        center_x = self.width() / 2
        ground = self.height() - 32
        self._cuboid(painter, (0, 6.8, 0), (2.25, 2.25, 2.25), self._color(8, 8, 8, 8, theme["primary"]), scale, center_x, ground)
        self._cuboid(painter, (0, 4.0, 0), (1.8, 2.5, 1.0), self._color(20, 20, 8, 12, theme["secondary"]), scale, center_x, ground)
        self._cuboid(painter, (-1.3, 4.0, 0), (0.55, 2.35, 0.8), self._color(44, 20, 4, 12, theme["primary"]), scale, center_x, ground)
        self._cuboid(painter, (1.3, 4.0, 0), (0.55, 2.35, 0.8), self._color(44, 20, 4, 12, theme["primary"]), scale, center_x, ground)
        self._cuboid(painter, (-0.48, 1.25, 0), (0.72, 2.5, 0.85), self._color(4, 20, 4, 12, theme["secondary"]), scale, center_x, ground)
        self._cuboid(painter, (0.48, 1.25, 0), (0.72, 2.5, 0.85), self._color(4, 20, 4, 12, theme["secondary"]), scale, center_x, ground)
        painter.setPen(QPen(QColor(theme["primary"]), 2))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -2, -2), 10, 10)
        painter.setPen(QColor(theme["muted"]))
        painter.setFont(QFont("Segoe UI", 10, QFont.Bold))
        painter.drawText(QRect(0, 8, self.width(), 20), Qt.AlignCenter, "ПРЕДПРОСМОТР СКИНА")


class ProfileScreen(FadeInWidget):
    def __init__(self, main_window: "MainWindow") -> None:
        super().__init__()
        self.main_window = main_window
        self.account_manager = main_window.login_screen.account_manager
        self.skin_path = ""
        self.init_ui()
        self.refresh_theme()

    def init_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(70, 35, 70, 35)
        root.setSpacing(16)

        header = QHBoxLayout()
        title = QLabel("Профиль")
        title.setObjectName("profileTitle")
        self.account_badge = QLabel("VVITTOX WORKS ACCOUNTS")
        self.account_badge.setObjectName("accountBadge")
        self.header_face = QLabel()
        self.header_face.setObjectName("profileHeaderFace")
        self.header_face.setFixedSize(32, 32)
        self.header_face.setAlignment(Qt.AlignCenter)
        back = MinecraftButton("НАЗАД", self.main_window.theme_manager, "secondary")
        back.setFixedWidth(130)
        back.clicked.connect(lambda: self.main_window.show_main_screen(self.main_window.current_username))
        header.addWidget(title)
        header.addSpacing(14)
        header.addWidget(self.header_face)
        header.addWidget(self.account_badge)
        header.addStretch()
        header.addWidget(back)
        self.back_button = back

        body = QHBoxLayout()
        body.setSpacing(18)
        self.avatar_card = QFrame()
        self.avatar_card.setObjectName("profileAvatarCard")
        avatar_layout = QVBoxLayout(self.avatar_card)
        avatar_layout.setContentsMargins(22, 22, 22, 22)
        avatar_layout.setSpacing(12)
        self.avatar = Skin3DWidget(self.main_window.theme_manager)
        self.avatar.setToolTip("Зажмите левую кнопку мыши и двигайте, чтобы повернуть персонажа. Колесо меняет масштаб.")
        self.skin_button = MinecraftButton("Выбрать скин", self.main_window.theme_manager, "secondary")
        self.skin_button.clicked.connect(self.choose_skin)
        avatar_layout.addWidget(self.avatar, alignment=Qt.AlignCenter)
        avatar_layout.addWidget(self.skin_button)

        self.form_card = QFrame()
        self.form_card.setObjectName("profileFormCard")
        form = QVBoxLayout(self.form_card)
        form.setContentsMargins(24, 22, 24, 22)
        form.setSpacing(10)
        self.profile_hint = QLabel("Локальный профиль лаунчера. Пароль хранится только в виде хеша.")
        self.profile_hint.setObjectName("profileHint")
        self.profile_username = QLineEdit()
        self.profile_username.setPlaceholderText("Никнейм")
        self.profile_password = QLineEdit()
        self.profile_password.setPlaceholderText("Новый пароль (необязательно)")
        self.profile_password.setEchoMode(QLineEdit.Password)
        self.save_button = MinecraftButton("Сохранить профиль", self.main_window.theme_manager, "primary")
        self.save_button.clicked.connect(self.save_profile)
        form.addWidget(QLabel("Имя аккаунта"))
        form.addWidget(self.profile_username)
        form.addWidget(QLabel("Изменить пароль"))
        form.addWidget(self.profile_password)
        form.addSpacing(8)
        form.addWidget(self.profile_hint)
        form.addStretch()
        form.addWidget(self.save_button)
        body.addWidget(self.avatar_card)
        body.addWidget(self.form_card, 1)

        root.addLayout(header)
        root.addLayout(body, 1)

    def load_profile(self, username: str) -> None:
        profile = self.account_manager.get_profile(username)
        self.profile_username.setText(str(profile.get("username", username)))
        self.profile_password.clear()
        self.skin_path = str(profile.get("skin", ""))
        self.update_avatar()

    def choose_skin(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Выберите скин или изображение профиля", "", "Изображения (*.png *.jpg *.jpeg)"
        )
        if path:
            self.skin_path = path
            self.update_avatar()

    def update_avatar(self) -> None:
        pixmap = QPixmap(self.skin_path) if self.skin_path else QPixmap()
        self.avatar.set_skin(pixmap)
        if pixmap.isNull():
            self.header_face.clear()
            self.header_face.setText("?")
            return
        face = pixmap.copy(8, 8, 8, 8)
        self.header_face.setText("")
        self.header_face.setPixmap(face.scaled(28, 28, Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def save_profile(self) -> None:
        old_username = self.main_window.current_username
        ok, result = self.account_manager.update_profile(
            old_username,
            self.profile_username.text(),
            self.profile_password.text(),
            self.skin_path,
        )
        if not ok:
            QMessageBox.warning(self, "Профиль", result)
            return
        self.main_window.current_username = result
        self.main_window.main_screen.set_username(result)
        self.profile_password.clear()
        QMessageBox.information(self, "Профиль", "Профиль VVittox Works Accounts сохранён.")

    def refresh_theme(self) -> None:
        theme = self.main_window.theme_manager.get_theme()
        self.setStyleSheet(
            f"""
            QLabel#profileTitle {{ color: {theme['text']}; font-size: 28px; font-weight: 900; }}
            QLabel#accountBadge {{ color: {theme['success']}; font-size: 10px; font-weight: 900; letter-spacing: 0.08em; }}
            QLabel#profileHint {{ color: {theme['muted']}; font-size: 12px; }}
            QLabel#profileHeaderFace {{ background: {theme['panel_alt']}; color: {theme['muted']}; border: 1px solid {theme['primary']}; border-radius: 5px; font-weight: 900; }}
            QFrame#profileAvatarCard, QFrame#profileFormCard {{
                background: {hex_to_rgba(theme['panel'], 235)};
                border: 1px solid {hex_to_rgba(theme['primary'], 62)};
                border-radius: 10px;
            }}
            QLabel {{ color: {theme['muted']}; }}
            """
        )
        self.profile_username.setStyleSheet(self.main_window.input_style())
        self.profile_password.setStyleSheet(self.main_window.input_style())
        self.back_button.refresh_style()
        self.skin_button.refresh_style()
        self.save_button.refresh_style()


class QuickInfoCard(QFrame):
    def __init__(self, title: str, value: str, accent: str = "primary") -> None:
        super().__init__()
        self.title = title
        self.value = value
        self.accent = accent
        self.setMinimumHeight(92)
        self.setObjectName("quickInfoCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(6)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("quickCardTitle")
        self.value_label = QLabel(value)
        self.value_label.setObjectName("quickCardValue")
        self.value_label.setWordWrap(True)

        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)

    def set_value(self, value: str) -> None:
        self.value_label.setText(value)

    def refresh_theme(self, theme: Dict[str, str]) -> None:
        accent = theme[self.accent] if self.accent in theme else theme["primary"]
        self.setStyleSheet(
            f"""
            QFrame#quickInfoCard {{
                background: {hex_to_rgba(theme['panel_alt'], 245)};
                border: 1px solid {hex_to_rgba(accent, 75)};
                border-radius: 9px;
            }}
            QFrame#quickInfoCard:hover {{
                border-color: {accent};
                background: {hex_to_rgba(theme['panel_alt'], 255)};
            }}
            QLabel#quickCardTitle {{
                color: {theme['muted']};
                font-size: 10px;
                font-weight: 800;
                letter-spacing: 0.08em;
                text-transform: uppercase;
                border: none;
            }}
            QLabel#quickCardValue {{
                color: {theme['text']};
                font-size: 14px;
                font-weight: 800;
                border: none;
            }}
            """
        )


class ModCard(QFrame):
    def __init__(self, name: str, details: str, enabled: bool = True) -> None:
        super().__init__()
        self.name = name
        self.enabled = enabled
        self.setObjectName("modCard")
        self.setMinimumHeight(76)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 12, 10)
        layout.setSpacing(12)

        left = QVBoxLayout()
        title = QLabel(name)
        title.setObjectName("modTitle")
        subtitle = QLabel(details)
        subtitle.setObjectName("modSubtitle")
        left.addWidget(title)
        left.addWidget(subtitle)

        self.state = QLabel("Включён" if enabled else "Отключён")
        self.state.setObjectName("modState")

        self.toggle_button = QPushButton("Отключить" if enabled else "Включить")
        self.toggle_button.setObjectName("modToggle")
        self.remove_button = QPushButton("Удалить")
        self.remove_button.setObjectName("modRemove")

        actions = QHBoxLayout()
        actions.addWidget(self.state)
        actions.addWidget(self.toggle_button)
        actions.addWidget(self.remove_button)

        layout.addLayout(left)
        layout.addLayout(actions)

    def refresh_theme(self, theme: Dict[str, str]) -> None:
        self.setStyleSheet(
            f"""
            QFrame#modCard {{
                background: {hex_to_rgba(theme['panel_alt'], 245)};
                border: 1px solid {hex_to_rgba(theme['primary'], 70)};
                border-radius: 10px;
            }}
            QLabel#modTitle {{
                color: {theme['text']};
                font-size: 13px;
                font-weight: 800;
                border: none;
            }}
            QLabel#modSubtitle {{
                color: {theme['muted']};
                font-size: 11px;
                border: none;
            }}
            QLabel#modState {{
                color: {theme['success']};
                font-size: 10px;
                font-weight: 700;
                border: none;
            }}
            QPushButton#modToggle {{
                background: {hex_to_rgba(theme['primary'], 22)};
                color: {theme['text']};
                border: 1px solid {hex_to_rgba(theme['primary'], 70)};
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 10px;
                font-weight: 700;
            }}
            QPushButton#modRemove {{
                background: {hex_to_rgba('#ff6a55', 18)};
                color: {theme['text']};
                border: 1px solid rgba(255,106,85,120);
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 10px;
                font-weight: 700;
            }}
            """
        )


class CurseForgeDownloadThread(QThread):
    finished_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)

    def __init__(self, mod_id: str, version: str, loader: str, source: str = "curseforge") -> None:
        super().__init__()
        self.mod_id = mod_id
        self.version = version
        self.loader = loader
        self.source = source

    def run(self) -> None:
        try:
            if self.source == "modrinth":
                self._download_modrinth()
                return
            params = {"pageSize": 1, "sortField": 2, "sortOrder": "desc"}
            if self.version:
                params["gameVersion"] = self.version
            if self.loader and self.loader != "Авто":
                params["modLoaderType"] = {"Forge": 1, "Fabric": 4, "Quilt": 5}.get(self.loader, 0)
            request = urllib.request.Request(
                f"{CURSEFORGE_API_URL}/mods/{self.mod_id}/files?{urllib.parse.urlencode(params)}",
                headers={"x-api-key": CURSEFORGE_API_KEY, "Accept": "application/json"},
            )
            with urllib.request.urlopen(request, timeout=25) as response:
                files = json.loads(response.read().decode("utf-8")).get("data", [])
            if not files:
                raise RuntimeError("Для выбранной версии подходящий файл не найден")
            file_info = files[0]
            download_url = file_info.get("downloadUrl")
            if not download_url:
                raise RuntimeError("CurseForge не предоставил прямую ссылку на файл")

            mods_dir = ensure_mods_folder()
            filename = str(file_info.get("fileName") or f"curseforge_{self.mod_id}.jar")
            target = mods_dir / Path(filename).name
            temporary = target.with_suffix(target.suffix + ".download")
            download_request = urllib.request.Request(
                download_url, headers={"User-Agent": "FRESKMID Launcher"}
            )
            with urllib.request.urlopen(download_request, timeout=60) as response, open(temporary, "wb") as output:
                shutil.copyfileobj(response, output)
            os.replace(temporary, target)
            self.finished_signal.emit(str(target))
        except Exception as exc:
            self.error_signal.emit(str(exc))

    def _download_modrinth(self) -> None:
        params = {"game_versions": json.dumps([self.version])} if self.version else {}
        request = urllib.request.Request(
            f"https://api.modrinth.com/v2/project/{urllib.parse.quote(self.mod_id)}/version?{urllib.parse.urlencode(params)}",
            headers={"User-Agent": "FRESKMID Launcher"},
        )
        with urllib.request.urlopen(request, timeout=25) as response:
            versions = json.loads(response.read().decode("utf-8"))
        if not versions or not versions[0].get("files"):
            raise RuntimeError("Для выбранной версии совместимый файл не найден")
        file_info = next((item for item in versions[0]["files"] if item.get("primary")), versions[0]["files"][0])
        download_url = file_info.get("url")
        filename = Path(str(file_info.get("filename") or f"modrinth_{self.mod_id}.jar")).name
        target = ensure_mods_folder() / filename
        temporary = target.with_suffix(target.suffix + ".download")
        with urllib.request.urlopen(download_url, timeout=60) as response, open(temporary, "wb") as output:
            shutil.copyfileobj(response, output)
        os.replace(temporary, target)
        self.finished_signal.emit(str(target))


class ModCatalogCard(QFrame):
    download_requested = pyqtSignal(str, str)

    def __init__(self, mod: Dict[str, Any], theme_manager: ThemeManager) -> None:
        super().__init__()
        self.mod = mod
        self.theme_manager = theme_manager
        self.setObjectName("modCatalogCard")
        self.setMinimumHeight(96)
        self.setCursor(Qt.PointingHandCursor)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(12)

        self.icon = QLabel()
        self.icon.setFixedSize(68, 68)
        self.icon.setAlignment(Qt.AlignCenter)
        self.icon.setObjectName("modCatalogIcon")
        layout.addWidget(self.icon)

        info = QVBoxLayout()
        info.setSpacing(3)
        self.title = QLabel(str(mod.get("name", "Без названия")))
        self.title.setObjectName("modCatalogTitle")
        self.summary = QLabel(str(mod.get("summary", "Описание отсутствует")))
        self.summary.setObjectName("modCatalogSummary")
        self.summary.setWordWrap(True)
        author = str(mod.get("author", "CurseForge"))
        downloads = int(mod.get("downloads", 0))
        self.meta = QLabel(f"{author}  •  {downloads:,} загрузок".replace(",", " "))
        self.meta.setObjectName("modCatalogMeta")
        info.addWidget(self.title)
        info.addWidget(self.summary)
        info.addWidget(self.meta)
        layout.addLayout(info, 1)

        self.download_button = QPushButton("Скачать")
        self.download_button.setObjectName("catalogDownloadButton")
        self.download_button.setCursor(Qt.PointingHandCursor)
        self.download_button.clicked.connect(
            lambda: self.download_requested.emit(str(mod["id"]), str(mod.get("source", "curseforge")))
        )
        layout.addWidget(self.download_button)
        self.load_icon()
        self.refresh_theme()

    def load_icon(self) -> None:
        icon_url = str(self.mod.get("icon", ""))
        if not icon_url:
            return
        try:
            request = urllib.request.Request(icon_url, headers={"User-Agent": "FRESKMID Launcher"})
            with urllib.request.urlopen(request, timeout=8) as response:
                pixmap = QPixmap()
                pixmap.loadFromData(response.read())
            if not pixmap.isNull():
                self.icon.setPixmap(pixmap.scaled(68, 68, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        except Exception:
            pass

    def refresh_theme(self) -> None:
        theme = self.theme_manager.get_theme()
        self.setStyleSheet(
            f"""
            QFrame#modCatalogCard {{
                background: {hex_to_rgba(theme['panel_alt'], 245)};
                border: 1px solid {hex_to_rgba(theme['primary'], 58)};
                border-radius: 9px;
            }}
            QFrame#modCatalogCard:hover {{
                border-color: {theme['primary']};
                background: {hex_to_rgba(theme['panel_alt'], 255)};
            }}
            QLabel#modCatalogIcon {{
                background: {theme['panel']};
                color: {theme['muted']};
                border: 1px solid {hex_to_rgba(theme['primary'], 45)};
                border-radius: 7px;
            }}
            QLabel#modCatalogTitle {{ color: {theme['text']}; font-size: 14px; font-weight: 800; border: none; }}
            QLabel#modCatalogSummary {{ color: {theme['muted']}; font-size: 11px; border: none; }}
            QLabel#modCatalogMeta {{ color: {theme['success']}; font-size: 10px; font-weight: 700; border: none; }}
            QPushButton#catalogDownloadButton {{
                background: {theme['primary']}; color: #15120c; border: none;
                border-radius: 6px; padding: 9px 13px; font-weight: 800;
            }}
            QPushButton#catalogDownloadButton:hover {{ background: {QColor(theme['primary']).lighter(115).name()}; }}
            QPushButton#catalogDownloadButton:pressed {{ padding-top: 11px; padding-bottom: 7px; }}
            """
        )


class SocialButton(QPushButton):
    def __init__(self, label: str, url: str, theme_manager: ThemeManager) -> None:
        super().__init__(label)
        self.url = url
        self.theme_manager = theme_manager
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(url)
        self.setMinimumHeight(34)
        self.refresh_theme()
        self.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(self.url)))

    def refresh_theme(self) -> None:
        theme = self.theme_manager.get_theme()
        self.setStyleSheet(
            f"""
            QPushButton {{
                background: {hex_to_rgba(theme['panel_alt'], 220)};
                color: {theme['text']};
                border: 1px solid {hex_to_rgba(theme['primary'], 45)};
                border-radius: 6px;
                padding: 6px 8px;
                font-size: 11px;
                font-weight: 800;
                text-align: left;
            }}
            QPushButton:hover {{
                background: {hex_to_rgba(theme['primary'], 35)};
                border-color: {theme['primary']};
                padding-left: 11px;
            }}
            QPushButton:pressed {{
                background: {theme['secondary']};
                color: {theme['text']};
                padding-left: 13px;
                padding-top: 8px;
                padding-bottom: 4px;
            }}
            """
        )


class MainScreen(FadeInWidget):
    def __init__(self, main_window: "MainWindow") -> None:
        super().__init__()
        self.main_window = main_window
        self.quick_cards: List[QuickInfoCard] = []
        self.version_shortcuts: List[QPushButton] = []
        self.init_ui()
        self.refresh_theme()

    def init_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 22)
        root.setSpacing(22)

        self.sidebar = QFrame()
        self.sidebar.setFixedWidth(248)
        side = QVBoxLayout(self.sidebar)
        side.setContentsMargins(17, 22, 17, 20)
        side.setSpacing(9)

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
        self.nav_profile = NavigationButton("Профиль", self.main_window.theme_manager)
        self.nav_mods = NavigationButton("Моды", self.main_window.theme_manager)
        self.nav_settings = NavigationButton("Настройки", self.main_window.theme_manager)
        self.nav_folder = NavigationButton("Папка игры", self.main_window.theme_manager)
        self.nav_logout = NavigationButton("Сменить аккаунт", self.main_window.theme_manager)

        self.nav_mods.clicked.connect(self.main_window.show_mods)
        self.nav_profile.clicked.connect(self.main_window.show_profile)
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

        self.socials_caption = QLabel("СОЦСЕТИ VVITTOX")
        self.socials_caption.setObjectName("caption")
        self.socials_layout = QVBoxLayout()
        self.socials_layout.setSpacing(5)
        self.social_buttons = [
            SocialButton("Сайт VVITTOX", "https://sites.google.com/view/vvittox/vvittox", self.main_window.theme_manager),
            SocialButton("Telegram", "https://t.me/+RZWsezO061A2M2Iy", self.main_window.theme_manager),
            SocialButton("Discord", "https://discord.gg/XUjfd7uucj", self.main_window.theme_manager),
            SocialButton("GitHub / Freskmid-Launcher", "https://github.com/VVittox/Freskmid-Launcher", self.main_window.theme_manager),
        ]
        for button in self.social_buttons:
            self.socials_layout.addWidget(button)

        side.addWidget(logo)
        side.addSpacing(19)
        side.addWidget(self.nav_home)
        side.addWidget(self.nav_profile)
        side.addWidget(self.nav_mods)
        side.addWidget(self.nav_settings)
        side.addWidget(self.nav_folder)
        side.addStretch()
        side.addWidget(self.profile_card)
        side.addSpacing(10)
        side.addWidget(self.socials_caption)
        side.addLayout(self.socials_layout)
        side.addWidget(self.nav_logout)

        content = QVBoxLayout()
        content.setSpacing(16)

        header_layout = QHBoxLayout()
        title_box = QVBoxLayout()
        self.page_title = QLabel("Главная")
        self.page_title.setObjectName("pageTitle")
        self.page_title.setMinimumHeight(38)
        self.welcome_label = QLabel("Добро пожаловать")
        self.welcome_label.setObjectName("muted")
        self.header_skin_face = QLabel("?")
        self.header_skin_face.setObjectName("mainSkinFace")
        self.header_skin_face.setAlignment(Qt.AlignCenter)
        self.header_skin_face.setFixedSize(42, 42)
        title_box.addWidget(self.page_title)
        title_box.addWidget(self.welcome_label)
        header_layout.addLayout(title_box)
        header_layout.addStretch()
        header_layout.addWidget(self.header_skin_face)

        self.server_banner = PromoBanner(self.main_window)
        self.server_banner.clicked.connect(self.main_window.launch_game)

        self.launch_card = QFrame()
        self.launch_card.setObjectName("launchCard")
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
            "Один рекламный баннер для всех ваших проектов. Выбирайте версию, "
            "вводите никнейм и запускайте Minecraft без привязки к одному серверу."
        )
        hint.setWordWrap(True)
        hint.setObjectName("hint")

        self.quick_stats = QFrame()
        quick_layout = QHBoxLayout(self.quick_stats)
        quick_layout.setContentsMargins(0, 0, 0, 0)
        quick_layout.setSpacing(12)

        self.version_info_card = QuickInfoCard("Версия", "Выберите сборку", "primary")
        self.ram_info_card = QuickInfoCard("RAM", f"{self.main_window.settings.get('ram', 4)} GB", "success")
        self.folder_info_card = QuickInfoCard("Папка", "FRESKMID", "secondary")
        self.quick_cards = [self.version_info_card, self.ram_info_card, self.folder_info_card]
        for card in self.quick_cards:
            quick_layout.addWidget(card)

        self.version_shortcuts_frame = QFrame()
        shortcut_layout = QHBoxLayout(self.version_shortcuts_frame)
        shortcut_layout.setContentsMargins(0, 0, 0, 0)
        shortcut_layout.setSpacing(8)
        self.version_shortcuts = []

        for version_id in ["1.20.1", "1.19.2", "1.18.2", "1.16.5"]:
            button = QPushButton(version_id)
            button.setObjectName("versionShortcut")
            button.setCursor(Qt.PointingHandCursor)
            button.clicked.connect(lambda checked=False, value=version_id: self.select_version(value))
            shortcut_layout.addWidget(button)
            self.version_shortcuts.append(button)

        content.addLayout(header_layout)
        content.addWidget(self.server_banner)
        content.addWidget(self.quick_stats)
        content.addWidget(self.version_shortcuts_frame)
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
            raw_versions = get_version_list()
            seen = set()
            for entry in raw_versions:
                version_id = str(entry.get("id", "")).strip()
                if not version_id or version_id in seen:
                    continue
                seen.add(version_id)
                ids.append(version_id)
        except Exception:
            ids = ["1.20.1", "1.19.2", "1.18.2"]

        if not ids:
            ids = ["1.20.1", "1.19.2", "1.18.2"]

        for version_id in ids:
            lower = version_id.lower()
            if "forge" in lower:
                label = f"Forge {version_id}"
            elif "fabric" in lower:
                label = f"Fabric {version_id}"
            elif "quilt" in lower:
                label = f"Quilt {version_id}"
            else:
                label = f"Vanilla {version_id}"
            self.version_select.addItem(label, version_id)

        if self.version_select.count():
            self.version_select.setCurrentIndex(0)

    def open_game_folder(self) -> None:
        Path(minecraft_directory).mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(minecraft_directory))

    def select_version(self, version_id: str) -> None:
        index = self.version_select.findData(version_id)
        if index >= 0:
            self.version_select.setCurrentIndex(index)
        self.version_info_card.set_value(version_id)

    def set_username(self, username: str) -> None:
        self.username.setText(username)
        self.profile_name.setText(username or "Гость")
        self.welcome_label.setText(
            f"Добро пожаловать, {username}" if username else "Выберите версию и начните игру"
        )
        self.update_skin_face(username)

    def update_skin_face(self, username: str) -> None:
        profile = self.main_window.login_screen.account_manager.get_profile(username) if username else {}
        pixmap = QPixmap(str(profile.get("skin", "")))
        if pixmap.isNull():
            self.header_skin_face.setPixmap(QPixmap())
            self.header_skin_face.setText("?")
            return
        face = pixmap.copy(8, 8, 8, 8)
        self.header_skin_face.setText("")
        self.header_skin_face.setPixmap(face.scaled(36, 36, Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def refresh_runtime_cards(self) -> None:
        selected = self.version_select.currentData() or self.version_select.currentText()
        self.version_info_card.set_value(str(selected or "Выберите сборку"))
        self.ram_info_card.set_value(f"{int(self.main_window.settings.get('ram', 4))} GB")
        self.folder_info_card.set_value(Path(minecraft_directory).name)

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
                border: 1px solid {hex_to_rgba(theme['primary'], 62)};
                border-radius: 9px;
            }}
        """
        self.sidebar.setStyleSheet(
            panel_style
            + f"""
            QLabel {{ border: none; color: {theme['text']}; }}
            QFrame {{ background: {hex_to_rgba(theme['panel'], 242)}; border-radius: 9px; }}
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
            f"color: {theme['text']}; font-size: 30px; font-weight: 900; letter-spacing: 0px;"
        )
        self.welcome_label.setStyleSheet(
            f"color: {theme['muted']}; font-size: 13px;"
        )
        self.header_skin_face.setStyleSheet(
            f"background: {theme['panel_alt']}; color: {theme['muted']}; "
            f"border: 1px solid {theme['primary']}; border-radius: 7px; font-weight: 900;"
        )
        self.start_progress_label.setStyleSheet(
            f"color: {theme['text']}; font-size: 12px; font-weight: 700; border: none;"
        )
        self.start_progress.setStyleSheet(self.main_window.progress_style())
        self.version_select.setStyleSheet(self.main_window.combo_style())
        self.username.setStyleSheet(self.main_window.input_style())
        self.start_button.refresh_style()
        self.folder_button.refresh_style()
        for card in self.quick_cards:
            card.refresh_theme(theme)
        self.quick_stats.setStyleSheet(
            f"""
            QFrame {{
                background: transparent;
                border: none;
            }}
            """
        )
        self.version_shortcuts_frame.setStyleSheet(
            f"""
            QFrame {{
                background: transparent;
                border: none;
            }}
            QPushButton#versionShortcut {{
                background: {hex_to_rgba(theme['panel_alt'], 210)};
                color: {theme['text']};
                border: 1px solid {hex_to_rgba(theme['primary'], 60)};
                border-radius: 6px;
                padding: 7px 10px;
                font-size: 11px;
                font-weight: 800;
            }}
            QPushButton#versionShortcut:hover {{
                background: {hex_to_rgba(theme['primary'], 24)};
                border-color: {theme['primary']};
            }}
            """
        )
        for button in self.version_shortcuts:
            button.setStyleSheet(
                f"""
                QPushButton {{
                    background: {hex_to_rgba(theme['panel_alt'], 210)};
                    color: {theme['text']};
                    border: 1px solid {hex_to_rgba(theme['primary'], 60)};
                    border-radius: 6px;
                    padding: 7px 10px;
                    font-size: 11px;
                    font-weight: 800;
                }}
                QPushButton:hover {{
                    background: {hex_to_rgba(theme['primary'], 24)};
                    border-color: {theme['primary']};
                }}
                """
            )
        for button in (self.nav_home, self.nav_profile, self.nav_mods, self.nav_settings, self.nav_folder, self.nav_logout):
            button.refresh_style()
        for button in self.social_buttons:
            button.refresh_theme()
        self.server_banner.update()
        self.refresh_runtime_cards()


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

        misc_group = QGroupBox("Дополнительно")
        misc_layout = QVBoxLayout(misc_group)
        self.keep_launcher_open = QCheckBox("Оставлять лаунчер открытым после запуска")
        self.keep_launcher_open.setChecked(bool(self.main_window.settings.get("keep_launcher_open", True)))
        self.use_java_args = QCheckBox("Пользовательские аргументы Java")
        self.use_java_args.setChecked(bool(self.main_window.settings.get("use_java_args", False)))
        self.java_args_field = QLineEdit()
        self.java_args_field.setPlaceholderText("Например: -XX:+UseG1GC -Dfile.encoding=UTF-8")
        self.java_args_field.setText(str(self.main_window.settings.get("java_args", "")))
        self.java_args_field.setVisible(self.use_java_args.isChecked())
        self.use_java_args.toggled.connect(self.java_args_field.setVisible)
        misc_layout.addWidget(self.keep_launcher_open)
        misc_layout.addWidget(self.use_java_args)
        misc_layout.addWidget(self.java_args_field)

        general_layout.addWidget(theme_group)
        general_layout.addWidget(performance_group)
        general_layout.addWidget(misc_group)
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
        return {
            "ram": self.ram_slider.value(),
            "keep_launcher_open": self.keep_launcher_open.isChecked(),
            "use_java_args": self.use_java_args.isChecked(),
            "java_args": self.java_args_field.text().strip(),
        }

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
        self.java_args_field.setStyleSheet(self.main_window.input_style())
        self.ram_slider.setStyleSheet(self.main_window.slider_style())
        self.about_text.setStyleSheet(
            f"background: {theme['panel_alt']}; color: {theme['text']}; border: none; padding: 14px;"
        )
        self.back_button.refresh_style()


class ModsScreen(FadeInWidget):
    def __init__(self, main_window: "MainWindow") -> None:
        super().__init__()
        self.main_window = main_window
        self.mod_cards: List[ModCard] = []
        self.init_ui()
        self.refresh_theme()

    def init_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(70, 35, 70, 35)
        root.setSpacing(14)

        header = QHBoxLayout()
        title = QLabel("Моды")
        title.setObjectName("modsTitle")
        back = MinecraftButton("НАЗАД", self.main_window.theme_manager, "secondary")
        back.setFixedWidth(130)
        back.clicked.connect(lambda: self.main_window.show_main_screen(self.main_window.current_username))
        header.addWidget(title)
        header.addStretch()
        header.addWidget(back)
        self.back_button = back

        controls = QHBoxLayout()
        self.loader_combo = QComboBox()
        self.loader_combo.addItems(["Vanilla", "Forge", "Fabric", "Quilt", "Авто"])
        self.loader_combo.setCurrentText("Vanilla")

        self.add_mod_button = MinecraftButton("Добавить мод", self.main_window.theme_manager, "primary")
        self.add_mod_button.clicked.connect(self.add_mod)
        self.mods_folder_button = MinecraftButton("Папка модов", self.main_window.theme_manager, "secondary")
        self.mods_folder_button.clicked.connect(self.main_window.open_mods_folder)
        self.download_button = MinecraftButton("Скачать из URL", self.main_window.theme_manager, "secondary")
        self.download_button.clicked.connect(self.download_mod)

        controls.addWidget(QLabel("Загрузчик: "))
        controls.addWidget(self.loader_combo)
        controls.addStretch()
        controls.addWidget(self.mods_folder_button)
        controls.addWidget(self.add_mod_button)
        controls.addWidget(self.download_button)

        self.url_field = QLineEdit()
        self.url_field.setPlaceholderText("Прямая ссылка на мод / CurseForge .jar")

        installed_title = QLabel("Установленные моды")
        installed_title.setObjectName("installedModsTitle")

        self.mods_scroll = QScrollArea()
        self.mods_scroll.setWidgetResizable(True)
        self.mods_scroll.setFrameShape(QFrame.NoFrame)
        self.mods_scroll_content = QWidget()
        self.mods_layout = QVBoxLayout(self.mods_scroll_content)
        self.mods_layout.setSpacing(10)
        self.mods_layout.setContentsMargins(0, 0, 0, 0)
        self.mods_scroll.setWidget(self.mods_scroll_content)

        root.addLayout(header)
        root.addLayout(controls)
        root.addWidget(self.url_field)
        root.addWidget(installed_title)
        root.addWidget(self.mods_scroll)

        self.refresh_mods_list()

    def refresh_mods_list(self) -> None:
        self.mod_cards = []
        for widget in list(self.mods_layout.children()):
            if isinstance(widget, QWidget):
                widget.deleteLater()

        mods_dir = ensure_mods_folder()
        mod_files = []
        for path in sorted(mods_dir.iterdir()):
            is_mod = path.suffix.lower() in {".jar", ".zip"}
            is_disabled_mod = path.name.lower().endswith((".jar.disabled", ".zip.disabled"))
            if path.is_file() and (is_mod or is_disabled_mod):
                mod_files.append(path)

        if not mod_files:
            empty = QLabel("Папка модов пуста. Добавьте .jar или .zip файл.")
            empty.setObjectName("modEmptyLabel")
            self.mods_layout.addWidget(empty)
        else:
            for path in mod_files:
                extension = ".jar" if ".jar" in path.name.lower() else ".zip"
                enabled = not path.name.lower().endswith(".disabled")
                details = f"{extension.upper().lstrip('.')} • {path.stat().st_size // 1024} KB"
                card = ModCard(path.name, details, enabled)
                card.refresh_theme(self.main_window.theme_manager.get_theme())
                card.toggle_button.clicked.connect(lambda checked=False, p=path: self.toggle_mod(p))
                card.remove_button.clicked.connect(lambda checked=False, p=path: self.remove_mod(p))
                self.mod_cards.append(card)
                self.mods_layout.addWidget(card)

    def add_mod(self) -> None:
        mods_dir = ensure_mods_folder()
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите мод",
            str(mods_dir),
            "Minecraft mods (*.jar *.zip);;Все файлы (*.*)",
        )
        if not file_name:
            return
        target = Path(file_name)
        try:
            shutil.copy2(target, mods_dir / target.name)
            self.refresh_mods_list()
            QMessageBox.information(self, "Мод", f"Файл добавлен: {mods_dir / target.name}")
        except OSError as exc:
            QMessageBox.critical(self, "Ошибка", f"Не удалось добавить мод:\n{exc}")

    def toggle_mod(self, path: Path) -> None:
        try:
            if path.name.endswith(".disabled"):
                new_path = path.with_name(path.name.replace(".disabled", ""))
                path.rename(new_path)
            else:
                new_path = path.with_name(path.name + ".disabled")
                path.rename(new_path)
            self.refresh_mods_list()
        except OSError as exc:
            QMessageBox.critical(self, "Ошибка", f"Не удалось переключить мод:\n{exc}")

    def remove_mod(self, path: Path) -> None:
        try:
            path.unlink()
            self.refresh_mods_list()
        except OSError as exc:
            QMessageBox.critical(self, "Ошибка", f"Не удалось удалить мод:\n{exc}")

    def download_mod(self) -> None:
        url = self.url_field.text().strip()
        if not url:
            QMessageBox.warning(self, "Ссылка", "Введите ссылку на mod или .jar файл.")
            return
        mods_dir = ensure_mods_folder()
        try:
            parsed = urllib.parse.urlparse(url)
            filename = os.path.basename(parsed.path) or "downloaded_mod.jar"
            if not filename.lower().endswith((".jar", ".zip")):
                filename += ".jar"
            target = mods_dir / filename
            with urllib.request.urlopen(url, timeout=30) as response, open(target, "wb") as out:
                shutil.copyfileobj(response, out)
            self.refresh_mods_list()
            QMessageBox.information(self, "Мод", f"Загружено в папку модов:\n{target}")
        except Exception as exc:
            QMessageBox.critical(self, "Ошибка загрузки", f"Не удалось скачать мод:\n{exc}")

    def refresh_theme(self) -> None:
        theme = self.main_window.theme_manager.get_theme()
        self.setStyleSheet(
            f"""
            QLabel#modsTitle {{
                color: {theme['text']};
                font-size: 28px;
                font-weight: 900;
            }}
            QLabel#catalogTitle, QLabel#installedModsTitle {{
                color: {theme['text']};
                font-size: 16px;
                font-weight: 900;
                padding-top: 4px;
            }}
            QLabel#catalogStatus {{
                color: {theme['muted']};
                font-size: 11px;
                padding: 2px 0;
            }}
            QLabel#modEmptyLabel {{
                color: {theme['muted']};
                font-size: 13px;
                padding: 14px;
                border: 1px dashed {hex_to_rgba(theme['primary'], 60)};
                border-radius: 8px;
            }}
            QComboBox {{
                background: {theme['panel_alt']};
                color: {theme['text']};
                border: 1px solid {hex_to_rgba(theme['primary'], 55)};
                border-radius: 5px;
                padding: 8px 12px;
                font-size: 13px;
            }}
            QLineEdit {{
                background: {theme['panel_alt']};
                color: {theme['text']};
                border: 1px solid {hex_to_rgba(theme['primary'], 55)};
                border-radius: 5px;
                padding: 9px 12px;
                font-size: 13px;
            }}
            QScrollArea {{ background: transparent; border: none; }}
            """
        )
        self.back_button.refresh_style()
        self.add_mod_button.refresh_style()
        self.mods_folder_button.refresh_style()
        self.download_button.refresh_style()
        for card in self.mod_cards:
            card.refresh_theme(theme)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1280, 780)
        self.setMinimumSize(1080, 680)
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
        self.profile_screen = ProfileScreen(self)
        self.settings_screen = SettingsScreen(self)
        self.mods_screen = ModsScreen(self)
        self.stacked_widget.addWidget(self.login_screen)
        self.stacked_widget.addWidget(self.main_screen)
        self.stacked_widget.addWidget(self.profile_screen)
        self.stacked_widget.addWidget(self.settings_screen)
        self.stacked_widget.addWidget(self.mods_screen)
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
            self.settings["mods_enabled"] = bool(data.get("mods_enabled", True))
            self.settings["mod_loader"] = str(data.get("mod_loader", "Vanilla"))
            self.settings["curseforge_url"] = str(data.get("curseforge_url", ""))
            self.settings["keep_launcher_open"] = bool(data.get("keep_launcher_open", True))
            self.settings["use_java_args"] = bool(data.get("use_java_args", False))
            self.settings["java_args"] = str(data.get("java_args", ""))
        except (OSError, ValueError, TypeError):
            pass

    def save_settings(self) -> None:
        data = {
            "theme": self.theme_manager.current_theme,
            "ram": int(self.settings.get("ram", 4)),
            "mods_enabled": bool(self.settings.get("mods_enabled", True)),
            "mod_loader": str(self.settings.get("mod_loader", "Vanilla")),
            "curseforge_url": str(self.settings.get("curseforge_url", "")),
            "keep_launcher_open": bool(self.settings.get("keep_launcher_open", True)),
            "use_java_args": bool(self.settings.get("use_java_args", False)),
            "java_args": str(self.settings.get("java_args", "")),
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
        self.profile_screen.refresh_theme()
        self.settings_screen.refresh_theme()
        self.main_screen.refresh_runtime_cards()
        self.save_settings()

    def open_mods_folder(self) -> None:
        mods_dir = ensure_mods_folder()
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(mods_dir)))

    def show_main_screen(self, username: str = "") -> None:
        if username:
            self.current_username = username
        self.main_screen.set_username(self.current_username)
        self.main_screen.refresh_runtime_cards()
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

    def show_profile(self) -> None:
        if self.launch_thread.isRunning():
            return
        if not self.current_username:
            self.show_login()
            return
        self.profile_screen.load_profile(self.current_username)
        self.stacked_widget.setCurrentWidget(self.profile_screen)

    def show_mods(self) -> None:
        if self.launch_thread.isRunning():
            return
        self.mods_screen.refresh_mods_list()
        self.stacked_widget.setCurrentWidget(self.mods_screen)

    def reload_server_banner(self) -> None:
        self.main_screen.server_banner.reload_banner()
        QMessageBox.information(
            self,
            "Баннер",
            f"Баннер перечитан из assets/{PROMO_BANNER_FILE}",
        )

    def _validated_username(self) -> Optional[str]:
        username = self.main_screen.username.text().strip()
        if not username:
            QMessageBox.warning(self, "Никнейм", "Введите никнейм Minecraft.")
            return None
        self.current_username = username
        self.main_screen.set_username(username)
        return username

    def _start_launch(self, version_id: str) -> None:
        if self.launch_thread.isRunning():
            return
        username = self._validated_username()
        if username is None:
            return

        self.settings = self.settings_screen.get_settings()
        self.save_settings()

        if self.settings.get("mods_enabled", True):
            ensure_mods_folder()
            selected_loader = str(self.settings.get("mod_loader", "Vanilla"))
            if selected_loader not in ("Vanilla", "Авто"):
                self.main_screen.start_button.setText(f"{selected_loader.upper()}…")

        self.launch_thread.configure(version_id, username, self.settings)
        self.main_screen.start_button.setText("ПОДГОТОВКА…")
        self.launch_thread.start()

    def launch_game(self) -> None:
        selected = self.main_screen.version_select.currentData()
        self._start_launch(str(selected or self.main_screen.version_select.currentText()))

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