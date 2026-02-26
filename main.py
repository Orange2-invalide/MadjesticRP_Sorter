#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Majestic RP Screenshot Sorter v4.0.0
by create Orange · https://www.donationalerts.com/r/orange91323
"""

import sys
import os
import re
import cv2
import json
import time
import shutil
import bisect
import hashlib
import threading
import webbrowser
from pathlib import Path
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Generator
from concurrent.futures import ThreadPoolExecutor
from collections import OrderedDict
import datetime
from PIL import Image, ImageTk, ImageDraw

import numpy as np
from PIL import Image, ImageTk
import customtkinter as ctk
from tkinter import filedialog, Text, END
import tkinter as tk
from loguru import logger

import sys


def get_data_dir():
    if sys.platform == 'win32':
        base = Path(os.environ.get('APPDATA', Path.home()))
    else:
        base = Path.home()

    data_dir = base / "MajesticSorter"
    data_dir.mkdir(exist_ok=True)
    return data_dir


DATA_DIR = get_data_dir()


# ═══════════════════════════════════════════
#  СИСТЕМА АВТООБНОВЛЕНИЯ
# ═══════════════════════════════════════════

def _parse_version(version_str):
    """Парсит версию в кортеж чисел для сравнения."""
    try:
        # Убираем 'v' в начале если есть
        version_str = version_str.strip().lstrip('v').lstrip('V')
        parts = version_str.split('.')
        return tuple(int(p) for p in parts[:3])
    except:
        return (0, 0, 0)


def _is_newer_version(latest, current):
    """Проверяет, новее ли latest чем current."""
    return _parse_version(latest) > _parse_version(current)


def check_for_updates(callback=None):
    """
    Проверяет наличие обновлений на GitHub.
    Возвращает: (есть_обновление, версия, ссылка_скачивания, описание)
    """
    # Если репозиторий не указан — пропускаем проверку
    if not GITHUB_REPO or not UPDATE_CHECK_URL:
        return False, APP_VERSION, None, None

    try:
        import urllib.request

        req = urllib.request.Request(
            UPDATE_CHECK_URL,
            headers={"User-Agent": "MajesticSorter/AutoUpdate"}
        )

        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))

            latest_version = data.get("tag_name", "").lstrip('v')
            description = data.get("body", "")

            # Ищем файл для скачивания
            download_url = None
            for asset in data.get("assets", []):
                name = asset.get("name", "").lower()
                if name.endswith('.exe') or name.endswith('.zip'):
                    download_url = asset.get("browser_download_url")
                    break

            # Если нет assets, используем zipball
            if not download_url:
                download_url = data.get("zipball_url")

            if _is_newer_version(latest_version, APP_VERSION):
                return True, latest_version, download_url, description

            return False, latest_version, download_url, description

    except Exception as e:
        print(f"[UPDATE] Ошибка проверки: {e}")
        return False, None, None, None

def download_update(url, progress_callback=None):
    """
    Скачивает обновление.
    progress_callback(percent, downloaded, total) - для прогресс-бара
    """
    try:
        import urllib.request

        # Определяем имя файла
        filename = url.split('/')[-1]
        if not filename.endswith(('.exe', '.zip')):
            filename = "MajesticSorter_update.zip"

        DATA_DIR = Path.home() / ".majestic_sorter"
        DATA_DIR.mkdir(exist_ok=True)

        download_path = DATA_DIR / filename  # ← ЭТА СТРОКА БЫЛА ПРОПУЩЕНА!

        req = urllib.request.Request(
            url,
            headers={"User-Agent": "MajesticSorter/AutoUpdate"}
        )

        with urllib.request.urlopen(req, timeout=60) as response:
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            chunk_size = 8192

            with open(download_path, 'wb') as f:
                while True:
                    chunk = response.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)

                    if progress_callback and total_size > 0:
                        percent = int(downloaded * 100 / total_size)
                        progress_callback(percent, downloaded, total_size)

        return True, download_path

    except Exception as e:
        print(f"[UPDATE] Ошибка скачивания: {e}")
        return False, None

def apply_update(file_path):
    """Применяет обновление (открывает папку с файлом)."""
    try:
        import subprocess
        import sys

        if sys.platform == 'win32':
            # Открываем папку с файлом
            subprocess.Popen(f'explorer /select,"{file_path}"')
            return True

        return False
    except Exception as e:
        print(f"[UPDATE] Ошибка применения: {e}")
        return False


class UpdateDialog(ctk.CTkToplevel):
    """Окно проверки и установки обновлений."""

    def __init__(self, parent, version, download_url, description):
        super().__init__(parent)

        print(f"[DEBUG] UpdateDialog.__init__ начало")

        self.title("Доступно обновление!")
        self.configure(fg_color=P["bg"])

        self.download_url = download_url
        self.version = version

        # Размеры и позиция
        w, h = 500, 350
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.resizable(False, False)
        self.minsize(w, h)

        # Строим интерфейс
        self._build(version, description)

        # КРИТИЧЕСКИ ВАЖНО: Принудительно показываем окно
        self.deiconify()  # Показать окно
        self.lift()  # Поднять наверх
        self.focus_force()  # Установить фокус
        self.grab_set()  # Захватить ввод

        # Обновляем окно
        self.update()

        # Ещё раз поднимаем через 100мс
        self.after(100, self._bring_to_front)

        print(f"[DEBUG] UpdateDialog.__init__ завершено")

    def _bring_to_front(self):
        """Поднимает окно на передний план."""
        try:
            self.deiconify()
            self.lift()
            self.focus_force()
            self.attributes('-topmost', True)
            self.update()
            self.after(300, lambda: self.attributes('-topmost', False))
            print(f"[DEBUG] _bring_to_front выполнено")
        except Exception as e:
            print(f"[DEBUG] _bring_to_front ошибка: {e}")

    def _build(self, version, description):
        print(f"[DEBUG] _build начало")

        # Основной контейнер
        main_frame = ctk.CTkFrame(self, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Заголовок
        ctk.CTkLabel(
            main_frame,
            text="🎉 Доступно обновление!",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=P["accent"]
        ).pack(pady=(10, 10))

        # Версии
        version_frame = ctk.CTkFrame(main_frame, fg_color=P["card"], corner_radius=10)
        version_frame.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(
            version_frame,
            text=f"Текущая версия: {APP_VERSION}",
            font=ctk.CTkFont(size=12),
            text_color=P["t2"]
        ).pack(pady=(10, 2))

        ctk.CTkLabel(
            version_frame,
            text=f"Новая версия: {version}",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=P["ok"]
        ).pack(pady=(2, 10))

        # Описание
        if description:
            ctk.CTkLabel(
                main_frame,
                text="Что нового:",
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=P["text"]
            ).pack(anchor="w", padx=10, pady=(10, 5))

            desc_text = description[:300]
            if len(description) > 300:
                desc_text += "..."

            ctk.CTkLabel(
                main_frame,
                text=desc_text,
                font=ctk.CTkFont(size=10),
                text_color=P["t2"],
                wraplength=450,
                justify="left"
            ).pack(fill="x", padx=10, pady=(0, 10))

        # Кнопки внизу
        btn_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        btn_frame.pack(fill="x", padx=10, pady=(20, 10), side="bottom")

        # Кнопка "Позже"
        later_btn = ctk.CTkButton(
            btn_frame,
            text="Позже",
            width=150,
            height=40,
            fg_color=P["entry"],
            hover_color=P["bh"],
            border_width=1,
            border_color=P["border"],
            text_color=P["t2"],
            font=ctk.CTkFont(size=12),
            command=self._on_later
        )
        later_btn.pack(side="left", padx=(0, 10))
        print(f"[DEBUG] Кнопка 'Позже' создана")

        # Кнопка "Скачать"
        download_btn = ctk.CTkButton(
            btn_frame,
            text="🌐 Скачать обновление",
            width=200,
            height=40,
            fg_color=P["accent"],
            hover_color=P["ah"],
            text_color="#fff",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._open_browser
        )
        download_btn.pack(side="right")
        print(f"[DEBUG] Кнопка 'Скачать' создана")

        print(f"[DEBUG] _build завершено")

    def _on_later(self):
        """Закрывает окно."""
        print(f"[DEBUG] Нажата кнопка 'Позже'")
        self.destroy()

    def _open_browser(self):
        """Открывает страницу релиза в браузере."""
        print(f"[DEBUG] Нажата кнопка 'Скачать'")
        try:
            url = f"https://github.com/{GITHUB_REPO}/releases/latest"
            print(f"[DEBUG] Открываю URL: {url}")
            webbrowser.open(url)
            self.destroy()
        except Exception as e:
            print(f"[DEBUG] Ошибка открытия браузера: {e}")

    def _open_download_page(self):
        """Открывает страницу релиза в браузере."""
        import webbrowser
        url = DOWNLOAD_URL if DOWNLOAD_URL else self.download_url
        if url:
            webbrowser.open(url)
        self.destroy()
    def _download_thread(self):
        def progress_callback(percent, downloaded, total):
            mb_downloaded = downloaded / (1024 * 1024)
            mb_total = total / (1024 * 1024)

            self.after(0, lambda: self.progress_bar.set(percent / 100))
            self.after(0, lambda: self.progress_label.configure(
                text=f"{percent}% ({mb_downloaded:.1f} / {mb_total:.1f} MB)"
            ))

        success, file_path = download_update(self.download_url, progress_callback)

        if success:
            self.after(0, lambda: self._download_complete(file_path))
        else:
            self.after(0, self._download_failed)

    def _download_complete(self, file_path):
        self.progress_bar.set(1)
        self.progress_label.configure(text="✅ Скачано!")

        self.download_btn.configure(
            text="📂 Открыть папку",
            state="normal",
            command=lambda: self._open_folder(file_path)
        )
        self.later_btn.configure(state="normal", text="Закрыть")

    def _download_failed(self):
        self.progress_label.configure(text="❌ Ошибка скачивания")
        self.download_btn.configure(text="Повторить", state="normal")
        self.later_btn.configure(state="normal")
        self.is_downloading = False

    def _open_folder(self, file_path):
        apply_update(file_path)
        self.destroy()


# ═══════════════════════════════════════════
#  ОПРЕДЕЛЕНИЕ GPU
# ═══════════════════════════════════════════

def _detect_gpu_vendor() -> str:
    """Определяет производителя GPU."""
    try:
        import torch
        if torch.cuda.is_available():
            return "NVIDIA"
    except ImportError:
        pass

    try:
        import onnxruntime as ort
        providers = ort.get_available_providers()
        if 'DmlExecutionProvider' in providers:
            return "AMD/Intel (DirectML)"
        if 'ROCMExecutionProvider' in providers:
            return "AMD (ROCm)"
    except ImportError:
        pass

    return "CPU"


GPU_VENDOR = _detect_gpu_vendor()

# Типы данных
_U8 = np.uint8
_U16 = np.uint16
_F32 = np.float32

# ═══════════════════════════════════════════
#  АВТООБНОВЛЕНИЕ
# ═══════════════════════════════════════════

APP_VERSION = "4.0.0"
GITHUB_REPO = "Orange2-invalide/MadjesticRP_Sorter"
UPDATE_CHECK_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
DOWNLOAD_URL = f"https://github.com/{GITHUB_REPO}/releases/latest"

# ═══════════════════════════════════════════
#  ПРОВЕРКА ДОСТУПНЫХ OCR ДВИЖКОВ
# ═══════════════════════════════════════════

# RapidOCR — лучший выбор (работает на AMD/Intel/NVIDIA)
RAPIDOCR_OK = False
RapidOCREngine = None
try:
    from rapidocr_onnxruntime import RapidOCR as RapidOCREngine
    RAPIDOCR_OK = True
    print("[DEBUG] RapidOCR загружен успешно")
except ImportError:
    try:
        from rapidocr import RapidOCR as RapidOCREngine
        RAPIDOCR_OK = True
        print("[DEBUG] RapidOCR (альт) загружен успешно")
    except ImportError:
        print("[DEBUG] RapidOCR не найден")

# PaddleOCR — опционально (только для NVIDIA)
PADDLEOCR_OK = False
PADDLE_HAS_CUDA = False
PaddleOCR = None
try:
    from paddleocr import PaddleOCR
    PADDLEOCR_OK = True
    try:
        import paddle
        PADDLE_HAS_CUDA = paddle.is_compiled_with_cuda()
    except:
        pass
    print(f"[DEBUG] PaddleOCR загружен, CUDA: {PADDLE_HAS_CUDA}")
except ImportError:
    print("[DEBUG] PaddleOCR не найден")
except Exception as e:
    print(f"[DEBUG] PaddleOCR ошибка: {e}")

# EasyOCR — медленный fallback
EASYOCR_OK = False
try:
    import easyocr
    EASYOCR_OK = True
    print("[DEBUG] EasyOCR загружен")
except ImportError:
    print("[DEBUG] EasyOCR не найден")

# Tesseract — для таймера боди-камеры
TESSERACT_OK = False
try:
    import pytesseract
    pytesseract.get_tesseract_version()
    TESSERACT_OK = True
    print("[DEBUG] Tesseract загружен")
except:
    print("[DEBUG] Tesseract не найден")

# Plyer для уведомлений
PLYER_OK = False
try:
    from plyer import notification as _notify
    PLYER_OK = True
except:
    pass

# Winsound для звуков
try:
    import winsound
except:
    winsound = None

# ═══════════════════════════════════════════
#  ОПРЕДЕЛЕНИЕ GPU
# ═══════════════════════════════════════════

def _detect_gpu_vendor() -> str:
    """Определяет производителя GPU."""
    try:
        import torch
        if torch.cuda.is_available():
            return "NVIDIA"
    except ImportError:
        pass

    try:
        import onnxruntime as ort
        providers = ort.get_available_providers()
        if 'DmlExecutionProvider' in providers:
            return "AMD/Intel (DirectML)"
        if 'ROCMExecutionProvider' in providers:
            return "AMD (ROCm)"
    except ImportError:
        pass

    return "CPU"

GPU_VENDOR = _detect_gpu_vendor()
print(f"[DEBUG] GPU: {GPU_VENDOR}")
print(f"[DEBUG] OCR статус: RapidOCR={RAPIDOCR_OK}, PaddleOCR={PADDLEOCR_OK}, EasyOCR={EASYOCR_OK}")

# Типы данных
_U8 = np.uint8
_U16 = np.uint16
_F32 = np.float32

UPDATE_URL = "https://api.github.com/repos/m1rageLA/Majestic-RP-Imgur-Reports-Sorter/releases/latest"
DOWNLOAD_URL = ""


def _play_sort_sound():
    try:
        if winsound:
            winsound.MessageBeep(winsound.MB_OK)
    except:
        pass


def _play_done_sound():
    try:
        if winsound:
            winsound.MessageBeep(winsound.MB_ICONASTERISK)
    except:
        pass


def _play_error_sound():
    try:
        if winsound:
            winsound.MessageBeep(winsound.MB_ICONHAND)
    except:
        pass


def _play_sort_sound():
    try:
        if winsound: winsound.MessageBeep(winsound.MB_OK)
    except:
        pass


def _play_done_sound():
    try:
        if winsound: winsound.MessageBeep(winsound.MB_ICONASTERISK)
    except:
        pass


def _play_error_sound():
    try:
        if winsound: winsound.MessageBeep(winsound.MB_ICONHAND)
    except:
        pass


APP_VERSION = "3.0.0"
APP_AUTHOR = "create Orange"
APP_DONATE = "https://www.donationalerts.com/r/orange91323"
APP_IDEAS = "AshHazee, Vlad Kimro"

P = {
    "bg": "#0a0a0a", "card": "#131313", "card2": "#1a1a1a", "entry": "#1e1e1e",
    "border": "#252525", "bh": "#333333", "accent": "#2CC985", "ah": "#3DF5A0",
    "red": "#E8364F", "rh": "#FF5068", "orange": "#FF8C42", "oh": "#FFA862",
    "purple": "#A855F7", "blue": "#3B82F6", "gold": "#FFD700", "text": "#E0E0E0",
    "t2": "#909090", "dim": "#484848", "log": "#080808", "ok": "#2CC985",
    "err": "#E8364F", "warn": "#FFA502", "info": "#70A1FF", "bodycam": "#ED3A3A",
    "donate_bg": "#1a1200", "donate_border": "#3d2e00"
}

EXTS = frozenset({".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp"})
THR_VER = 41
GROUP_BC_WINDOW = 30
_U8 = np.uint8;
_U16 = np.uint16;
_F32 = np.float32
_CACHE_MAX = 500

SETTINGS_FILE = DATA_DIR / "settings.json"
LICENSE_FILE = DATA_DIR / "license.key"
PRO_FEATURES = False


def load_settings() -> dict:
    if SETTINGS_FILE.exists():
        try:
            return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_settings(data: dict):
    SETTINGS_FILE.write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def _get_hwid() -> str:
    import platform
    raw = platform.node() + os.environ.get("COMPUTERNAME", "") + os.environ.get("USERNAME", "")
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _check_license() -> bool:
    """Проверяет лицензию через онлайн-проверку."""
    global PRO_FEATURES

    KEYS_URL = "https://gist.githubusercontent.com/Orange2-invalide/3ee82de29e91ca7d0fe33a3ed9f12c53/raw/keys.json"

    if not LICENSE_FILE.exists():
        print("[DEBUG] license.key не существует")
        PRO_FEATURES = False
        return False

    try:
        data = json.loads(LICENSE_FILE.read_text(encoding="utf-8"))
        key = data.get("key", "").strip().upper()
        print(f"[DEBUG] Ключ из файла: '{key}'")

        if not key.startswith("MJ-") or len(key) < 15:
            print(f"[DEBUG] Неверный формат ключа")
            PRO_FEATURES = False
            return False

        key_hash = hashlib.sha256(key.encode()).hexdigest()[:16]
        print(f"[DEBUG] Хэш ключа: {key_hash}")

        # Онлайн проверка
        try:
            import urllib.request
            print(f"[DEBUG] Запрос к: {KEYS_URL}")
            req = urllib.request.Request(KEYS_URL, headers={"User-Agent": "MajesticSorter/2.0"})
            with urllib.request.urlopen(req, timeout=10) as response:
                raw = response.read().decode('utf-8')
                print(f"[DEBUG] Ответ сервера: {raw[:200]}")
                online_data = json.loads(raw)

                allowed_hashes = online_data.get("keys", [])
                disabled_hashes = online_data.get("disabled_keys", [])

                print(f"[DEBUG] Разрешённые хэши: {allowed_hashes}")
                print(f"[DEBUG] Наш хэш в списке: {key_hash in allowed_hashes}")

                # Проверяем что ключ не отключён
                if key_hash in disabled_hashes:
                    print("[DEBUG] ❌ Ключ отключён!")
                    PRO_FEATURES = False
                    return False

                if key_hash in allowed_hashes:
                    print("[DEBUG] ✅ PRO активирован!")
                    data["verified"] = True
                    data["verified_hash"] = key_hash
                    data["last_check"] = datetime.datetime.now().isoformat()
                    LICENSE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
                    PRO_FEATURES = True
                    return True

        except Exception as e:
            print(f"[DEBUG] Ошибка сети: {e}")
            # Оффлайн проверка
            if data.get("verified") and data.get("verified_hash") == key_hash:
                print("[DEBUG] Используем оффлайн-верификацию")
                PRO_FEATURES = True
                return True

        PRO_FEATURES = False
        return False

    except Exception as e:
        print(f"[DEBUG] Ошибка: {e}")
        PRO_FEATURES = False
        return False

        # Генерируем хэш ключа
        key_hash = hashlib.sha256(key.encode()).hexdigest()[:16]
        print(f"[DEBUG] Хэш ключа: {key_hash}")

        # Пробуем проверить онлайн
        try:
            import urllib.request
            print(f"[DEBUG] Запрос к: {KEYS_URL}")
            req = urllib.request.Request(KEYS_URL, headers={"User-Agent": "MajesticSorter/2.0"})
            with urllib.request.urlopen(req, timeout=10) as response:
                raw = response.read().decode('utf-8')
                print(f"[DEBUG] Ответ сервера: {raw[:200]}")
                online_data = json.loads(raw)
                allowed_hashes = online_data.get("keys", [])
                print(f"[DEBUG] Разрешённые хэши: {allowed_hashes}")
                print(f"[DEBUG] Наш хэш в списке: {key_hash in allowed_hashes}")

                if key_hash in allowed_hashes:
                    print("[DEBUG] ✅ PRO активирован!")
                    data["verified"] = True
                    data["verified_hash"] = key_hash
                    LICENSE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
                    PRO_FEATURES = True
                    return True
                else:
                    print("[DEBUG] ❌ Хэш не найден в списке разрешённых")

        except Exception as e:
            print(f"[DEBUG] Ошибка сети: {e}")
            # Если есть оффлайн-верификация
            if data.get("verified") and data.get("verified_hash") == key_hash:
                print("[DEBUG] Используем оффлайн-верификацию")
                PRO_FEATURES = True
                return True

        PRO_FEATURES = False
        return False

    except Exception as e:
        print(f"[DEBUG] Ошибка чтения файла: {e}")
        import traceback
        traceback.print_exc()
        PRO_FEATURES = False
        return False

    except Exception as e:
        print(f"[DEBUG] Общая ошибка: {e}")
        PRO_FEATURES = False
        return False

    except Exception as e:
        print(f"[DEBUG] Ошибка: {e}")
        PRO_FEATURES = False
        return False

    except Exception:
        PRO_FEATURES = False
        return False

def _check_update() -> dict:
    """Проверяет наличие обновления"""
    try:
        import urllib.request
        with urllib.request.urlopen(UPDATE_URL, timeout=5) as response:
            data = json.loads(response.read().decode())
            return data
    except Exception:
        return {}


def generate_license_key() -> str:
    import random, string
    parts = ['MJ']
    for _ in range(3):
        parts.append(''.join(random.choices(
            string.ascii_uppercase + string.digits, k=4)))
    return '-'.join(parts)  # MJ-XXXX-XXXX-XXXX = 19 символов


SETTINGS_FILE = DATA_DIR / "settings.json"


def load_settings() -> dict:
    if SETTINGS_FILE.exists():
        try:
            return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_settings(data: dict):
    SETTINGS_FILE.write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )


OCR_CACHE_FILE = DATA_DIR / "ocr_cache.json"


class OCRDiskCache:
    def __init__(s):
        super().__init__()
        s._data = {};
        s._lk = threading.Lock()
        s._load()

    def _load(s):
        if OCR_CACHE_FILE.exists():
            try:
                s._data = json.loads(OCR_CACHE_FILE.read_text(encoding="utf-8"))
            except Exception:
                s._data = {}

    def save(s):
        with s._lk:
            try:
                OCR_CACHE_FILE.write_text(
                    json.dumps(s._data, indent=1, ensure_ascii=False), encoding="utf-8")
            except Exception:
                pass

    def get(s, file_hash):
        with s._lk:
            entry = s._data.get(file_hash)
            if entry: return entry.get("texts", []), entry.get("cat", "")
        return None, None

    def put(s, file_hash, texts, cat):
        with s._lk:
            s._data[file_hash] = {
                "texts": texts, "cat": cat,
                "ts": datetime.datetime.now().isoformat()
            }
            if len(s._data) > 5000:
                keys = sorted(s._data, key=lambda k: s._data[k].get("ts", ""))
                for k in keys[:1000]: del s._data[k]


_ocr_disk_cache = OCRDiskCache()

# ═══════════════════════════════════════════
#  БАЗА ЗНАНИЙ ЛОКАЦИЙ
# ═══════════════════════════════════════════
LOCATION_DB_FILE = DATA_DIR / "location_knowledge.json"


def load_location_db() -> dict:
    if LOCATION_DB_FILE.exists():
        try:
            return json.loads(LOCATION_DB_FILE.read_text(encoding="utf-8"))
        except:
            pass
    return {"samples": [], "feature_ranges": {}, "version": 1}


def save_location_db(db: dict):
    LOCATION_DB_FILE.write_text(
        json.dumps(db, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def add_location_sample(db: dict, features: dict, location: str, filename: str = ""):
    sample = {
        "location": location,
        "filename": filename,
        "features": features,
        "timestamp": datetime.datetime.now().isoformat()
    }
    db["samples"].append(sample)
    _update_feature_ranges(db, features, location)
    save_location_db(db)


def _update_feature_ranges(db: dict, features: dict, location: str):
    if location not in db["feature_ranges"]:
        db["feature_ranges"][location] = {}
    ranges = db["feature_ranges"][location]
    for key, val in features.items():
        if not isinstance(val, (int, float)):
            continue
        if key not in ranges:
            ranges[key] = {"min": val, "max": val, "sum": val, "count": 1, "mean": val}
        else:
            r = ranges[key]
            r["min"] = min(r["min"], val)
            r["max"] = max(r["max"], val)
            r["sum"] = r.get("sum", r["mean"] * r["count"]) + val
            r["count"] += 1
            r["mean"] = r["sum"] / r["count"]


def predict_location_from_db(db: dict, features: dict) -> Tuple[str, float, dict]:
    if not db.get("feature_ranges"):
        return "Unsorted", 0.0, {}
    FEATURE_WEIGHTS = {
        "elsh_beds": 7.0, "elsh_clothes": 5.0, "elsh_floor": 4.0,
        "elsh_lamp": 10.0, "elsh_wall_or": 3.0,
        "paleto_floor": 9.0, "paleto_wall_dark": 8.0,
        "paleto_wall_blue": 4.0, "paleto_sky": 2.0,
        "sandy_floor": 9.0, "sandy_door": 8.0,
        "sandy_wall": 3.0, "sandy_floor_br": 3.0, "sandy_mm": 5.0,
        "floor_h": 4.0, "floor_s": 3.0, "floor_v": 5.0,
    }
    scores = {};
    details = {}
    for location, ranges in db["feature_ranges"].items():
        score = 0.0;
        total_weight = 0.0;
        loc_details = {}
        for key, val in features.items():
            if not isinstance(val, (int, float)) or key not in ranges:
                continue
            r = ranges[key]
            weight = FEATURE_WEIGHTS.get(key, 1.0)
            mean = r["mean"]
            rng = max(r["max"] - r["min"], 0.001)
            dist = abs(val - mean) / rng
            similarity = max(0.0, 1.0 - dist)
            if r["min"] <= val <= r["max"]:
                similarity = min(1.0, similarity * 1.3)
            feature_score = similarity * weight
            score += feature_score;
            total_weight += weight
            loc_details[key] = {
                "val": round(val, 4), "mean": round(mean, 4),
                "sim": round(similarity, 3), "score": round(feature_score, 3)
            }
        scores[location] = score / total_weight if total_weight > 0 else 0.0
        details[location] = loc_details
    if not scores:
        return "Unsorted", 0.0, {}
    best = max(scores, key=scores.get)
    sorted_scores = sorted(scores.values(), reverse=True)
    conf = sorted_scores[0] - sorted_scores[1] if len(sorted_scores) > 1 else sorted_scores[0]
    return best, min(conf, 1.0), {"scores": scores, "details": details.get(best, {})}


# ═══════════════════════════════════════════
#  БАЗА ЗНАНИЙ ЛОКАЦИЙ
# ═══════════════════════════════════════════
TRIGGER_DB_FILE = DATA_DIR / "trigger_knowledge.json"


def load_trigger_db() -> dict:
    if TRIGGER_DB_FILE.exists():
        try:
            return json.loads(TRIGGER_DB_FILE.read_text(encoding="utf-8"))
        except:
            pass
    return {
        "labeled": [],
        "cat_keywords": {"TAB": [], "VAC": [], "PMP": []},
        "version": 1
    }


def save_trigger_db(db: dict):
    TRIGGER_DB_FILE.write_text(
        json.dumps(db, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def add_trigger_sample(db: dict, filename: str, cat: str,
                       ocr_texts: list, features: dict):
    """Добавляет размеченный пример в базу."""
    sample = {
        "file": filename,
        "cat": cat,  # TAB / VAC / PMP
        "ocr_texts": ocr_texts,
        "features": features
    }
    # Убираем дубликат если есть
    db["labeled"] = [s for s in db["labeled"] if s["file"] != filename]
    db["labeled"].append(sample)

    # Извлекаем ключевые слова из OCR текстов
    _extract_keywords_from_sample(db, cat, ocr_texts)
    save_trigger_db(db)


def _extract_keywords_from_sample(db: dict, cat: str, ocr_texts: list):
    """Извлекает уникальные слова из OCR и добавляет в словарь категории."""
    if cat not in db["cat_keywords"]:
        db["cat_keywords"][cat] = []

    existing = set(db["cat_keywords"][cat])

    for text in ocr_texts:
        # Разбиваем на слова длиннее 4 символов
        words = [w.strip(".,!?:;()[]") for w in text.split() if len(w.strip(".,!?:;()[]")) >= 4]
        for word in words:
            word = word.lower()
            if word not in existing:
                existing.add(word)
                db["cat_keywords"][cat].append(word)


def predict_cat_from_db(db: dict, ocr_texts: list) -> tuple:
    """
    Предсказывает категорию на основе базы триггеров.
    Возвращает (cat_code, confidence, matched_words)
    """
    if not db["labeled"]:
        return "", 0.0, []

    combined = " ".join(ocr_texts).lower()
    scores = {"TAB": 0, "VAC": 0, "PMP": 0}
    matched = {"TAB": [], "VAC": [], "PMP": []}

    # Считаем совпадения ключевых слов
    for cat, keywords in db["cat_keywords"].items():
        for kw in keywords:
            if len(kw) >= 4 and kw in combined:
                scores[cat] += 1
                matched[cat].append(kw)

    if all(v == 0 for v in scores.values()):
        return "", 0.0, []

    best_cat = max(scores, key=scores.get)
    best_score = scores[best_cat]
    total = sum(scores.values())
    confidence = best_score / total if total > 0 else 0.0

    # Минимальный порог — хотя бы 2 совпадения
    if best_score < 2:
        return "", 0.0, matched[best_cat]

    return best_cat, confidence, matched[best_cat]


# ═══════════════════════════════════════════
#  LRU КЭШ
# ═══════════════════════════════════════════
class LRUCache:
    def __init__(self, maxsize=_CACHE_MAX):
        self._d = OrderedDict();
        self._m = maxsize;
        self._lk = threading.Lock()

    def get(self, k):
        with self._lk:
            if k in self._d: self._d.move_to_end(k); return self._d[k]
        return None

    def put(self, k, v):
        with self._lk:
            if k in self._d: self._d.move_to_end(k)
            self._d[k] = v
            while len(self._d) > self._m: self._d.popitem(last=False)

    def pop(self, k):
        with self._lk: return self._d.pop(k, None)


# ═══════════════════════════════════════════
#  КОНФИГ
# ═══════════════════════════════════════════
@dataclass
class Config:
    BASE: Tuple[int, int] = (1920, 1080)

    CHAT_SCAN_ROIS: List[Tuple[int, int, int, int]] = field(default_factory=lambda: [
        # Для 1920x1080
        (0, 700, 800, 380),
        (0, 800, 650, 280),
        (400, 780, 1120, 280),
        (300, 700, 1320, 360),
        (0, 650, 960, 430),
        # Для меньших разрешений (1558x871 и подобных)
        (0, 500, 600, 350),
        (0, 550, 500, 300),
        (0, 450, 700, 400),
        (0, 400, 800, 450),
    ])

    TEXT_PURPLE_LO: Tuple[int, int, int] = (120, 30, 120);
    TEXT_PURPLE_HI: Tuple[int, int, int] = (160, 200, 255)
    TEXT_GREEN_LO: Tuple[int, int, int] = (35, 60, 120);
    TEXT_GREEN_HI: Tuple[int, int, int] = (85, 255, 255)
    TEXT_ORANGE_LO: Tuple[int, int, int] = (10, 80, 140);
    TEXT_ORANGE_HI: Tuple[int, int, int] = (30, 255, 255)
    TEXT_WHITE_LO: Tuple[int, int, int] = (0, 0, 160);
    TEXT_WHITE_HI: Tuple[int, int, int] = (180, 45, 255)
    TEXT_YELLOW_LO: Tuple[int, int, int] = (20, 80, 160);
    TEXT_YELLOW_HI: Tuple[int, int, int] = (40, 255, 255)
    TEXT_GRAY_LO: Tuple[int, int, int] = (0, 0, 120);
    TEXT_GRAY_HI: Tuple[int, int, int] = (180, 30, 200)
    TEXT_RED_LO: Tuple[int, int, int] = (0, 60, 120);
    TEXT_RED_HI: Tuple[int, int, int] = (10, 255, 255)
    TEXT_RED2_LO: Tuple[int, int, int] = (170, 60, 120);
    TEXT_RED2_HI: Tuple[int, int, int] = (180, 255, 255)

    KW_TABLETS: List[str] = field(default_factory=lambda: [
        "вылечил", "вылечен", "вылечили", "лечили", "лечил", "лечен",
        "таблетк", "таблет", "выдал", "получил", "вылечипи", "вылечипм",
        "вылечмим", "вылечмям", "еылечипи", "еылечмим", "еылечмям", "еыленмям",
        "кылечипм", "вылециям", "вылеиим", "вылечиям", "вылениям", "оглечения",
        "излечения", "излечил", "таблегк", "таблегки", "таблетик", "таблетни",
        "вылечипа", "вылечнли", "вылечнил", "еылечили", "еылечил", "леченмя",
        "печения", "печенмя", "лененмя", "купить таблет", "купивь таблет",
        "вьілечил", "вьілечили", "вілечив", "виличив", "таблетки", "табпетки",
    ])
    KW_VACCINES: List[str] = field(default_factory=lambda: [
        "вакцинировал", "вакцинировали", "вакцинир", "вакцин", "ваксин",
        "вакцинировамия", "вакщинировали", "вакциннровали", "вакмнровали",
        "вакынровали", "вакцинмровали", "вакцынировали", "вакцінував",
        "вакцинирован", "вакцинировап", "еакциниpовали", "еакцинировали",
        "вакц", "привив", "прививк", "привит", "шприц",
    ])
    KW_PMP: List[str] = field(default_factory=lambda: [
        "реанимировал", "реанимировали", "реанимир", "реаним",
        "реанімировал", "реанимировап",
    ])
    PMP_CONFIRM: List[str] = field(default_factory=lambda: [
        "750", "спасен", "спасён", "награда",
    ])
    KW_REJECT: List[str] = field(default_factory=lambda: [
        "транспорт", "семейный", "удалён", "секунд",
    ])
    KW_REFUSE: List[str] = field(default_factory=lambda: [
        "отказался от", "оказался от", "отказал", "отказался от лечения",
        "оказался от лечения", "отказался от печения", "отказался от леченмя",
        "отказался от ленения", "отказапся от",
    ])
    FUZZY_CORE_TABLETS: List[str] = field(default_factory=lambda: [
        "вылечил", "вылечили", "вылечен", "таблетки", "таблетк", "лечили", "лечил",
    ])
    FUZZY_CORE_VACCINES: List[str] = field(default_factory=lambda: [
        "вакцинировал", "вакцинировали", "вакцинир",
    ])
    FUZZY_CORE_PMP: List[str] = field(default_factory=lambda: [
        "реанимировал", "реанимировали",
    ])

    TESS_CFG: str = "--psm 6 --oem 1 -l rus"

    # Зоны
    MINIMAP = (40, 900, 260, 130)
    HORIZON = (300, 60, 1320, 280)
    CEILING = (400, 20, 1120, 180)
    WALL_L = (30, 180, 200, 520)
    WALL_R = (1690, 180, 200, 520)
    FLOOR = (350, 730, 1220, 220)
    FLOOR_CENTER = (600, 780, 720, 150)
    WALL_CENTER = (500, 200, 920, 400)
    BED_AREA = (400, 300, 1120, 450)

    # ELSH цвета HSV
    ELSH_FLOOR_LO: Tuple[int, int, int] = (50, 3, 150)
    ELSH_FLOOR_HI: Tuple[int, int, int] = (100, 40, 220)
    ELSH_WALL_ORANGE_LO: Tuple[int, int, int] = (15, 100, 80)
    ELSH_WALL_ORANGE_HI: Tuple[int, int, int] = (35, 255, 210)
    ELSH_BED_LO: Tuple[int, int, int] = (85, 60, 80)
    ELSH_BED_HI: Tuple[int, int, int] = (110, 255, 230)
    ELSH_CLOTHES_LO: Tuple[int, int, int] = (100, 20, 140)
    ELSH_CLOTHES_HI: Tuple[int, int, int] = (125, 100, 230)

    # PALETO цвета HSV
    PALETO_FLOOR_LO: Tuple[int, int, int] = (0, 0, 45)
    PALETO_FLOOR_HI: Tuple[int, int, int] = (180, 20, 90)
    PALETO_WALL_GRAY_LO: Tuple[int, int, int] = (0, 0, 75)
    PALETO_WALL_GRAY_HI: Tuple[int, int, int] = (180, 20, 130)
    PALETO_WALL_DARK_LO: Tuple[int, int, int] = (60, 10, 50)
    PALETO_WALL_DARK_HI: Tuple[int, int, int] = (130, 60, 115)
    PALETO_WALL_BLUE_LO: Tuple[int, int, int] = (80, 8, 60)
    PALETO_WALL_BLUE_HI: Tuple[int, int, int] = (120, 80, 130)

    # SANDY цвета HSV
    SANDY_FLOOR_LO: Tuple[int, int, int] = (18, 25, 120)
    SANDY_FLOOR_HI: Tuple[int, int, int] = (42, 255, 230)
    SANDY_WALL_LO: Tuple[int, int, int] = (20, 10, 120)
    SANDY_WALL_HI: Tuple[int, int, int] = (40, 60, 210)
    SANDY_FLOOR_BROWN_LO: Tuple[int, int, int] = (20, 40, 70)
    SANDY_FLOOR_BROWN_HI: Tuple[int, int, int] = (38, 130, 175)
    SANDY_DOOR_LO: Tuple[int, int, int] = (10, 120, 15)
    SANDY_DOOR_HI: Tuple[int, int, int] = (30, 255, 50)

    # Пороги
    THR_ELSH_FLOOR: float = 0.001
    THR_ELSH_WALL_ORANGE: float = 0.05
    THR_ELSH_BED: float = 0.002
    THR_PALETO_FLOOR_DARK: float = 0.15
    THR_PALETO_WALL_DARK: float = 0.15
    THR_SANDY_FLOOR_SAND: float = 0.30
    THR_SANDY_WALL_BEIGE: float = 0.06
    THR_SANDY_DOOR: float = 0.10

    ELSH_LAMP = ((0, 0, 230), (180, 25, 255))
    SANDY_MAP = ((14, 80, 90), (32, 210, 195))
    PALETO_SKY = ((88, 12, 50), (155, 130, 200))

    THR_ELSH_LAMP: float = 0.005
    THR_SANDY_MAP: float = 0.06
    THR_PALETO_SKY: float = 0.50
    THR_SKIP_OCR: float = 0.02
    W_MM: float = 4.0;
    W_CT: float = 3.0

    THR_DB_CONFIDENCE: float = 0.05
    MIN_DB_SAMPLES: int = 3

    HOSPITALS_OCR: Dict[str, List[str]] = field(default_factory=lambda: {
        "ELSH": ["alta", "pillbox", "strawberry", "textile", "mission", "chamberlain",
                 "integrity", "rockford", "davis", "vespucci", "vinewood"],
        "Sandy Shores": ["sandy", "shores", "desert", "grand", "senora", "harmony"],
        "Paleto Bay": ["paleto", "bay", "procopio", "blaine", "grapeseed"],
    })
    NIGHT_START: int = 22;
    NIGHT_END: int = 12
    F_SANDY: str = "Sandy"
    F_PALETO: str = "Paleto"
    F_ELSH: str = "ELSH"
    F_UNK: str = "Unsorted"

    # Боди-кам
    BODYCAM_TIMER_ROI: Tuple[int, int, int, int] = (68, 836, 70, 19)
    BODYCAM_ROIS: List[Tuple[int, int, int, int]] = field(default_factory=lambda: [
        (0, 790, 90, 70), (0, 810, 70, 60), (0, 830, 60, 50), (0, 760, 130, 110), (10, 800, 80, 70),
        (0, 850, 80, 50), (0, 870, 100, 40), (0, 20, 90, 70), (0, 40, 80, 60), (0, 10, 110, 90),
        (1830, 20, 90, 70), (1820, 10, 100, 90), (1830, 790, 90, 70), (1820, 810, 100, 60),
    ])
    BODYCAM_SCAN_STRIPS: List[Tuple[int, int, int, int]] = field(default_factory=lambda: [
        (0, 400, 300, 50), (0, 450, 300, 50), (0, 500, 300, 50), (0, 550, 300, 50), (0, 600, 300, 50),
        (0, 650, 300, 50), (0, 700, 300, 50), (0, 750, 300, 50), (0, 800, 300, 50), (0, 850, 300, 50),
        (0, 900, 300, 50), (0, 0, 300, 50), (0, 50, 300, 50),
    ])
    BODYCAM_RED_STRICT_LO: Tuple[int, int, int] = (0, 100, 80)
    BODYCAM_RED_STRICT_HI: Tuple[int, int, int] = (10, 255, 255)
    BODYCAM_RED2_STRICT_LO: Tuple[int, int, int] = (170, 100, 80)
    BODYCAM_RED2_STRICT_HI: Tuple[int, int, int] = (180, 255, 255)
    BODYCAM_RED_DIM_LO: Tuple[int, int, int] = (0, 60, 50)
    BODYCAM_RED_DIM_HI: Tuple[int, int, int] = (15, 255, 220)
    BODYCAM_RED2_DIM_LO: Tuple[int, int, int] = (165, 60, 50)
    BODYCAM_RED2_DIM_HI: Tuple[int, int, int] = (180, 255, 220)
    BODYCAM_RED_SOFT_LO: Tuple[int, int, int] = (0, 40, 40)
    BODYCAM_RED_SOFT_HI: Tuple[int, int, int] = (20, 255, 255)
    BODYCAM_RED2_SOFT_LO: Tuple[int, int, int] = (160, 40, 40)
    BODYCAM_RED2_SOFT_HI: Tuple[int, int, int] = (180, 255, 255)
    BODYCAM_BGR_R_MIN: int = 100;
    BODYCAM_BGR_BG_MAX: int = 95
    BODYCAM_BGR_DOMINANCE: float = 1.3
    BODYCAM_BGR_DIM_R_MIN: int = 80;
    BODYCAM_BGR_DIM_R_MAX: int = 220
    BODYCAM_BGR_DIM_G_MAX: int = 90;
    BODYCAM_BGR_DIM_B_MAX: int = 85
    BODYCAM_BGR_DIM_DOMINANCE: float = 1.2;
    BODYCAM_BGR_DIM_MIN_CONFIRM: int = 3
    BODYCAM_RED_THR: float = 0.002;
    BODYCAM_RED_THR_SOFT: float = 0.003
    BODYCAM_MAX_RED_RATIO: float = 0.25
    BODYCAM_BLOB_STRICT_R_MIN: float = 140.0;
    BODYCAM_BLOB_STRICT_G_MAX: float = 90.0
    BODYCAM_BLOB_STRICT_B_MAX: float = 90.0;
    BODYCAM_BLOB_STRICT_DOM: float = 1.5
    BODYCAM_BLOB_STRICT_CIRC: float = 0.35
    BODYCAM_BLOB_STRICT_AREA_MIN: int = 10;
    BODYCAM_BLOB_STRICT_AREA_MAX: int = 800
    BODYCAM_BLOB_DIM_R_MIN: float = 90.0;
    BODYCAM_BLOB_DIM_R_MAX: float = 220.0
    BODYCAM_BLOB_DIM_G_MAX: float = 95.0;
    BODYCAM_BLOB_DIM_B_MAX: float = 95.0
    BODYCAM_BLOB_DIM_DOM: float = 1.2;
    BODYCAM_BLOB_DIM_CIRC: float = 0.30
    BODYCAM_BLOB_DIM_AREA_MIN: int = 10;
    BODYCAM_BLOB_DIM_AREA_MAX: int = 800
    BODYCAM_BLOB_SOFT_R_MIN: float = 70.0;
    BODYCAM_BLOB_SOFT_G_MAX: float = 110.0
    BODYCAM_BLOB_SOFT_B_MAX: float = 110.0;
    BODYCAM_BLOB_SOFT_DOM: float = 1.1
    BODYCAM_BLOB_SOFT_CIRC: float = 0.25
    BODYCAM_BLOB_SOFT_AREA_MIN: int = 8;
    BODYCAM_BLOB_SOFT_AREA_MAX: int = 1000
    BODYCAM_BLOB_MAX_X: int = 400
    WARM_CORNER_HUE_MAX: int = 25;
    WARM_CORNER_HUE_MIN2: int = 170
    WARM_CORNER_SAT_MIN: int = 40;
    WARM_CORNER_VAL_MIN: int = 40
    WARM_CORNER_STRONG_RATIO: float = 0.3;
    WARM_CORNER_STRONG_RDOM: float = 0.3
    WARM_CORNER_WEAK_RATIO: float = 0.15;
    WARM_CORNER_WEAK_RDOM: float = 0.15
    BC_TINT_SAT_MIN: int = 25;
    BC_TINT_CORNER_RATIO: float = 0.4
    BC_TINT_CORNERS_NEEDED: int = 3;
    BC_VIGNETTE_VAL_MAX: int = 100

    def save_thresholds(self, p=None):
        if p is None:
            p = DATA_DIR / "thresholds.json"
        d = {"_version": THR_VER}
        for k in dir(self):
            if k.startswith(("THR_", "BODYCAM_", "ELSH_", "PALETO_", "WARM_", "BC_", "TEXT_", "SANDY_")):
                if not callable(getattr(self, k)):
                    try:
                        d[k] = getattr(self, k)
                    except:
                        pass
        p.write_text(json.dumps(d, indent=2, default=str), encoding="utf-8")

    def load_thresholds(self, p=None):
        if p is None:
            p = DATA_DIR / "thresholds.json"
        if not p.exists(): return
        if not p.exists(): return
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            if d.get("_version", 0) < THR_VER: p.unlink(); return
            for k, v in d.items():
                if hasattr(self, k) and k != "_version":
                    try:
                        cur = getattr(self, k)
                        if isinstance(cur, tuple):
                            setattr(self, k, tuple(v))
                        elif isinstance(cur, float):
                            setattr(self, k, float(v))
                        elif isinstance(cur, int):
                            setattr(self, k, int(v))
                        else:
                            setattr(self, k, v)
                    except:
                        pass
        except:
            try:
                p.unlink()
            except:
                pass


# ═══════════════════════════════════════════
#  УТИЛИТЫ
# ═══════════════════════════════════════════
_TS1 = re.compile(r'(\d{4})-(\d{2})-(\d{2})\s+(\d{2})(\d{2})(\d{2})')
_TS2 = re.compile(r'(\d{4})-(\d{2})-(\d{2})\s+(\d{2})-(\d{2})-(\d{2})')


def _extract_ts(fp):
    n = fp.stem
    for pat in (_TS1, _TS2):
        m = pat.search(n)
        if m:
            try:
                return datetime.datetime(
                    int(m.group(1)), int(m.group(2)), int(m.group(3)),
                    int(m.group(4)), int(m.group(5)), int(m.group(6))
                ).timestamp()
            except:
                pass
    try:
        return fp.stat().st_mtime
    except:
        return None


def _ld(fp):
    """Загружает изображение, поддерживает пути с кириллицей."""
    try:
        # Работает с путями содержащими русские буквы
        with open(str(fp), 'rb') as f:
            img_array = np.frombuffer(f.read(), dtype=np.uint8)
            img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
            return img
    except Exception as e:
        logger.error(f"Ошибка загрузки {fp}: {e}")
        return None


def _fh(fp):
    h = hashlib.md5()
    with open(fp, "rb") as f: h.update(f.read(65536))
    return h.hexdigest()


# ═══════════════════════════════════════════
#  КОНТЕКСТ ИЗОБРАЖЕНИЯ
# ═══════════════════════════════════════════
class ImageContext:
    __slots__ = ('img', 'cfg', 'h', 'w', 'sx', 'sy', '_hsv', '_gray', '_ism', '_hsm',
                 '_masks', '_pcd', '_pcr', '_cc', '_chat_detected', '_chat_roi')

    def __init__(s, img, cfg):
        s.img = img;
        s.cfg = cfg;
        s.h, s.w = img.shape[:2]
        s.sx = s.w / cfg.BASE[0];
        s.sy = s.h / cfg.BASE[1]
        s._hsv = None;
        s._gray = None;
        s._ism = None;
        s._hsm = None
        s._masks = {};
        s._pcd = False;
        s._pcr = True;
        s._cc = {}
        s._chat_detected = False;
        s._chat_roi = None

    @property
    def hsv(s):
        if s._hsv is None: s._hsv = cv2.cvtColor(s.img, cv2.COLOR_BGR2HSV)
        return s._hsv

    @property
    def gray(s):
        if s._gray is None: s._gray = cv2.cvtColor(s.img, cv2.COLOR_BGR2GRAY)
        return s._gray

    @property
    def img_small(s):
        if s._ism is None:
            s._ism = cv2.resize(s.img, (s.w >> 2, s.h >> 2), interpolation=cv2.INTER_AREA)
        return s._ism

    @property
    def hsv_small(s):
        if s._hsm is None:
            s._hsm = cv2.cvtColor(s.img_small, cv2.COLOR_BGR2HSV)
        return s._hsm

    def _bnd(s, x, y, w, h, sm=False):
        if sm:
            s4, s5 = s.sx * .25, s.sy * .25
            a, b = max(0, int(x * s4)), max(0, int(y * s5))
            src = s._hsm if s._hsm is not None else s.img_small
            mh, mw = src.shape[:2]
            c, d = min(mw, int((x + w) * s4)), min(mh, int((y + h) * s5))
        else:
            a, b = max(0, int(x * s.sx)), max(0, int(y * s.sy))
            c, d = min(s.w, int((x + w) * s.sx)), min(s.h, int((y + h) * s.sy))
        return (a, b, c, d) if c > a and d > b else None

    def crop(s, x, y, w, h):
        k = ('i', x, y, w, h);
        v = s._cc.get(k)
        if v is not None: return v
        bn = s._bnd(x, y, w, h)
        if bn is None: return None
        a, b, c, d = bn;
        r = s.img[b:d, a:c]
        res = r if r.size > 0 else None;
        s._cc[k] = res;
        return res

    def crop_hsv(s, x, y, w, h):
        bn = s._bnd(x, y, w, h)
        if bn is None: return None
        a, b, c, d = bn;
        r = s.hsv[b:d, a:c]
        return r if r.size > 0 else None

    def crop_hsv_small(s, x, y, w, h):
        bn = s._bnd(x, y, w, h, sm=True)
        if bn is None: return None
        a, b, c, d = bn;
        r = s.hsv_small[b:d, a:c]
        return r if r.size > 0 else None

    def get_mask(s, lo, hi, sm=False):
        k = (lo, hi, sm);
        v = s._masks.get(k)
        if v is not None: return v
        src = s.hsv_small if sm else s.hsv
        m = cv2.inRange(src, np.array(lo, _U8), np.array(hi, _U8))
        s._masks[k] = m;
        return m

    def crop_mask(s, mask, x, y, w, h, sm=False):
        bn = s._bnd(x, y, w, h, sm)
        if bn is None: return None
        a, b, c, d = bn;
        r = mask[b:d, a:c]
        return r if r.size > 0 else None

    def detect_chat_area(s, diag=None):
        if s._chat_detected: return s._chat_roi
        s._chat_detected = True
        gray = s.gray;
        best_score = 0;
        best_roi = None
        strip_h = max(1, int(60 * s.sy))
        for y_start in range(s.h - strip_h, max(0, s.h // 2), -strip_h // 2):
            for x_start in [0, int(s.w * 0.1)]:
                x_end = min(s.w, x_start + int(700 * s.sx))
                strip = gray[y_start:y_start + strip_h, x_start:x_end]
                if strip.size == 0: continue
                std = float(np.std(strip))
                if std < 15: continue
                _, bn = cv2.threshold(strip, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                cnt, _ = cv2.findContours(bn, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                score = len(cnt) * std
                if score > best_score:
                    best_score = score
                    roi_y = max(0, y_start - strip_h * 3)
                    roi_h = min(s.h - roi_y, strip_h * 8)
                    best_roi = (x_start, roi_y, x_end - x_start, roi_h)
        if best_roi and best_score > 500:
            s._chat_roi = best_roi
            if diag: diag.append(f"  [чат] обнаружен в {best_roi}")
        return s._chat_roi

    def quick_red_precheck(s, diag=None):
        if s._pcd: return s._pcr
        s._pcd = True
        if s.w < 400 or s.h < 200: s._pcr = True; return True
        lw = max(1, int(150 * s.sx));
        th = max(1, int(110 * s.sy));
        bh = max(1, int(150 * s.sy))
        zones = [("НЛ", slice(s.h - bh, s.h), slice(0, lw)), ("ВЛ", slice(0, th), slice(0, lw)),
                 ("ВП", slice(0, th), slice(s.w - lw, s.w)), ("НП", slice(s.h - bh, s.h), slice(s.w - lw, s.w))]
        for nm, sy, sx in zones:
            z = s.img[sy, sx]
            if z.size == 0: continue
            r = z[:, :, 2].astype(_F32);
            g = z[:, :, 1].astype(_F32);
            b = z[:, :, 0].astype(_F32)
            rm = (r > 35) & (r > g * 1.05) & (r > b * 1.05)
            rt = float(np.count_nonzero(rm)) / max(1, z.shape[0] * z.shape[1])
            if rt > 0.0005: s._pcr = True; return True
            zh = cv2.cvtColor(z, cv2.COLOR_BGR2HSV)
            sm = float(zh[:, :, 1].mean())
            if sm > 20: s._pcr = True; return True
        tx, ty, tw, tth = s.cfg.BODYCAM_TIMER_ROI;
        tr = s.crop(tx, ty, tw, tth)
        if tr is not None:
            g2 = cv2.cvtColor(tr, cv2.COLOR_BGR2GRAY)
            if float(np.std(g2)) > 15: s._pcr = True; return True
        hs = s.hsv_small
        m1 = cv2.inRange(hs, np.array([0, 30, 30], _U8), np.array([20, 255, 255], _U8))
        m2 = cv2.inRange(hs, np.array([160, 30, 30], _U8), np.array([180, 255, 255], _U8))
        tr2 = cv2.countNonZero(m1) + cv2.countNonZero(m2)
        tp = hs.shape[0] * hs.shape[1]
        if tr2 / max(1, tp) > 0.0002: s._pcr = True; return True
        s._pcr = False;
        return False


# ═══════════════════════════════════════════
#  OCR
# ═══════════════════════════════════════════
class OCR:
    _instance = None
    _lock = threading.Lock()
    _init_lock = threading.Lock()

    _engine = None
    _engine_name = "none"
    _initialized = False

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
        return cls._instance

    def init(self, callback=None) -> bool:
        """Инициализирует OCR с оптимизированными настройками."""
        with self._init_lock:
            if self._initialized:
                return self._engine is not None

            def log(msg, level="info"):
                print(f"[OCR] {msg}")
                if callback:
                    callback(msg, level)

            log(f"GPU: {GPU_VENDOR}")

            # RapidOCR с оптимизацией
            if RAPIDOCR_OK:
                try:
                    log("Загрузка RapidOCR (оптимизированный)...")

                    # Оптимизированные параметры для скорости
                    self._engine = RapidOCREngine(
                        det_use_cuda=False,
                        rec_use_cuda=False,
                        # Уменьшаем размер для быстрой обработки
                        det_limit_side_len=960,  # было 1920
                        det_limit_type="max",
                        # Меньше итераций
                        det_db_thresh=0.3,
                        det_db_box_thresh=0.5,
                        det_db_unclip_ratio=1.6,
                        # Быстрый режим
                        rec_batch_num=6,
                    )

                    self._engine_name = f"RapidOCR Fast ({GPU_VENDOR})"
                    log(f"✓ {self._engine_name}")
                    self._initialized = True
                    return True
                except TypeError:
                    # Если параметры не поддерживаются - используем базовые
                    try:
                        self._engine = RapidOCREngine()
                        self._engine_name = f"RapidOCR ({GPU_VENDOR})"
                        log(f"✓ {self._engine_name}")
                        self._initialized = True
                        return True
                    except Exception as e:
                        log(f"RapidOCR ошибка: {e}")
                except Exception as e:
                    log(f"RapidOCR ошибка: {e}")

            # PaddleOCR fallback
            if PADDLEOCR_OK:
                try:
                    log("Загрузка PaddleOCR...")
                    self._engine = PaddleOCR(
                        use_angle_cls=False,
                        lang="ru",
                        use_gpu=PADDLE_HAS_CUDA,
                        show_log=False
                    )
                    self._engine_name = "PaddleOCR"
                    log(f"✓ {self._engine_name}")
                    self._initialized = True
                    return True
                except Exception as e:
                    log(f"PaddleOCR ошибка: {e}")

            # EasyOCR fallback
            if EASYOCR_OK:
                try:
                    log("Загрузка EasyOCR...")
                    self._engine = easyocr.Reader(["ru", "en"], gpu=False, verbose=False)
                    self._engine_name = "EasyOCR"
                    log(f"✓ {self._engine_name}")
                    self._initialized = True
                    return True
                except Exception as e:
                    log(f"EasyOCR ошибка: {e}")

            log("❌ Нет доступных OCR движков!")
            self._initialized = True
            self._engine_name = "none"
            return False

    @property
    def name(self) -> str:
        return self._engine_name

    @property
    def is_ready(self) -> bool:
        return self._initialized and self._engine is not None

    @property
    def _n(self) -> str:
        return self._engine_name

    @property
    def _ok(self) -> bool:
        return self._initialized

    @property
    def _r(self):
        return self._engine

    def read(self, img, mc=0.15, mh=5, ml=2):
        """Читает текст с изображения."""
        if not self._initialized:
            self.init()
        if self._engine is None:
            return "", 0.

        if "RapidOCR" in self._engine_name:
            return self._read_rapid(img, mc, mh, ml)
        elif "Paddle" in self._engine_name:
            return self._read_paddle(img, mc, mh, ml)
        elif "EasyOCR" in self._engine_name:
            return self._read_easy(img, mc, mh, ml)

        return "", 0.

    def read_fast(self, img, mc=0.10, mh=3, ml=2):
        """Быстрое чтение с пониженными требованиями к качеству."""
        if not self._initialized:
            self.init()
        if self._engine is None:
            return "", 0.

        # Уменьшаем изображение для скорости
        h, w = img.shape[:2]
        if w > 800:
            scale = 800 / w
            img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)

        if "RapidOCR" in self._engine_name:
            return self._read_rapid(img, mc, mh, ml)
        elif "Paddle" in self._engine_name:
            return self._read_paddle(img, mc, mh, ml)
        elif "EasyOCR" in self._engine_name:
            return self._read_easy(img, mc, mh, ml)

        return "", 0.

    def _read_rapid(self, img, mc, mh, ml):
        try:
            result, _ = self._engine(img)
            if not result:
                return "", 0.

            lines, confidences = [], []
            for item in result:
                if len(item) < 3:
                    continue
                box, text, conf = item[0], item[1], item[2]

                if conf < mc or len(text.strip()) < ml:
                    continue

                if box:
                    try:
                        ys = [p[1] for p in box]
                        if max(ys) - min(ys) < mh:
                            continue
                    except:
                        pass

                lines.append(text.strip())
                confidences.append(conf)

            if not lines:
                return "", 0.

            return " ".join(lines).lower(), sum(confidences) / len(confidences)
        except Exception as e:
            return "", 0.

    def _read_paddle(self, img, mc, mh, ml):
        try:
            r = self._engine.ocr(img, cls=False)
            if not r or not r[0]:
                return "", 0.
            ln, cf = [], []
            for l in r[0]:
                if not l:
                    continue
                bx, (tx, c) = l
                if c < mc or len(tx.strip()) < ml:
                    continue
                if bx:
                    ys = [p[1] for p in bx]
                    if max(ys) - min(ys) < mh:
                        continue
                ln.append(tx.strip())
                cf.append(c)
            return (" ".join(ln).lower(), sum(cf) / len(cf)) if ln else ("", 0.)
        except:
            return "", 0.

    def _read_easy(self, img, mc, mh, ml):
        try:
            r = self._engine.readtext(img, detail=1, paragraph=False)
            if not r:
                return "", 0.
            ln, cf = [], []
            for bx, tx, c in r:
                if c < mc or len(tx.strip()) < ml:
                    continue
                if bx:
                    ys = [p[1] for p in bx]
                    if max(ys) - min(ys) < mh:
                        continue
                ln.append(tx.strip())
                cf.append(c)
            return (" ".join(ln).lower(), sum(cf) / len(cf)) if ln else ("", 0.)
        except:
            return "", 0.

    def has_text_region(self, gray, min_contours=2):
        """Быстрая проверка наличия текста без OCR."""
        if gray is None or gray.size == 0:
            return False
        if float(np.std(gray)) < 10:
            return False
        _, bn = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        cnt, _ = cv2.findContours(bn, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        return len(cnt) >= min_contours


_ocr = OCR()

# ═══════════════════════════════════════════
#  ПРЕДЗАГРУЗЧИК
# ═══════════════════════════════════════════
class FilePreloader:
    def __init__(s, mx=4):
        s._c = {};
        s._l = threading.Lock()
        s._p = ThreadPoolExecutor(2, thread_name_prefix="pf");
        s._m = mx

    def prefetch(s, fps):
        for fp in fps[:s._m]:
            k = str(fp)
            with s._l:
                if k in s._c: continue
            s._p.submit(s._load, fp)

    def _load(s, fp):
        k = str(fp);
        i = _ld(fp)
        with s._l:
            s._c[k] = i
            while len(s._c) > s._m * 3: del s._c[next(iter(s._c))]

    def get(s, fp):
        k = str(fp)
        with s._l:
            if k in s._c: return s._c.pop(k)
        return _ld(fp)

    def shutdown(s):
        s._p.shutdown(wait=False)


# ═══════════════════════════════════════════
#  БОДИ-КАМЕРА
# ═══════════════════════════════════════════
_TRE = re.compile(r'(\d{1,2}[:\.]?\d{2}[:\.]?\d{0,2})')


def _crbv(roi, rm, bm, d):
    if roi is None or roi.size == 0: return 0, 0
    b, g, r = roi[:, :, 0], roi[:, :, 1], roi[:, :, 2];
    t = roi.shape[0] * roi.shape[1]
    ds = int(d * 10);
    r16, g16, b16 = r.astype(_U16), g.astype(_U16), b.astype(_U16)
    m = (r >= rm) & (g <= bm) & (b <= bm) & (r16 * 10 > g16 * ds) & (r16 * 10 > b16 * ds)
    return int(np.count_nonzero(m)), t


def _crdv(roi, rn, rx, gx, bx, d):
    if roi is None or roi.size == 0: return 0, 0
    b, g, r = roi[:, :, 0], roi[:, :, 1], roi[:, :, 2];
    t = roi.shape[0] * roi.shape[1]
    ds = int(d * 10);
    r16, g16, b16 = r.astype(_U16), g.astype(_U16), b.astype(_U16)
    m = (r >= rn) & (r <= rx) & (g <= gx) & (b <= bx) & (r16 * 10 > g16 * ds) & (r16 * 10 > b16 * ds)
    return int(np.count_nonzero(m)), t


def _rdom(roi):
    if roi is None or roi.size == 0: return 0.
    r = roi[:, :, 2].astype(_F32);
    g = roi[:, :, 1].astype(_F32);
    b = roi[:, :, 0].astype(_F32)
    t = roi.shape[0] * roi.shape[1]
    return float(np.count_nonzero((r > g * 1.1) & (r > b * 1.1) & (r > 50))) / t if t else 0.


def _wc(ctx, cfg):
    cz = [(0, 780, 100, 80), (0, 800, 80, 70), (0, 830, 70, 60), (0, 10, 100, 80),
          (0, 20, 80, 70), (1820, 780, 100, 80), (1820, 10, 100, 80)]
    ws = wc = 0
    for zx, zy, zw, zh in cz:
        roi = ctx.crop(zx, zy, zw, zh);
        hr = ctx.crop_hsv(zx, zy, zw, zh)
        if roi is None or hr is None: continue
        t = roi.shape[0] * roi.shape[1]
        if t == 0: continue
        h_ch, s_ch, v_ch = hr[:, :, 0], hr[:, :, 1], hr[:, :, 2]
        wm = ((h_ch <= cfg.WARM_CORNER_HUE_MAX) | (h_ch >= cfg.WARM_CORNER_HUE_MIN2)) & \
             (s_ch > cfg.WARM_CORNER_SAT_MIN) & (v_ch > cfg.WARM_CORNER_VAL_MIN)
        wr = float(np.count_nonzero(wm)) / t;
        rd = _rdom(roi)
        rm_m = float(roi[:, :, 2].mean());
        gm_m = float(roi[:, :, 1].mean());
        bm_m = float(roi[:, :, 0].mean())
        mg = max(gm_m, bm_m)
        if wr > cfg.WARM_CORNER_STRONG_RATIO and rd > cfg.WARM_CORNER_STRONG_RDOM and rm_m > mg:
            ws += 1
        elif wr > cfg.WARM_CORNER_WEAK_RATIO and rd > cfg.WARM_CORNER_WEAK_RDOM and rm_m > mg * .95:
            wc += 1
    return ws >= 1 or wc >= 2


def _tv(ctx, cfg, diag=None):
    cr = ctx.crop(600, 300, 720, 480)
    if cr is None: return False
    ch = cv2.cvtColor(cr, cv2.COLOR_BGR2HSV)
    cs = float(ch[:, :, 1].mean());
    cv_ = float(ch[:, :, 2].mean())
    cz = [("НЛ", 0, 780, 120, 100), ("НЛ2", 0, 840, 80, 60), ("ВЛ", 0, 10, 120, 100),
          ("ВЛ2", 0, 30, 80, 70), ("ВП", 1800, 10, 120, 100), ("НП", 1800, 780, 120, 100)]
    ti = dk = 0
    for nm, zx, zy, zw, zh in cz:
        roi = ctx.crop(zx, zy, zw, zh);
        hr = ctx.crop_hsv(zx, zy, zw, zh)
        if roi is None or hr is None: continue
        t = roi.shape[0] * roi.shape[1]
        if t == 0: continue
        s2 = float(hr[:, :, 1].mean());
        v2 = float(hr[:, :, 2].mean())
        if s2 - cs > 10 and s2 > cfg.BC_TINT_SAT_MIN: ti += 1
        if cv_ - v2 > 30 and v2 < cfg.BC_VIGNETTE_VAL_MAX: dk += 1
        if float(np.count_nonzero(hr[:, :, 1] > 40)) / t > cfg.BC_TINT_CORNER_RATIO: ti += 1
    return ti >= cfg.BC_TINT_CORNERS_NEEDED or dk >= 3 or (ti >= 2 and dk >= 1)


def check_bc_timer(ctx, diag=None):
    cfg = ctx.cfg;
    tx, ty, tw, th = cfg.BODYCAM_TIMER_ROI
    roi = ctx.crop(tx, ty, tw, th)
    if roi is None: return False, ""
    g = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    if float(np.std(g)) < 10: return False, ""
    big = cv2.resize(g, None, fx=4, fy=4, interpolation=cv2.INTER_LINEAR)
    _, bn1 = cv2.threshold(big, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    bn2 = cv2.bitwise_not(bn1)
    for bi in (bn1, bn2):
        t, _ = _ocr.read(cv2.cvtColor(bi, cv2.COLOR_GRAY2BGR), mc=0.15, mh=3, ml=1)
        if t:
            tc = t.strip().replace(" ", "");
            m = _TRE.search(tc)
            if m:
                tv = m.group(1);
                dg = re.sub(r'[^0-9]', '', tv)
                if dg and not all(c == '0' for c in dg): return True, tv
    if TESSERACT_OK:
        for bi in (bn1, bn2):
            try:
                t = pytesseract.image_to_string(
                    bi, config="--psm 7 --oem 1 -c tessedit_char_whitelist=0123456789:").strip()
                if t:
                    m = _TRE.search(t.replace(" ", ""))
                    if m:
                        tv = m.group(1);
                        dg = re.sub(r'[^0-9]', '', tv)
                        if dg and not all(c == '0' for c in dg): return True, tv
            except:
                pass
    return False, ""


def _bis(a, c, ox, rm, gm, bm, cfg):
    return (cfg.BODYCAM_BLOB_STRICT_AREA_MIN <= a <= cfg.BODYCAM_BLOB_STRICT_AREA_MAX
            and c >= cfg.BODYCAM_BLOB_STRICT_CIRC and rm >= cfg.BODYCAM_BLOB_STRICT_R_MIN
            and gm <= cfg.BODYCAM_BLOB_STRICT_G_MAX and bm <= cfg.BODYCAM_BLOB_STRICT_B_MAX
            and rm > gm * cfg.BODYCAM_BLOB_STRICT_DOM and rm > bm * cfg.BODYCAM_BLOB_STRICT_DOM
            and ox <= cfg.BODYCAM_BLOB_MAX_X)


def _bid(a, c, ox, rm, gm, bm, cfg):
    return (cfg.BODYCAM_BLOB_DIM_AREA_MIN <= a <= cfg.BODYCAM_BLOB_DIM_AREA_MAX
            and c >= cfg.BODYCAM_BLOB_DIM_CIRC
            and cfg.BODYCAM_BLOB_DIM_R_MIN <= rm <= cfg.BODYCAM_BLOB_DIM_R_MAX
            and gm <= cfg.BODYCAM_BLOB_DIM_G_MAX and bm <= cfg.BODYCAM_BLOB_DIM_B_MAX
            and rm > gm * cfg.BODYCAM_BLOB_DIM_DOM and rm > bm * cfg.BODYCAM_BLOB_DIM_DOM
            and ox <= cfg.BODYCAM_BLOB_MAX_X)


def _biso(a, c, ox, rm, gm, bm, cfg):
    return (cfg.BODYCAM_BLOB_SOFT_AREA_MIN <= a <= cfg.BODYCAM_BLOB_SOFT_AREA_MAX
            and c >= cfg.BODYCAM_BLOB_SOFT_CIRC and rm >= cfg.BODYCAM_BLOB_SOFT_R_MIN
            and gm <= cfg.BODYCAM_BLOB_SOFT_G_MAX and bm <= cfg.BODYCAM_BLOB_SOFT_B_MAX
            and rm > gm * cfg.BODYCAM_BLOB_SOFT_DOM and rm > bm * cfg.BODYCAM_BLOB_SOFT_DOM
            and ox <= cfg.BODYCAM_BLOB_MAX_X)


def check_bodycam(ctx, diag=None):
    cfg = ctx.cfg
    if not ctx.quick_red_precheck(diag):
        if _tv(ctx, cfg, diag): return True, .002
        tf, tt = check_bc_timer(ctx, diag)
        if tf: return True, .5
        return False, 0.
    ms1 = ctx.get_mask(cfg.BODYCAM_RED_STRICT_LO, cfg.BODYCAM_RED_STRICT_HI)
    ms2 = ctx.get_mask(cfg.BODYCAM_RED2_STRICT_LO, cfg.BODYCAM_RED2_STRICT_HI)
    md1 = ctx.get_mask(cfg.BODYCAM_RED_DIM_LO, cfg.BODYCAM_RED_DIM_HI)
    md2 = ctx.get_mask(cfg.BODYCAM_RED2_DIM_LO, cfg.BODYCAM_RED2_DIM_HI)
    mf1 = ctx.get_mask(cfg.BODYCAM_RED_SOFT_LO, cfg.BODYCAM_RED_SOFT_HI)
    mf2 = ctx.get_mask(cfg.BODYCAM_RED2_SOFT_LO, cfg.BODYCAM_RED2_SOFT_HI)
    ms = cv2.bitwise_or(ms1, ms2);
    md = cv2.bitwise_or(md1, md2);
    mf = cv2.bitwise_or(mf1, mf2)
    br = 0.;
    sc = []
    for i, (rx, ry, rw, rh) in enumerate(cfg.BODYCAM_ROIS):
        roi = ctx.crop(rx, ry, rw, rh)
        if roi is None: continue
        t = roi.shape[0] * roi.shape[1]
        if t == 0: continue
        cs_m = ctx.crop_mask(ms, rx, ry, rw, rh);
        cd_m = ctx.crop_mask(md, rx, ry, rw, rh)
        if cs_m is None or cd_m is None: continue
        rs = cv2.countNonZero(cs_m);
        rd = cv2.countNonZero(cd_m)
        if (rs / t + rd / t) > cfg.BODYCAM_MAX_RED_RATIO: continue
        rb, _ = _crbv(roi, cfg.BODYCAM_BGR_R_MIN, cfg.BODYCAM_BGR_BG_MAX, cfg.BODYCAM_BGR_DOMINANCE)
        rbd, _ = _crdv(roi, cfg.BODYCAM_BGR_DIM_R_MIN, cfg.BODYCAM_BGR_DIM_R_MAX,
                       cfg.BODYCAM_BGR_DIM_G_MAX, cfg.BODYCAM_BGR_DIM_B_MAX, cfg.BODYCAM_BGR_DIM_DOMINANCE)
        rdm = _rdom(roi);
        ef = 0.
        if rb / t >= cfg.BODYCAM_RED_THR:
            ef = rb / t
        elif rs / t >= cfg.BODYCAM_RED_THR and rb > 0:
            ef = rs / t
        elif rbd / t >= cfg.BODYCAM_RED_THR and rbd >= cfg.BODYCAM_BGR_DIM_MIN_CONFIRM:
            ef = rbd / t
        elif rd / t >= cfg.BODYCAM_RED_THR and rbd >= cfg.BODYCAM_BGR_DIM_MIN_CONFIRM:
            ef = rd / t
        elif rdm >= .15 and rd / t >= .001:
            ef = rdm * .02
        elif rd / t >= cfg.BODYCAM_RED_THR * .5 and rdm >= .05:
            ef = rd / t
        if ef > br: br = ef
        if ef < cfg.BODYCAM_RED_THR:
            cf_m = ctx.crop_mask(mf, rx, ry, rw, rh)
            if cf_m is not None:
                rsf = cv2.countNonZero(cf_m);
                rf = rsf / t
                if cfg.BODYCAM_RED_THR_SOFT <= rf <= cfg.BODYCAM_MAX_RED_RATIO:
                    if rb >= 1 or rbd >= cfg.BODYCAM_BGR_DIM_MIN_CONFIRM or rdm >= .05:
                        rm2 = float(roi[:, :, 2].mean());
                        gm2 = float(roi[:, :, 1].mean());
                        bm2 = float(roi[:, :, 0].mean())
                        if rm2 > max(gm2, bm2) * 1.05: sc.append((rf, i))
    if br >= cfg.BODYCAM_RED_THR: return True, br
    if sc: sc.sort(reverse=True); return True, sc[0][0] * .8
    if _wc(ctx, cfg): return True, .003
    if _tv(ctx, cfg, diag): return True, .002
    tf, tt = check_bc_timer(ctx, diag)
    if tf: return True, .5
    ma = cv2.bitwise_or(cv2.bitwise_or(ms, md), mf)
    sb2 = [];
    db2 = [];
    sb3 = []
    for si, (sx2, sy2, sw2, sh2) in enumerate(cfg.BODYCAM_SCAN_STRIPS):
        sm = ctx.crop_mask(ma, sx2, sy2, sw2, sh2)
        if sm is None or cv2.countNonZero(sm) == 0: continue
        cnt, _ = cv2.findContours(sm, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not cnt: continue
        st = ctx.crop(sx2, sy2, sw2, sh2)
        if st is None: continue
        ix = 1. / ctx.sx
        for c in cnt:
            a = cv2.contourArea(c)
            if a < 5: continue
            p_arc = cv2.arcLength(c, True)
            if p_arc == 0: continue
            ci = 4. * np.pi * a / (p_arc * p_arc)
            x1, y1, bw, bh = cv2.boundingRect(c)
            br2 = st[y1:y1 + bh, x1:x1 + bw]
            if br2.size == 0: continue
            rm_b = float(br2[:, :, 2].mean());
            gm_b = float(br2[:, :, 1].mean());
            bm3 = float(br2[:, :, 0].mean())
            ox = int(x1 * ix) + sx2
            if ox > cfg.BODYCAM_BLOB_MAX_X: continue
            if _bis(a, ci, ox, rm_b, gm_b, bm3, cfg):
                sb2.append(1)
            elif _bid(a, ci, ox, rm_b, gm_b, bm3, cfg):
                db2.append(1)
            elif _biso(a, ci, ox, rm_b, gm_b, bm3, cfg):
                sb3.append(1)
    if sb2: return True, .005
    if db2: return True, .004
    if len(sb3) >= 2: return True, .003
    return False, br


# ═══════════════════════════════════════════
#  OCR + ТРИГГЕР
# ═══════════════════════════════════════════
def _extract_colored_text_mask(roi_bgr, cfg):
    hsv = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2HSV);
    masks = []
    for lo, hi in [(cfg.TEXT_PURPLE_LO, cfg.TEXT_PURPLE_HI), (cfg.TEXT_GREEN_LO, cfg.TEXT_GREEN_HI),
                   (cfg.TEXT_ORANGE_LO, cfg.TEXT_ORANGE_HI), (cfg.TEXT_WHITE_LO, cfg.TEXT_WHITE_HI),
                   (cfg.TEXT_YELLOW_LO, cfg.TEXT_YELLOW_HI), (cfg.TEXT_GRAY_LO, cfg.TEXT_GRAY_HI),
                   (cfg.TEXT_RED_LO, cfg.TEXT_RED_HI), (cfg.TEXT_RED2_LO, cfg.TEXT_RED2_HI)]:
        masks.append(cv2.inRange(hsv, np.array(lo, _U8), np.array(hi, _U8)))
    combined = masks[0]
    for m in masks[1:]: combined = cv2.bitwise_or(combined, m)
    combined = cv2.morphologyEx(combined, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (3, 1)))
    combined = cv2.morphologyEx(combined, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2)))
    return combined


def _generate_ocr_variants_fast(roi_bgr, cfg) -> Generator:
    g = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2GRAY);
    scale = 1.8
    yield roi_bgr
    color_mask = _extract_colored_text_mask(roi_bgr, cfg)
    if cv2.countNonZero(color_mask) > 50:
        cm_big = cv2.resize(color_mask, None, fx=scale, fy=scale, interpolation=cv2.INTER_NEAREST)
        yield cv2.cvtColor(cm_big, cv2.COLOR_GRAY2BGR)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    cl = clahe.apply(g)
    cl_big = cv2.resize(cl, None, fx=scale, fy=scale, interpolation=cv2.INTER_LINEAR)
    _, cl_bn = cv2.threshold(cl_big, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    yield cv2.cvtColor(cl_bn, cv2.COLOR_GRAY2BGR)
    g_big = cv2.resize(g, None, fx=scale, fy=scale, interpolation=cv2.INTER_LINEAR)
    _, bn2 = cv2.threshold(g_big, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    yield cv2.cvtColor(bn2, cv2.COLOR_GRAY2BGR)
    hsv = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2HSV)
    white = cv2.inRange(hsv, np.array([0, 0, 150], _U8), np.array([180, 50, 255], _U8))
    purple = cv2.inRange(hsv, np.array([120, 25, 110], _U8), np.array([165, 220, 255], _U8))
    wp = cv2.bitwise_or(white, purple)
    if cv2.countNonZero(wp) > 30:
        wp_big = cv2.resize(wp, None, fx=scale, fy=scale, interpolation=cv2.INTER_NEAREST)
        yield cv2.cvtColor(wp_big, cv2.COLOR_GRAY2BGR)


def _levenshtein(s1, s2):
    if abs(len(s1) - len(s2)) > 3: return 99
    if len(s1) > len(s2): s1, s2 = s2, s1
    prev = list(range(len(s1) + 1))
    for j in range(1, len(s2) + 1):
        curr = [j] + [0] * len(s1)
        for i in range(1, len(s1) + 1):
            cost = 0 if s1[i - 1] == s2[j - 1] else 1
            curr[i] = min(curr[i - 1] + 1, prev[i] + 1, prev[i - 1] + cost)
        prev = curr
    return prev[len(s1)]


def _fuzzy_find(text, keywords, max_dist=2):
    for kw in keywords:
        kw_len = len(kw)
        if kw_len < 4:
            if kw in text: return True
            continue
        if kw in text: return True
        for start in range(len(text) - kw_len + max_dist + 1):
            if start < 0: continue
            for win_len in range(max(kw_len - max_dist, 3), kw_len + max_dist + 1):
                end = start + win_len
                if end > len(text): break
                if _levenshtein(text[start:end], kw) <= max_dist: return True
    return False


def _check_trigger_exact(text, cfg):
    has_pmp = any(k in text for k in cfg.KW_PMP) and any(c in text for c in cfg.PMP_CONFIRM)
    if has_pmp: return True, "PMP"
    if any(k in text for k in cfg.KW_VACCINES): return True, "VAC"
    if any(k in text for k in cfg.KW_TABLETS): return True, "TAB"
    return False, ""


def _check_trigger_fuzzy(text, cfg):
    if _fuzzy_find(text, cfg.FUZZY_CORE_PMP, 2):
        for c in cfg.PMP_CONFIRM:
            if c in text: return True, "PMP"
    if _fuzzy_find(text, cfg.FUZZY_CORE_VACCINES, 2): return True, "VAC"
    if _fuzzy_find(text, cfg.FUZZY_CORE_TABLETS, 2): return True, "TAB"
    return False, ""


TRANSLIT_MAP = {
    # Вакцины
    "baklnh": "вакцин",
    "bakuih": "вакцин",
    "vakc": "вакцин",
    "baklnhy": "вакцину",
    "baknhy": "вакцину",
    "vaktsn": "вакцин",
    "вакц": "вакцин",

    # Таблетки
    "tabletk": "таблетк",
    "tablet": "таблет",
    "ta6teleok": "таблеток",
    "ta6let": "таблет",

    # Лекарства/Препараты
    "lekarst": "лекарств",
    "nekapctb": "лекарств",
    "npenapat": "препарат",
    "preparat": "препарат",
    "nekapctbehhbi": "лекарственны",
    "medukami": "медикам",
    "medikament": "медикамент",

    # ПМП
    "пмп": "пмп",
    "pmp": "пмп",
    "nмn": "пмп",
    "pmп": "пмп",
    "пмn": "пмп",

    # Выдал/Получил
    "vydal": "выдал",
    "poluchil": "получил",
    "bыдaл": "выдал",
    "пoлyчил": "получил",
    "b3an": "взял",
    "b3ял": "взял",

    # Аптечка
    "aptechk": "аптечк",
    "anteчk": "аптечк",

    # Больницы
    "elsh": "elsh",
    "sandy": "sandy",
    "paleto": "paleto",
    "3nш": "элш",
    "caнди": "санди",
    "naneto": "палето",
}


def _check_trigger_with_translit(text, cfg):
    """Проверяет текст на наличие ключевых слов с учётом транслита."""
    text = text.lower()

    # Сначала проверяем обычные ключевые слова
    if any(kw in text for kw in cfg.KW_VACCINES):
        return True, "VAC"
    if any(kw in text for kw in cfg.KW_TABLETS):
        return True, "TAB"
    if any(kw in text for kw in cfg.KW_PMP):
        if any(c in text for c in cfg.PMP_CONFIRM):
            return True, "PMP"

    # Проверяем транслит
    for translit, original in TRANSLIT_MAP.items():
        if translit in text:
            # Определяем категорию по оригиналу
            if original in ["вакцин", "вакцину"]:
                return True, "VAC"
            elif original in ["таблетк", "таблет"]:
                return True, "TAB"
            elif original in ["пмп"]:
                # Проверяем подтверждение для ПМП
                pmp_confirms = ["выдал", "получил", "взял", "vydal", "poluchil", "b3an"]
                if any(c in text for c in pmp_confirms):
                    return True, "PMP"
            elif original in ["лекарств", "препарат", "медикамент", "аптечк"]:
                return True, "TAB"  # Лекарства = таблетки

    return False, ""


def find_trigger(ctx, diag=None, trigger_db=None):
    def lg(m):
        if diag: diag.append(m)
        print(m)

    cfg = ctx.cfg

    # ===== ТЕСТ: Сканируем всё изображение =====
    lg(f"  [ТЕСТ] Сканирую всё изображение {ctx.w}x{ctx.h}")
    try:
        full_img = ctx.img
        t_full, conf_full = _ocr.read(full_img, mc=0.05, mh=3, ml=2)
        lg(f"  [ТЕСТ] OCR результат: '{t_full[:200] if t_full else 'ПУСТО'}'")

        # Проверяем ключевые слова прямо в полном тексте
        if t_full:
            t_lower = t_full.lower()
            # Ищем ключевые слова
            if any(kw in t_lower for kw in ["лекарств", "препарат", "nekapctb", "npenapat", "lekarst", "preparat"]):
                lg(f"  [ТЕСТ] ✓ Найдено: лекарство/препарат → TAB")
                return True, "TAB", [t_full]
            if any(kw in t_lower for kw in ["вакцин", "vakc", "bakuih", "прививк"]):
                lg(f"  [ТЕСТ] ✓ Найдено: вакцина → VAC")
                return True, "VAC", [t_full]
            if any(kw in t_lower for kw in ["реаним", "reanim", "resuscitat", "спасен", "спасён"]):
                lg(f"  [ТЕСТ] ✓ Найдено: реанимация → PMP")
                return True, "PMP", [t_full]
            if any(kw in t_lower for kw in ["вылечил", "вылечен", "лечил", "лечен", "вылеч"]):
                lg(f"  [ТЕСТ] ✓ Найдено: вылечил → TAB")
                return True, "TAB", [t_full]
            if any(kw in t_lower for kw in ["таблетк", "таблет", "tabletk", "tablet"]):
                lg(f"  [ТЕСТ] ✓ Найдено: таблетки → TAB")
                return True, "TAB", [t_full]
    except Exception as e:
        lg(f"  [ТЕСТ] Ошибка OCR: {e}")
    # ===== КОНЕЦ ТЕСТА =====

    all_texts = []
    seen_texts = set()
    trigger_found = False
    trigger_cat = ""
    MAX_OCR_ROIS = 3

    scan_rois = list(cfg.CHAT_SCAN_ROIS)
    chat_roi = ctx.detect_chat_area(diag)
    if chat_roi:
        scan_rois.insert(0, chat_roi)

    lg(f"  [триг] Размер изображения: {ctx.w}x{ctx.h}")
    lg(f"  [триг] Масштаб: sx={ctx.sx:.2f} sy={ctx.sy:.2f}")
    lg(f"  [триг] Проверяю {len(scan_rois)} областей")

    rois_with_ocr = 0
    for i, (rx, ry, rw, rh) in enumerate(scan_rois):
        if trigger_found or rois_with_ocr >= MAX_OCR_ROIS:
            break

        roi = ctx.crop(rx, ry, rw, rh)
        if roi is None:
            continue

        lg(f"  [триг] roi{i} ({rx},{ry},{rw},{rh}) размер={roi.shape}")

        gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        if float(np.std(gray_roi)) < 8:
            continue
        if not _ocr.has_text_region(gray_roi, 1):
            continue

        rois_with_ocr += 1
        lg(f"  [триг] roi{i} - запускаю OCR...")

        h, w = roi.shape[:2]
        if w > 600:
            scale = 600 / w
            roi = cv2.resize(roi, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)

        for vi, var in enumerate(_generate_ocr_variants_fast(roi, cfg)):
            if trigger_found or vi >= 2:
                break

            t, conf = _ocr.read(var, mc=0.10, mh=3, ml=2)
            if not t or len(t) < 3:
                continue

            t_clean = re.sub(r'\s+', ' ', t.lower().strip())
            if t_clean in seen_texts:
                continue
            seen_texts.add(t_clean)
            all_texts.append(t_clean)

            lg(f"  [триг] roi{i}/v{vi} conf={conf:.2f}: '{t_clean[:60]}'")

            found, cat = _check_trigger_with_translit(t_clean, cfg)
            if found:
                trigger_found = True
                trigger_cat = cat
                lg(f"  [триг] ✓ найден через транслит: {cat}")
                break

            found, cat = _check_trigger_exact(t_clean, cfg)
            if found:
                trigger_found = True
                trigger_cat = cat
                break

            found_f, cat_f = _check_trigger_fuzzy(t_clean, cfg)
            if found_f:
                trigger_found = True
                trigger_cat = cat_f
                break

    if not all_texts:
        if trigger_db:
            db_cat, db_conf, db_words = predict_cat_from_db(trigger_db, [])
            if db_cat and db_conf >= 0.6:
                lg(f"  [триг_бд] пусто но БД: {db_cat} ({db_conf:.2f})")
        return False, "", all_texts

    comb = " ".join(all_texts)
    if any(r in comb for r in cfg.KW_REJECT):
        return False, "", all_texts
    if trigger_found:
        return True, trigger_cat, all_texts

    found_tr, cat_tr = _check_trigger_with_translit(comb, cfg)
    if found_tr:
        return True, cat_tr, all_texts

    found2, cat2 = _check_trigger_exact(comb, cfg)
    if found2:
        return True, cat2, all_texts
    found3, cat3 = _check_trigger_fuzzy(comb, cfg)
    if found3:
        return True, cat3, all_texts

    if trigger_db and all_texts:
        db_cat, db_conf, db_words = predict_cat_from_db(trigger_db, all_texts)
        if db_cat and db_conf >= 0.5:
            lg(f"  [триг_бд] {db_cat} conf={db_conf:.2f}")
            return True, db_cat, all_texts

    if any(r in comb for r in cfg.KW_REFUSE):
        return False, "", all_texts

    return False, "", all_texts

# ═══════════════════════════════════════════
#  ИЗВЛЕЧЕНИЕ ПРИЗНАКОВ
# ═══════════════════════════════════════════
def extract_features(ctx, diag=None) -> dict:
    def lg(m):
        if diag: diag.append(m)

    cfg = ctx.cfg

    fl = ctx.crop_hsv_small(*cfg.FLOOR)
    wl = ctx.crop_hsv_small(*cfg.WALL_L)
    wr_h = ctx.crop_hsv_small(*cfg.WALL_R)
    ct = ctx.crop_hsv_small(*cfg.CEILING)
    hz = ctx.crop_hsv_small(*cfg.HORIZON)
    mm = ctx.crop_hsv_small(*cfg.MINIMAP)
    fl_c = ctx.crop_hsv_small(*cfg.FLOOR_CENTER)
    wc = ctx.crop_hsv_small(*cfg.WALL_CENTER)
    bed = ctx.crop_hsv_small(*cfg.BED_AREA)

    upper_l = ctx.crop_hsv_small(30, 50, 300, 300)
    upper_r = ctx.crop_hsv_small(1590, 50, 300, 300)
    lower_l = ctx.crop_hsv_small(30, 650, 300, 300)
    lower_r = ctx.crop_hsv_small(1590, 650, 300, 300)
    center = ctx.crop_hsv_small(600, 300, 720, 480)

    def rs(z, lo, hi):
        if z is None or z.size == 0: return 0.
        m = cv2.inRange(z, np.array(lo, _U8), np.array(hi, _U8))
        t = z.shape[0] * z.shape[1]
        return cv2.countNonZero(m) / t if t else 0.

    def rs_multi(zones, lo, hi):
        vals = [rs(z, lo, hi) for z in zones if z is not None]
        return sum(vals) / len(vals) if vals else 0.

    def mean_hsv(z):
        if z is None or z.size == 0: return 0., 0., 0.
        return float(z[:, :, 0].mean()), float(z[:, :, 1].mean()), float(z[:, :, 2].mean())

    def std_hsv(z):
        if z is None or z.size == 0: return 0., 0., 0.
        return float(z[:, :, 0].std()), float(z[:, :, 1].std()), float(z[:, :, 2].std())

    elsh_floor = rs_multi([fl, fl_c], cfg.ELSH_FLOOR_LO, cfg.ELSH_FLOOR_HI)
    elsh_wall_or = rs_multi([wl, wr_h, wc], cfg.ELSH_WALL_ORANGE_LO, cfg.ELSH_WALL_ORANGE_HI)
    elsh_beds = rs(bed, cfg.ELSH_BED_LO, cfg.ELSH_BED_HI) if bed is not None else 0.
    elsh_clothes = rs(bed, cfg.ELSH_CLOTHES_LO, cfg.ELSH_CLOTHES_HI) if bed is not None else 0.
    elsh_lamp = rs(ct, *cfg.ELSH_LAMP)

    paleto_floor = rs_multi([fl, fl_c], cfg.PALETO_FLOOR_LO, cfg.PALETO_FLOOR_HI)
    paleto_wall_gray = rs_multi([wl, wr_h, wc], cfg.PALETO_WALL_GRAY_LO, cfg.PALETO_WALL_GRAY_HI)
    paleto_wall_dark = rs_multi([wl, wr_h, wc], cfg.PALETO_WALL_DARK_LO, cfg.PALETO_WALL_DARK_HI)
    paleto_wall_blue = rs_multi([wl, wr_h, wc], cfg.PALETO_WALL_BLUE_LO, cfg.PALETO_WALL_BLUE_HI)
    paleto_sky = rs(hz, *cfg.PALETO_SKY)

    sandy_floor = rs_multi([fl, fl_c], cfg.SANDY_FLOOR_LO, cfg.SANDY_FLOOR_HI)
    sandy_wall = rs_multi([wl, wr_h, wc], cfg.SANDY_WALL_LO, cfg.SANDY_WALL_HI)
    sandy_floor_br = rs_multi([fl, fl_c], cfg.SANDY_FLOOR_BROWN_LO, cfg.SANDY_FLOOR_BROWN_HI)
    sandy_door = rs_multi([wl, wr_h], cfg.SANDY_DOOR_LO, cfg.SANDY_DOOR_HI)
    sandy_mm = rs(mm, *cfg.SANDY_MAP)

    fh, fs, fv = mean_hsv(fl)
    wlh, wls, wlv = mean_hsv(wl)
    wrh, wrs, wrv = mean_hsv(wr_h)
    cth, cts, ctv = mean_hsv(ct)
    ceh, ces, cev = mean_hsv(center)
    mmh, mms, mmv = mean_hsv(mm)
    fsh, fss, fsv = std_hsv(fl)
    wsh, wss, wsv = std_hsv(wl)
    ul_h, ul_s, ul_v = mean_hsv(upper_l)
    ur_h, ur_s, ur_v = mean_hsv(upper_r)
    ll_h, ll_s, ll_v = mean_hsv(lower_l)
    lr_h, lr_s, lr_v = mean_hsv(lower_r)

    feats = {
        "elsh_floor": round(elsh_floor, 6), "elsh_wall_or": round(elsh_wall_or, 6),
        "elsh_beds": round(elsh_beds, 6), "elsh_clothes": round(elsh_clothes, 6),
        "elsh_lamp": round(elsh_lamp, 6),
        "paleto_floor": round(paleto_floor, 6), "paleto_wall_gray": round(paleto_wall_gray, 6),
        "paleto_wall_dark": round(paleto_wall_dark, 6), "paleto_wall_blue": round(paleto_wall_blue, 6),
        "paleto_sky": round(paleto_sky, 6),
        "sandy_floor": round(sandy_floor, 6), "sandy_wall": round(sandy_wall, 6),
        "sandy_floor_br": round(sandy_floor_br, 6), "sandy_door": round(sandy_door, 6),
        "sandy_mm": round(sandy_mm, 6),
        "floor_h": round(fh, 2), "floor_s": round(fs, 2), "floor_v": round(fv, 2),
        "wall_l_h": round(wlh, 2), "wall_l_s": round(wls, 2), "wall_l_v": round(wlv, 2),
        "wall_r_h": round(wrh, 2), "wall_r_s": round(wrs, 2), "wall_r_v": round(wrv, 2),
        "ceiling_h": round(cth, 2), "ceiling_s": round(cts, 2), "ceiling_v": round(ctv, 2),
        "center_h": round(ceh, 2), "center_s": round(ces, 2), "center_v": round(cev, 2),
        "minimap_h": round(mmh, 2), "minimap_s": round(mms, 2), "minimap_v": round(mmv, 2),
        "floor_std_h": round(fsh, 2), "floor_std_s": round(fss, 2), "floor_std_v": round(fsv, 2),
        "wall_std_h": round(wsh, 2), "wall_std_s": round(wss, 2), "wall_std_v": round(wsv, 2),
        "corner_ul_h": round(ul_h, 2), "corner_ul_s": round(ul_s, 2), "corner_ul_v": round(ul_v, 2),
        "corner_ur_h": round(ur_h, 2), "corner_ur_s": round(ur_s, 2), "corner_ur_v": round(ur_v, 2),
        "corner_ll_h": round(ll_h, 2), "corner_ll_s": round(ll_s, 2), "corner_ll_v": round(ll_v, 2),
        "corner_lr_h": round(lr_h, 2), "corner_lr_s": round(lr_s, 2), "corner_lr_v": round(lr_v, 2),
        "img_w": ctx.w, "img_h": ctx.h,
    }

    lg(f"  [признаки] ELSH: пол={elsh_floor:.4f} ст_ор={elsh_wall_or:.4f} кров={elsh_beds:.4f} "
       f"одеж={elsh_clothes:.4f} ламп={elsh_lamp:.4f}")
    lg(f"  [признаки] PALETO: пол={paleto_floor:.4f} ст_тём={paleto_wall_dark:.4f} "
       f"ст_син={paleto_wall_blue:.4f} небо={paleto_sky:.4f}")
    lg(f"  [признаки] SANDY: пол={sandy_floor:.4f} ст={sandy_wall:.4f} "
       f"дверь={sandy_door:.4f} карта={sandy_mm:.4f}")
    return feats


# ═══════════════════════════════════════════
#  КЛАССИЧЕСКИЙ ЦВЕТОВОЙ АНАЛИЗ
#  (обновлён по реальным данным ELSH/Paleto/Sandy)
# ═══════════════════════════════════════════
@dataclass
class CR:
    elsh: float = 0.;
    sandy: float = 0.;
    paleto: float = 0.
    winner: str = "Unsorted";
    conf: float = 0.
    d: Dict[str, float] = field(default_factory=dict)


def color_analyze_classic(ctx, features: dict, diag=None) -> CR:
    """
    Правила по реальным данным:

    ELSH:
      - elsh_beds=0.0004–0.54, elsh_clothes=0.001–0.078
      - elsh_lamp=0–0.238 (сильный сигнал)
      - floor_h=40–105, floor_v>90
      - paleto_wall_dark/blue могут быть высокими — это АРТЕФАКТ у ELSH!
      - ГЛАВНЫЙ признак: elsh_beds или elsh_lamp высокие

    PALETO:
      - paleto_floor=0.19–0.72 (ГЛАВНЫЙ)
      - paleto_wall_dark=0.20–0.36 (ГЛАВНЫЙ)
      - floor_v=70–110 (тёмный пол)
      - elsh_beds < 0.01 (отличие от ELSH)

    SANDY:
      - sandy_floor=0.45–0.76 (ГЛАВНЫЙ)
      - sandy_door=0.15–0.33 (уникальный)
      - floor_h=18–48, floor_s>60
    """

    def lg(m):
        if diag: diag.append(m)

    cfg = ctx.cfg;
    r = CR()
    ef = features

    elsh_floor = ef["elsh_floor"]
    elsh_wall_or = ef["elsh_wall_or"]
    elsh_beds = ef["elsh_beds"]
    elsh_clothes = ef["elsh_clothes"]
    lamp = ef["elsh_lamp"]

    paleto_floor = ef["paleto_floor"]
    paleto_wall_dark = ef["paleto_wall_dark"]
    paleto_wall_blue = ef["paleto_wall_blue"]
    psky = ef["paleto_sky"]

    sandy_floor = ef["sandy_floor"]
    sandy_wall = ef["sandy_wall"]
    sandy_floor_br = ef["sandy_floor_br"]
    sandy_door = ef["sandy_door"]
    smm = ef["sandy_mm"]

    floor_h = ef.get("floor_h", 0)
    floor_s = ef.get("floor_s", 0)
    floor_v = ef.get("floor_v", 0)
    center_s = ef.get("center_s", 0)
    wall_l_s = ef.get("wall_l_s", 0)

    e_score = 0.
    s_score = 0.
    p_score = 0.

    # ════════════════════════════════════════
    #  ШАГ 1: Вычисляем "сырые" ELSH очки
    #  (до применения подавления)
    # ════════════════════════════════════════
    elsh_raw = 0.

    # Кровати — самый надёжный признак ELSH
    # Видели: 0.0004–0.54 у ELSH, <0.07 у Paleto/Sandy
    if elsh_beds >= 0.002:
        elsh_raw += elsh_beds * 8.0
        lg(f"  [E] кровати={elsh_beds:.4f} +{elsh_beds * 8:.4f}")

    # Лампа — редкий но очень сильный
    # Видели: 0.070576 у ELSH, ~0 у Paleto/Sandy
    if lamp >= 0.005:
        elsh_raw += lamp * 10.0 + 0.3
        lg(f"  [E] лампа={lamp:.4f} +{lamp * 10 + 0.3:.4f}")

    # Одежда
    if elsh_clothes >= 0.001:
        elsh_raw += elsh_clothes * 6.0
        lg(f"  [E] одежда={elsh_clothes:.4f} +{elsh_clothes * 6:.4f}")

    # Пол ELSH
    if elsh_floor >= 0.001:
        elsh_raw += elsh_floor * 3.0

    # Оранжевые стены — только если нет Sandy пола
    if elsh_wall_or >= 0.05 and sandy_floor < 0.20:
        elsh_raw += elsh_wall_or * 3.0
        if elsh_wall_or >= 0.10:
            elsh_raw += 0.2

    # HSV пол: ELSH зелёный H=40–105, V>90
    if 40 <= floor_h <= 110 and floor_v >= 90:
        elsh_raw += 0.06

    # Насыщенность центра
    if center_s >= 30:
        elsh_raw += center_s / 1000.0

    # ════════════════════════════════════════
    #  ШАГ 2: Вычисляем "сырые" PALETO очки
    # ════════════════════════════════════════
    paleto_raw = 0.

    if paleto_floor >= 0.04:
        paleto_raw += paleto_floor * 10.0
        lg(f"  [P] пол={paleto_floor:.4f} +{paleto_floor * 10:.4f}")

    if paleto_wall_dark >= 0.03 and paleto_floor >= 0.03:
        paleto_raw += paleto_wall_dark * 9.0
        lg(f"  [P] ст_тём={paleto_wall_dark:.4f} +{paleto_wall_dark * 9:.4f}")

    if paleto_wall_blue >= 0.02 and paleto_floor >= 0.03:
        paleto_raw += paleto_wall_blue * 4.0
        lg(f"  [P] ст_синий={paleto_wall_blue:.4f} +{paleto_wall_blue * 4:.4f}")

    if 55 <= floor_h <= 110 and floor_v <= 115 and paleto_floor >= 0.03:
        paleto_raw += 0.15
        lg(f"  [P] HSV пол тёмный H={floor_h:.0f} V={floor_v:.0f} +0.15")

    # ════════════════════════════════════════
    #  ШАГ 3: Вычисляем "сырые" SANDY очки
    # ════════════════════════════════════════
    sandy_raw = 0.

    if sandy_floor >= 0.03:
        sandy_raw += sandy_floor * 10.0
        lg(f"  [S] пол={sandy_floor:.4f} +{sandy_floor * 10:.4f}")

    if sandy_door >= 0.01:
        sandy_raw += sandy_door * 12.0
        lg(f"  [S] дверь={sandy_door:.4f} +{sandy_door * 12:.4f}")

    if floor_s >= 45:
        sandy_raw += 0.30
        lg(f"  [S] высокая насыщенность пола S={floor_s:.0f} +0.30")

    if 18 <= floor_h <= 48 and floor_s >= 45:
        sandy_raw += 0.20
        lg(f"  [S] HSV пол тёплый H={floor_h:.0f} S={floor_s:.0f} +0.20")

    if sandy_floor_br >= 0.015:
        sandy_raw += sandy_floor_br * 3.0

    if smm >= cfg.THR_SANDY_MAP:
        sandy_raw += smm * cfg.W_MM

    # sandy_wall — только если нет Paleto/ELSH кроватей
    if sandy_wall >= cfg.THR_SANDY_WALL_BEIGE and paleto_floor < 0.05 and elsh_beds < 0.002:
        sandy_raw += sandy_wall * 0.5

    # ════════════════════════════════════════
    #  ШАГ 4: Применяем логику приоритетов
    # ════════════════════════════════════════

    # КЛЮЧЕВОЕ ПРАВИЛО:
    # Если elsh_beds высокий (>0.01) — это ТОЧНО ELSH, игнорируем Paleto/Sandy
    # Видели: ELSH с elsh_beds=0.54 определялось как Paleto — это баг!
    ELSH_BEDS_STRONG = 0.100  # порог "сильного" сигнала кроватей
    ELSH_LAMP_STRONG = 0.050  # порог "сильного" сигнала лампы

    is_elsh_strong = (
            (elsh_beds >= ELSH_BEDS_STRONG or lamp >= ELSH_LAMP_STRONG)
            and sandy_floor < 0.03
            and sandy_door < 0.01
    )

    if is_elsh_strong:
        # ELSH доминирует — подавляем Paleto и Sandy
        e_score = elsh_raw
        p_score = paleto_raw * 0.05  # почти обнуляем Paleto
        s_score = sandy_raw * 0.05  # почти обнуляем Sandy
        lg(f"  [логика] ELSH доминирует (beds={elsh_beds:.4f} lamp={lamp:.4f})")
    else:
        # Обычная логика — Paleto и Sandy могут выиграть
        e_score = elsh_raw

        if paleto_floor >= 0.04:
            e_score = elsh_raw * 0.1
            lg(f"  [логика] Paleto подавляет ELSH (pFloor={paleto_floor:.4f})")

        if sandy_floor >= 0.03:
            e_score = elsh_raw * 0.2
            lg(f"  [логика] Sandy подавляет ELSH (sFloor={sandy_floor:.4f})")

        p_score = paleto_raw
        s_score = sandy_raw

    # Минимум для ELSH если хоть что-то нашли
    if e_score > 0 and e_score < 0.02:
        e_score = 0.02

    r.elsh = min(e_score, 1.0)
    r.sandy = max(s_score, 0.0)
    r.paleto = max(p_score, 0.0)
    r.d = dict(features)

    lg(f"  [скоры] E={r.elsh:.4f} S={r.sandy:.4f} P={r.paleto:.4f}")

    sc2 = {cfg.F_ELSH: r.elsh, cfg.F_SANDY: r.sandy, cfg.F_PALETO: r.paleto}
    b_key = max(sc2, key=sc2.get)
    bv = sc2[b_key]
    vs = sorted(sc2.values(), reverse=True)
    s2v = vs[1] if len(vs) > 1 else 0

    if bv >= 0.003:
        r.winner = b_key
        r.conf = bv - s2v
    else:
        r.winner = cfg.F_UNK
        r.conf = 0

    lg(f"  [классика] → {r.winner} (уверенность={r.conf:.4f})")
    return r


# ═══════════════════════════════════════════
#  КЛАССЫ РЕЗУЛЬТАТОВ
# ═══════════════════════════════════════════
class Cat(str, Enum):
    TAB = "Таблетки";
    VAC = "Вакцины";
    PMP = "ПМП";
    UNK = "Неизвестно"


class Hosp(str, Enum):
    ELSH = "ELSH";
    SANDY = "Sandy Shores";
    PALETO = "Paleto Bay";
    UNK = "Неизвестно"


@dataclass
class Result:
    fp: Path;
    cat: Cat = Cat.UNK;
    hosp: Hosp = Hosp.UNK;
    night: bool = False
    conf: float = 0.;
    method: str = "";
    err: Optional[str] = None;
    ok: bool = False
    bodycam: bool = False;
    bodycam_ratio: float = 0.;
    bc_inherited: bool = False
    diag: List[str] = field(default_factory=list)
    color_detail: Dict[str, float] = field(default_factory=dict)
    ocr_texts: List[str] = field(default_factory=list)
    features: Dict[str, float] = field(default_factory=dict)

    @property
    def folder(s):
        if s.cat == Cat.PMP:
            # ПМП — определяем город/пригород
            if s.hosp == Hosp.ELSH:
                district = "Город"
            elif s.hosp in (Hosp.SANDY, Hosp.PALETO):
                district = "Пригород"
            else:
                district = "Неизвестно"
            base = f"ПМП - {district}"
            return base + (" [НОЧЬ]" if s.night else "")

        cat_names = {Cat.TAB: "Таблетки", Cat.VAC: "Вакцины"}
        cn = cat_names.get(s.cat, "Неизвестно")
        if s.hosp != Hosp.UNK:
            b = f"{cn} - {s.hosp.value}"
        else:
            b = cn
        return b + (" [НОЧЬ]" if s.night else "")


# ═══════════════════════════════════════════
#  АНАЛИЗАТОР
# ═══════════════════════════════════════════
class Analyzer:
    def __init__(s, cfg, require_bodycam=True, location_db=None, trigger_db=None):
        s.cfg = cfg
        s.require_bodycam = require_bodycam
        s._c = LRUCache(_CACHE_MAX)
        s._bts = [];
        s._btl = threading.Lock()
        s.location_db = location_db if location_db is not None else load_location_db()
        s.trigger_db = trigger_db if trigger_db is not None else load_trigger_db()

    def _rbc(s, ts):
        if ts is None: return
        with s._btl: bisect.insort(s._bts, ts)

    def _cbc(s, ts, w=GROUP_BC_WINDOW):
        if ts is None: return False
        with s._btl:
            if not s._bts: return False
            idx = bisect.bisect_left(s._bts, ts)
            for i in (idx - 1, idx):
                if 0 <= i < len(s._bts):
                    if abs(s._bts[i] - ts) <= w: return True
        return False

    def run(s, fp, wd=False):
        fv = _fh(fp)
        if not wd:
            c = s._c.get(fv)
            if c is not None:
                return Result(fp=fp, cat=c.cat, hosp=c.hosp, night=c.night, conf=c.conf,
                              method=c.method + "к", ok=c.ok, err=c.err, bodycam=c.bodycam,
                              bodycam_ratio=c.bodycam_ratio, bc_inherited=c.bc_inherited)
        r = s._do(fp, wd, fv);
        s._c.put(fv, r);
        return r

    def _do(s, fp, dg=False, fv=None):
        r = Result(fp=fp)
        diag = r.diag if dg else None

        def lg(m):
            if diag is not None: diag.append(m)

        img = _ld(fp)
        if img is None: r.err = "ошибка загрузки"; return r
        ctx = ImageContext(img, s.cfg)
        if fv and not dg:
            cached_texts, cached_cat = _ocr_disk_cache.get(fv)
            if cached_texts and cached_cat:
                cat_map = {"TAB": Cat.TAB, "VAC": Cat.VAC, "PMP": Cat.PMP}
                if cached_cat in cat_map:
                    r.cat = cat_map[cached_cat]
                    r.ocr_texts = cached_texts
                    lg(f"  [кэш] {cached_cat} из дискового кэша")
        ts = _extract_ts(fp)

        # 1. БОДИ-КАМ
        bc, bcr = check_bodycam(ctx, diag)
        r.bodycam = bc;
        r.bodycam_ratio = bcr
        if bc:
            s._rbc(ts)
        elif s.require_bodycam:
            if s._cbc(ts):
                r.bodycam = True;
                r.bc_inherited = True;
                r.bodycam_ratio = .001
            else:
                r.err = "Нет боди-кам";
                return r

        # 2. ТРИГГЕР
        t0 = time.monotonic()
        found, cat_code, txts = find_trigger(ctx, diag, trigger_db=s.trigger_db)
        dt = time.monotonic() - t0
        r.ocr_texts = txts
        lg(f"  [триг] найден={found} кат='{cat_code}' ({dt * 1000:.0f}мс)")

        if not found:
            r.err = "Нет триггера"
            if r.bc_inherited: r.bodycam = False; r.bc_inherited = False
            return r

        cat_map = {"TAB": Cat.TAB, "VAC": Cat.VAC, "PMP": Cat.PMP}
        r.cat = cat_map.get(cat_code, Cat.TAB)

        # 3. ПРИЗНАКИ — извлекаем для ВСЕХ категорий (включая ПМП)
        feats = extract_features(ctx, diag)
        r.features = feats
        r.color_detail = feats

        # 4. ЛОКАЦИЯ — определяем для ВСЕХ (ПМП нужна для город/пригород)
        hosp, method = s._determine_location(ctx, feats, diag)
        r.hosp = hosp
        r.method = method

        if r.cat == Cat.PMP:
            if r.hosp == Hosp.ELSH:
                lg("  [результат] ПМП - Город")
            elif r.hosp in (Hosp.SANDY, Hosp.PALETO):
                lg(f"  [результат] ПМП - Пригород ({r.hosp.value})")
            else:
                lg("  [результат] ПМП - район неизвестен")
        else:
            lg(f"  [результат] {r.cat.value} | {r.hosp.value} | {r.method}")

        r.night = s._nt(ctx)
        r.ok = True
        return r

    def _determine_location(s, ctx, feats, diag=None) -> Tuple[Hosp, str]:
        def lg(m):
            if diag: diag.append(m)

        cfg = s.cfg
        hm = {cfg.F_ELSH: Hosp.ELSH, cfg.F_SANDY: Hosp.SANDY, cfg.F_PALETO: Hosp.PALETO}

        db_sample_count = len(s.location_db.get("samples", []))
        db_loc_counts = {}
        for sample in s.location_db.get("samples", []):
            loc = sample.get("location", "")
            db_loc_counts[loc] = db_loc_counts.get(loc, 0) + 1

        has_enough_data = (
                db_sample_count >= cfg.MIN_DB_SAMPLES and
                len(db_loc_counts) >= 1 and
                any(v >= 2 for v in db_loc_counts.values())
        )

        if has_enough_data:
            pred_loc, pred_conf, pred_details = predict_location_from_db(s.location_db, feats)
            lg(f"  [бд] предсказание: {pred_loc} (уверенность={pred_conf:.4f})")
            if "scores" in pred_details:
                for loc_name, sc in pred_details["scores"].items():
                    lg(f"    {loc_name}: {sc:.4f}")
            if pred_conf >= cfg.THR_DB_CONFIDENCE and pred_loc != "Unsorted":
                hosp = hm.get(pred_loc, Hosp.UNK)
                if pred_conf < 0.15:
                    ocr_hosp = s._oh(ctx, diag)
                    if ocr_hosp != Hosp.UNK:
                        return ocr_hosp, "бд+ocr"
                return hosp, f"бд(д={pred_conf:.3f})"

        cr = color_analyze_classic(ctx, feats, diag)
        if cr.winner != cfg.F_UNK and cr.conf >= cfg.THR_SKIP_OCR:
            return hm.get(cr.winner, Hosp.UNK), "цвет"
        elif cr.winner != cfg.F_UNK:
            oh = s._oh(ctx, diag)
            hosp = oh if oh != Hosp.UNK else hm.get(cr.winner, Hosp.UNK)
            return hosp, "ocr" if oh != Hosp.UNK else "цвет_сл"
        else:
            oh = s._oh(ctx, diag)
            hosp = oh if oh != Hosp.UNK else Hosp.UNK
            return hosp, "ocr" if oh != Hosp.UNK else "неизв"

    def _oh(s, ctx, d=None):
        def lg(m):
            if d is not None: d.append(m)

        roi = ctx.crop(*s.cfg.MINIMAP)
        if roi is None: return Hosp.UNK
        g = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        b = cv2.resize(g, None, fx=4, fy=4, interpolation=cv2.INTER_LINEAR)
        e = cv2.createCLAHE(3., (8, 8)).apply(b)
        _, th = cv2.threshold(e, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        t, _ = _ocr.read(cv2.cvtColor(th, cv2.COLOR_GRAY2BGR), mc=.20, mh=6, ml=2)
        if not t:
            t, _ = _ocr.read(cv2.cvtColor(cv2.bitwise_not(th), cv2.COLOR_GRAY2BGR), mc=.20, mh=6, ml=2)
        if not t: return Hosp.UNK
        t = t.lower();
        lg(f"  [ocr_карта] '{t[:60]}'")
        hm = {"ELSH": Hosp.ELSH, "Sandy Shores": Hosp.SANDY, "Paleto Bay": Hosp.PALETO}
        for n, kws in s.cfg.HOSPITALS_OCR.items():
            for kw in kws:
                if kw in t: return hm.get(n, Hosp.UNK)
        return Hosp.UNK

    def _nt(s, ctx):
        roi = ctx.crop(140, 870, 170, 65)
        if roi is None or not TESSERACT_OK: return False
        g = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        b = cv2.resize(g, None, fx=3, fy=3, interpolation=cv2.INTER_LINEAR)
        _, bn = cv2.threshold(b, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        for v in (bn, cv2.bitwise_not(bn)):
            try:
                t = pytesseract.image_to_string(
                    v, config="--psm 7 --oem 1 -c tessedit_char_whitelist=0123456789:").strip()
                m = re.search(r"(\d{1,2}):(\d{2})", t)
                if m:
                    h_val = int(m.group(1))
                    if 0 <= h_val <= 23: return h_val >= s.cfg.NIGHT_START or h_val < s.cfg.NIGHT_END
            except:
                pass
        return False

    def teach(s, fp: Path, correct_location: str, log_fn=None) -> dict:
        def lg(msg, lv="default"):
            if log_fn: log_fn(msg, lv)

        img = _ld(fp)
        if img is None: lg("  Ошибка загрузки", "error"); return {}
        ctx = ImageContext(img, s.cfg)
        feats = extract_features(ctx)
        add_location_sample(s.location_db, feats, correct_location, fp.name)
        lg(f"  Добавлен: {fp.name} → {correct_location}", "success")
        lg(f"  Всего в БД: {len(s.location_db['samples'])}", "info")
        return feats


# ═══════════════════════════════════════════
#  GUI — СЕКЦИЯ
# ═══════════════════════════════════════════
class Sec(ctk.CTkFrame):
    def __init__(s, p, t, color=P["accent"], col=False, **kw):
        super().__init__(p, fg_color=P["card"], corner_radius=12, border_width=1,
                         border_color=P["border"], **kw)
        s._c = col;
        s._t = t
        s._h = ctk.CTkButton(s, text=s._tt(), anchor="w", font=ctk.CTkFont(size=11, weight="bold"),
                             fg_color="transparent", hover_color=P["entry"], text_color=color, height=36, command=s._tg)
        s._h.pack(fill="x", padx=4, pady=(2, 0))
        s._s = ctk.CTkFrame(s, height=1, fg_color=P["border"])
        s.body = ctk.CTkFrame(s, fg_color="transparent")
        if not col: s._s.pack(fill="x", padx=10); s.body.pack(fill="x", expand=False)

    def _tt(s):
        return f"  {'>' if s._c else 'v'}  {s._t}"

    def _tg(s):
        s._c = not s._c;
        s._h.configure(text=s._tt())
        if s._c:
            s.body.pack_forget(); s._s.pack_forget()
        else:
            s._s.pack(fill="x", padx=10); s.body.pack(fill="x", expand=False, pady=(0, 4))


def _icon():
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0));
    d = ImageDraw.Draw(img)
    for i in range(64):
        for j in range(64):
            r = int(15 + (i / 64) * 10);
            g = int(150 + (i / 64) * 50 + (j / 64) * 15);
            b = int(85 + (j / 64) * 40)
            cr = 16;
            ok = True
            for cd, dy, dx in [(i < cr and j < cr, cr - i, cr - j), (i < cr and j > 63 - cr, cr - i, j - (63 - cr)),
                               (i > 63 - cr and j < cr, i - (63 - cr), cr - j),
                               (i > 63 - cr and j > 63 - cr, i - (63 - cr), j - (63 - cr))]:
                if cd and dy ** 2 + dx ** 2 > cr ** 2: ok = False; break
            if ok: img.putpixel((j, i), (r, g, b, 255))
    d.rounded_rectangle([27, 12, 37, 52], radius=4, fill=(255, 255, 255, 220))
    d.rounded_rectangle([12, 27, 52, 37], radius=4, fill=(255, 255, 255, 220))
    d.ellipse([46, 4, 58, 16], fill=(232, 54, 79, 240));
    return img


class Tooltip:
    def __init__(s, widget, text, delay=500):
        s.widget = widget;
        s.text = text;
        s.delay = delay
        s.tip = None;
        s._id = None
        widget.bind("<Enter>", s._on_enter)
        widget.bind("<Leave>", s._on_leave)

    def _on_enter(s, e):
        s._id = s.widget.after(s.delay, s._show)

    def _on_leave(s, e):
        if s._id: s.widget.after_cancel(s._id); s._id = None
        s._hide()

    def _show(s):
        x = s.widget.winfo_rootx() + 20
        y = s.widget.winfo_rooty() + s.widget.winfo_height() + 5
        s.tip = tk.Toplevel(s.widget)
        s.tip.wm_overrideredirect(True)
        s.tip.wm_geometry(f"+{x}+{y}")
        frame = tk.Frame(s.tip, bg="#1a1a1a", bd=1, relief="solid",
                         highlightbackground="#333", highlightthickness=1)
        frame.pack()
        tk.Label(frame, text=s.text, bg="#1a1a1a", fg="#e0e0e0",
                 font=("Segoe UI", 9), padx=8, pady=4,
                 wraplength=300, justify="left").pack()

    def _hide(s):
        if s.tip:
            s.tip.destroy();
            s.tip = None


# ═══════════════════════════════════════════
#  ОКНО АНАЛИТИКИ
# ═══════════════════════════════════════════
class AnalyticsWindow(ctk.CTkToplevel):
    def __init__(s, parent, fp: Path, az: Analyzer, log_fn, location_db: dict):
        super().__init__(parent)
        s.title(f"Аналитика: {fp.name}")
        s.configure(fg_color=P["bg"]);
        s.transient(parent)
        s.fp = fp;
        s.az = az;
        s.log_fn = log_fn;
        s.location_db = location_db
        s.photo = None;
        s.features = {};
        s.result = None
        sw, sh = s.winfo_screenwidth(), s.winfo_screenheight()
        s.geometry(f"1100x750+{(sw - 1100) // 2}+{(sh - 750) // 2}")
        s._build()
        threading.Thread(target=s._run_analysis, daemon=True).start()

    def _build(s):
        hf = ctk.CTkFrame(s, fg_color=P["card"], corner_radius=0, height=50)
        hf.pack(fill="x");
        hf.pack_propagate(False)
        ctk.CTkLabel(hf, text="Полная аналитика скриншота",
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=P["accent"]).pack(side="left", padx=16, pady=12)
        ctk.CTkLabel(hf, text=s.fp.name,
                     font=ctk.CTkFont(size=10),
                     text_color=P["t2"]).pack(side="left", pady=12)

        mn = ctk.CTkFrame(s, fg_color="transparent")
        mn.pack(fill="both", expand=True, padx=8, pady=6)
        mn.columnconfigure(0, weight=1);
        mn.columnconfigure(1, weight=1);
        mn.rowconfigure(0, weight=1)

        # Левая панель
        lp = ctk.CTkFrame(mn, fg_color=P["card"], corner_radius=10)
        lp.grid(row=0, column=0, sticky="nsew", padx=(0, 4))

        s.img_lbl = ctk.CTkLabel(lp, text="Загрузка...",
                                 font=ctk.CTkFont(size=11), text_color=P["t2"])
        s.img_lbl.pack(padx=8, pady=8, expand=True)

        s.status_lbl = ctk.CTkLabel(lp, text="Анализирую...",
                                    font=ctk.CTkFont(size=11, weight="bold"),
                                    text_color=P["warn"])
        s.status_lbl.pack(padx=8, pady=4)

        tf = ctk.CTkFrame(lp, fg_color=P["entry"], corner_radius=8,
                          border_width=1, border_color=P["border"])
        tf.pack(fill="x", padx=8, pady=(0, 4))
        ctk.CTkLabel(tf, text="Правильная локация:",
                     font=ctk.CTkFont(size=10), text_color=P["t2"]).pack(anchor="w", padx=8, pady=(6, 0))
        s.loc_var = ctk.StringVar(value="ELSH")
        ctk.CTkOptionMenu(tf, values=["ELSH", "Sandy", "Paleto"],
                          variable=s.loc_var, width=140, height=30,
                          fg_color=P["bg"], button_color=P["gold"],
                          dropdown_fg_color=P["card"], text_color=P["text"],
                          font=ctk.CTkFont(size=11)).pack(padx=8, pady=4, anchor="w")
        ctk.CTkButton(tf, text="Обучить систему", height=34,
                      fg_color=P["accent"], hover_color=P["ah"],
                      text_color="#fff", font=ctk.CTkFont(size=11, weight="bold"),
                      command=s._teach).pack(fill="x", padx=8, pady=(0, 8))

        s.db_stat_lbl = ctk.CTkLabel(lp, text="", font=ctk.CTkFont(size=9), text_color=P["dim"])
        s.db_stat_lbl.pack(padx=8, pady=(0, 6))
        s._update_db_stat()

        # Правая панель — вкладки
        rp = ctk.CTkFrame(mn, fg_color=P["card"], corner_radius=10)
        rp.grid(row=0, column=1, sticky="nsew")
        rp.rowconfigure(0, weight=1);
        rp.columnconfigure(0, weight=1)

        tabs = ctk.CTkTabview(rp,
                              fg_color=P["card"],
                              segmented_button_fg_color=P["entry"],
                              segmented_button_selected_color=P["accent"],
                              segmented_button_selected_hover_color=P["ah"],
                              text_color=P["text"])
        tabs.pack(fill="both", expand=True, padx=4, pady=4)

        t1 = tabs.add("Признаки")
        s.feat_text = Text(t1, font=("Consolas", 9), bg=P["log"], fg=P["text"],
                           relief="flat", borderwidth=0, padx=6, pady=4, wrap="none")
        sb1 = tk.Scrollbar(t1, orient="vertical", command=s.feat_text.yview,
                           bg=P["card"], troughcolor=P["log"])
        sb1.pack(side="right", fill="y")
        s.feat_text.pack(fill="both", expand=True)
        s.feat_text.configure(yscrollcommand=sb1.set)

        t2 = tabs.add("Скоры БД")
        s.score_text = Text(t2, font=("Consolas", 9), bg=P["log"], fg=P["text"],
                            relief="flat", borderwidth=0, padx=6, pady=4, wrap="word")
        sb2 = tk.Scrollbar(t2, orient="vertical", command=s.score_text.yview,
                           bg=P["card"], troughcolor=P["log"])
        sb2.pack(side="right", fill="y")
        s.score_text.pack(fill="both", expand=True)
        s.score_text.configure(yscrollcommand=sb2.set)

        t3 = tabs.add("Диагностика")
        s.diag_text = Text(t3, font=("Consolas", 9), bg=P["log"], fg=P["text"],
                           relief="flat", borderwidth=0, padx=6, pady=4, wrap="word")
        sb3 = tk.Scrollbar(t3, orient="vertical", command=s.diag_text.yview,
                           bg=P["card"], troughcolor=P["log"])
        sb3.pack(side="right", fill="y")
        s.diag_text.pack(fill="both", expand=True)
        s.diag_text.configure(yscrollcommand=sb3.set)

        bf = ctk.CTkFrame(rp, fg_color="transparent")
        bf.pack(fill="x", padx=4, pady=(0, 4))
        ctk.CTkButton(bf, text="Копировать для анализа", height=30,
                      fg_color=P["purple"], hover_color="#C026D3",
                      text_color="#fff", font=ctk.CTkFont(size=10),
                      command=s._copy_for_analysis).pack(side="left", padx=(0, 4))
        ctk.CTkButton(bf, text="Сохранить JSON", height=30,
                      fg_color=P["entry"], hover_color=P["bh"],
                      border_width=1, border_color=P["border"],
                      text_color=P["t2"], font=ctk.CTkFont(size=10),
                      command=s._save_json).pack(side="left")

    def _update_db_stat(s):
        db = s.location_db;
        total = len(db.get("samples", []))
        by_loc = {}
        for sample in db.get("samples", []):
            loc = sample.get("location", "?")
            by_loc[loc] = by_loc.get(loc, 0) + 1
        lines = [f"БД: {total} примеров"]
        for loc, cnt in by_loc.items(): lines.append(f"  {loc}: {cnt}")
        s.db_stat_lbl.configure(text="\n".join(lines))

    def _run_analysis(s):
        try:
            pil = Image.open(s.fp)
            r = min(500 / pil.width, 280 / pil.height)
            pil = pil.resize((int(pil.width * r), int(pil.height * r)), Image.LANCZOS)
            s.photo = ImageTk.PhotoImage(pil)
            s.after(0, lambda: s.img_lbl.configure(image=s.photo, text=""))
        except:
            pass

        img = _ld(s.fp)
        if img is None:
            s.after(0, lambda: s.status_lbl.configure(text="Ошибка загрузки", text_color=P["err"]))
            return

        ctx = ImageContext(img, s.az.cfg);
        diag = []
        feats = extract_features(ctx, diag);
        s.features = feats
        r = s.az.run(s.fp, wd=True);
        s.result = r
        db_pred, db_conf, db_details = predict_location_from_db(s.location_db, feats)

        s.after(0, lambda: s._fill_features(feats))
        s.after(0, lambda: s._fill_scores(db_pred, db_conf, db_details, feats))
        s.after(0, lambda: s._fill_diag(r.diag))

        if r.ok:
            status = f"{r.cat.value} | {r.hosp.value} | {r.method}"
            s.after(0, lambda: s.status_lbl.configure(text=status, text_color=P["ok"]))
        else:
            s.after(0, lambda: s.status_lbl.configure(text=f"Ошибка: {r.err}", text_color=P["err"]))

    def _fill_features(s, feats):
        s.feat_text.delete("1.0", END)
        for tg, cl in [("elsh", P["orange"]), ("paleto", P["blue"]), ("sandy", P["gold"]),
                       ("mean", P["t2"]), ("header", P["accent"]), ("good", P["ok"]), ("dim", P["dim"])]:
            s.feat_text.tag_config(tg, foreground=cl)

        def ins(txt, tag="dim"):
            s.feat_text.insert(END, txt, tag)

        ins("══ ELSH ══\n", "header")
        for k in ["elsh_floor", "elsh_wall_or", "elsh_beds", "elsh_clothes", "elsh_lamp"]:
            v = feats.get(k, 0)
            ins(f"  {k:<22} = {v:.6f}\n", "good" if v > 0.01 else "elsh")

        ins("\n══ PALETO ══\n", "header")
        for k in ["paleto_floor", "paleto_wall_gray", "paleto_wall_dark", "paleto_wall_blue", "paleto_sky"]:
            v = feats.get(k, 0)
            ins(f"  {k:<22} = {v:.6f}\n", "good" if v > 0.10 else "paleto")

        ins("\n══ SANDY ══\n", "header")
        for k in ["sandy_floor", "sandy_wall", "sandy_floor_br", "sandy_door", "sandy_mm"]:
            v = feats.get(k, 0)
            ins(f"  {k:<22} = {v:.6f}\n", "good" if v > 0.10 else "sandy")

        ins("\n══ СРЕДНИЕ HSV ══\n", "header")
        for name, kh, ks, kv in [("Пол", "floor_h", "floor_s", "floor_v"),
                                 ("Стена Л", "wall_l_h", "wall_l_s", "wall_l_v"),
                                 ("Стена П", "wall_r_h", "wall_r_s", "wall_r_v"),
                                 ("Потолок", "ceiling_h", "ceiling_s", "ceiling_v"),
                                 ("Центр", "center_h", "center_s", "center_v"),
                                 ("Карта", "minimap_h", "minimap_s", "minimap_v")]:
            h = feats.get(kh, 0);
            sat = feats.get(ks, 0);
            v = feats.get(kv, 0)
            ins(f"  {name:<10} H={h:5.1f} S={sat:5.1f} V={v:5.1f}\n", "mean")

    def _fill_scores(s, db_pred, db_conf, db_details, feats):
        s.score_text.delete("1.0", END)
        for tg, cl in [("info", P["info"]), ("success", P["ok"]), ("header", P["accent"]),
                       ("accent", P["accent"]), ("dim", P["t2"]), ("warn", P["warn"])]:
            s.score_text.tag_config(tg, foreground=cl)

        def ins(txt, tag="dim"):
            s.score_text.insert(END, txt, tag)

        db = s.location_db;
        total = len(db.get("samples", []))
        ins(f"БД примеров: {total}\n", "info")
        ins(f"Предсказание: {db_pred} (уверенность={db_conf:.4f})\n\n", "success")

        if "scores" in db_details:
            ins("Скоры по локациям:\n", "header")
            for loc, sc in sorted(db_details["scores"].items(), key=lambda x: -x[1]):
                bar = "█" * int(sc * 20)
                ins(f"  {loc:<12} {sc:.4f} {bar}\n", "accent")

        ins("\nКол-во примеров:\n", "header")
        by_loc = {}
        for sample in db.get("samples", []):
            loc = sample.get("location", "?")
            by_loc[loc] = by_loc.get(loc, 0) + 1
        for loc, cnt in sorted(by_loc.items(), key=lambda x: -x[1]):
            ins(f"  {loc}: {cnt}\n", "dim")

        if db_pred in db.get("feature_ranges", {}):
            ins(f"\nДиапазоны {db_pred}:\n", "header")
            ranges = db["feature_ranges"][db_pred]
            for k in ["elsh_floor", "elsh_wall_or", "elsh_beds", "paleto_floor",
                      "paleto_wall_dark", "sandy_floor", "sandy_door", "sandy_mm"]:
                if k in ranges:
                    r = ranges[k];
                    cur = feats.get(k, 0)
                    ok = "✓" if r["min"] <= cur <= r["max"] else "✗"
                    ins(f"  {ok} {k:<22} [{r['min']:.4f}–{r['max']:.4f}] сред={r['mean']:.4f} | тек={cur:.4f}\n", "dim")

    def _fill_diag(s, diag_lines):
        s.diag_text.delete("1.0", END)
        for tg, cl in [("c", P["accent"]), ("t", P["info"]), ("r", P["ok"]), ("d", P["t2"]), ("e", P["err"]),
                       ("g", P["gold"])]:
            s.diag_text.tag_config(tg, foreground=cl)
        for line in diag_lines:
            if "[признаки]" in line or "[c]" in line:
                tag = "c"
            elif "[триг]" in line:
                tag = "t"
            elif "[результат]" in line:
                tag = "r"
            elif "[бд]" in line:
                tag = "g"
            elif "ошибка" in line.lower():
                tag = "e"
            else:
                tag = "d"
            s.diag_text.insert(END, line + "\n", tag)

    def _teach(s):
        correct_loc = s.loc_var.get()
        if not s.features: s.log_fn("  Дождитесь анализа", "warning"); return
        add_location_sample(s.location_db, s.features, correct_loc, s.fp.name)
        s.log_fn(f"  Обучение: {s.fp.name} → {correct_loc}", "success")
        s.log_fn(f"  Всего в БД: {len(s.location_db['samples'])}", "info")
        s._update_db_stat()
        db_pred, db_conf, db_details = predict_location_from_db(s.location_db, s.features)
        s.after(0, lambda: s._fill_scores(db_pred, db_conf, db_details, s.features))

    def _copy_for_analysis(s):
        if not s.features: return
        lines = [f"=== АНАЛИТИКА: {s.fp.name} ===",
                 f"Размер: {s.features.get('img_w', 0)}x{s.features.get('img_h', 0)}", "",
                 "--- КЛЮЧЕВЫЕ ПРИЗНАКИ ---"]
        for group, keys in [("ELSH", ["elsh_floor", "elsh_wall_or", "elsh_beds", "elsh_clothes", "elsh_lamp"]),
                            ("PALETO", ["paleto_floor", "paleto_wall_dark", "paleto_wall_blue", "paleto_sky"]),
                            ("SANDY", ["sandy_floor", "sandy_wall", "sandy_floor_br", "sandy_door", "sandy_mm"])]:
            lines.append(f"\n{group}:")
            for k in keys: lines.append(f"  {k} = {s.features.get(k, 0):.6f}")
        lines.append("\nСРЕДНИЕ HSV:")
        for zone in ["floor", "wall_l", "wall_r", "ceiling", "center"]:
            h = s.features.get(f"{zone}_h", 0);
            sat = s.features.get(f"{zone}_s", 0);
            v = s.features.get(f"{zone}_v", 0)
            lines.append(f"  {zone}: H={h:.1f} S={sat:.1f} V={v:.1f}")
        if s.result:
            lines.append(f"\nРЕЗУЛЬТАТ: {s.result.cat.value} | {s.result.hosp.value} | {s.result.method}")
        text = "\n".join(lines)
        s.clipboard_clear();
        s.clipboard_append(text)
        s.log_fn("  Скопировано", "success")

    def _save_json(s):
        if not s.features: return
        fp = filedialog.asksaveasfilename(defaultextension=".json",
                                          initialfile=f"analytics_{s.fp.stem}.json", filetypes=[("JSON", "*.json")])
        if fp:
            data = {"file": s.fp.name, "features": s.features,
                    "result": {"cat": s.result.cat.value if s.result else "",
                               "hosp": s.result.hosp.value if s.result else "",
                               "method": s.result.method if s.result else "",
                               "ok": s.result.ok if s.result else False}}
            Path(fp).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            s.log_fn(f"  Сохранено: {fp}", "success")


# ═══════════════════════════════════════════
#  ГЛАВНОЕ ОКНО
# ═══════════════════════════════════════════
class App(ctk.CTk):
    def __init__(s):
        super().__init__()
        s.title(f"Majestic RP Sorter v{APP_VERSION}")
        s.minsize(1080, 700)
        s.configure(fg_color=P["bg"])
        sw, sh = s.winfo_screenwidth(), s.winfo_screenheight()
        w = min(1200, sw - 40)
        h = sh - 80
        x = (sw - w) // 2
        y = 10
        s.geometry(f"{w}x{h}+{x}+{y}")
        try:
            s._ico = ImageTk.PhotoImage(_icon());
            s.iconphoto(True, s._ico)
        except:
            pass
        s.cfg = Config();
        s.cfg.load_thresholds()
        s.is_pro = _check_license()
        s.location_db = load_location_db()
        s.trigger_db = load_trigger_db()
        s.az = Analyzer(s.cfg, require_bodycam=True,
                        location_db=s.location_db, trigger_db=s.trigger_db)
        s.is_proc = False;
        s.skipped = [];
        s._stop = threading.Event();
        s._undo_history = []
        s.wk_var = ctk.StringVar(value="2");
        s.dry_var = ctk.BooleanVar(value=False)
        s.bc_var = ctk.BooleanVar(value=True);
        s._pf = FilePreloader()
        s._settings = load_settings()
        s._build()
        s._restore_settings()
        s._setup_log()
        threading.Thread(target=lambda: _ocr.init(s._log), daemon=True).start()
        s.protocol("WM_DELETE_WINDOW", s._on_close)
        threading.Thread(target=s._check_updates_background, daemon=True).start()

    def _on_close(s):
        s._save_current_settings()
        s.cfg.save_thresholds()
        save_location_db(s.location_db)
        save_trigger_db(s.trigger_db)
        s._pf.shutdown()
        _ocr_disk_cache.save()
        s.destroy()

    def _restore_settings(s):
        st = s._settings
        if st.get("last_input"):
            s.inp_e.delete(0, END)
            s.inp_e.insert(0, st["last_input"])
        if st.get("last_output"):
            s.out_e.delete(0, END)
            s.out_e.insert(0, st["last_output"])
        if st.get("workers"):
            s.wk_var.set(str(st["workers"]))
        if "require_bodycam" in st:
            s.bc_var.set(st["require_bodycam"])
        if "dry_run" in st:
            s.dry_var.set(st["dry_run"])
        if st.get("window_geometry"):
            try:
                s.geometry(st["window_geometry"])
            except Exception:
                pass

    def _save_current_settings(s):
        s._settings.update({
            "last_input": s.inp_e.get().strip(),
            "last_output": s.out_e.get().strip(),
            "workers": int(s.wk_var.get()),
            "require_bodycam": s.bc_var.get(),
            "dry_run": s.dry_var.get(),
            "window_geometry": s.geometry(),
        })
        save_settings(s._settings)

    def _undo_last(s):
        if not s._undo_history:
            s._log("  Нечего отменять", "warning")
            return
        src, dst = s._undo_history.pop()
        try:
            if dst.exists():
                dst.unlink()
                s._log(f"  ↩️ Отменено: {dst.name} удалён из {dst.parent.name}", "info")
        except Exception as e:
            s._log(f"  ❌ Ошибка отмены: {e}", "error")

    def _activate_pro(s):
        dialog = ctk.CTkToplevel(s)
        dialog.title("Активация PRO")
        dialog.configure(fg_color=P["bg"])
        dialog.transient(s)
        dialog.grab_set()

        sw, sh = dialog.winfo_screenwidth(), dialog.winfo_screenheight()
        dialog.geometry(f"450x240+{(sw - 450) // 2}+{(sh - 240) // 2}")
        dialog.resizable(False, False)

        ctk.CTkLabel(dialog, text="🔑 Активация PRO версии",
                     font=ctk.CTkFont(size=16, weight="bold"),
                     text_color=P["gold"]).pack(pady=(20, 10))

        ctk.CTkLabel(dialog, text="Введите ключ активации (формат: MJ-XXXX-XXXX-XXXX)",
                     font=ctk.CTkFont(size=10),
                     text_color=P["t2"]).pack(pady=(0, 10))

        key_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        key_frame.pack(fill="x", padx=20, pady=(0, 5))

        show_key = ctk.BooleanVar(value=False)

        key_entry = ctk.CTkEntry(key_frame, height=40,
                                 font=ctk.CTkFont(size=14, family="Consolas"),
                                 fg_color=P["entry"], border_color=P["border"],
                                 text_color=P["text"], placeholder_text="MJ-XXXX-XXXX-XXXX",
                                 show="●")
        key_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))

        def paste_key():
            try:
                clipboard = dialog.clipboard_get()
                key_entry.delete(0, END)
                key_entry.insert(0, clipboard.strip())
            except Exception:
                pass

        def toggle_show():
            if show_key.get():
                key_entry.configure(show="")
                show_btn.configure(text="🙈")
            else:
                key_entry.configure(show="●")
                show_btn.configure(text="👁")
            show_key.set(not show_key.get())

        ctk.CTkButton(key_frame, text="📋", width=40, height=40,
                      fg_color=P["accent"], hover_color=P["ah"],
                      text_color="#fff", font=ctk.CTkFont(size=16),
                      command=paste_key).pack(side="left", padx=(0, 5))
        Tooltip(key_frame.winfo_children()[-1], "Вставить из буфера обмена")

        show_btn = ctk.CTkButton(key_frame, text="👁", width=40, height=40,
                                 fg_color=P["entry"], hover_color=P["bh"],
                                 border_width=1, border_color=P["border"],
                                 text_color=P["text"], font=ctk.CTkFont(size=16),
                                 command=toggle_show)
        show_btn.pack(side="left")
        Tooltip(show_btn, "Показать/скрыть ключ")

        key_entry.bind("<Control-v>", lambda e: (paste_key(), "break")[1])
        key_entry.bind("<Control-V>", lambda e: (paste_key(), "break")[1])

        status_label = ctk.CTkLabel(dialog, text="",
                                    font=ctk.CTkFont(size=10),
                                    text_color=P["dim"])
        status_label.pack(pady=(5, 10))

        def do_activate():
            key = key_entry.get().strip().upper()
            if not key:
                status_label.configure(text="❌ Введите ключ", text_color=P["err"])
                return
            if not key.startswith("MJ-"):
                status_label.configure(text="❌ Ключ должен начинаться с MJ-", text_color=P["err"])
                return

            data = {"key": key}
            LICENSE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")

            if _check_license():
                s.is_pro = True
                status_label.configure(text="✅ PRO активирован!", text_color=P["ok"])
                s._log("  🔑 PRO активирован! Перезапустите программу", "success")
                _play_done_sound()
                dialog.after(1500, dialog.destroy)
            else:
                status_label.configure(text="❌ Ключ недействителен", text_color=P["err"])
                s._log("  ❌ Ключ недействителен", "error")

        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20)

        ctk.CTkButton(btn_frame, text="Отмена", height=36,
                      fg_color=P["entry"], hover_color=P["bh"],
                      border_width=1, border_color=P["border"],
                      text_color=P["t2"], font=ctk.CTkFont(size=11),
                      command=dialog.destroy).pack(side="left", fill="x", expand=True, padx=(0, 5))

        ctk.CTkButton(btn_frame, text="✅ Активировать", height=36,
                      fg_color=P["gold"], hover_color="#FFE033",
                      text_color="#1a1a1a", font=ctk.CTkFont(size=11, weight="bold"),
                      command=do_activate).pack(side="right", fill="x", expand=True, padx=(5, 0))

        key_entry.bind("<Return>", lambda e: do_activate())

        key_entry.focus_set()

    def _setup_log(s):
        (DATA_DIR / "logs").mkdir(exist_ok=True)
        logger.remove()
        tm = {"info": "info", "success": "success", "warning": "warning",
              "error": "error", "debug": "dim"}

        def sink(m): s._log(m.record["message"], tm.get(m.record["level"].name.lower(), "default"))

        logger.add(sink, level="INFO")
        logger.add(DATA_DIR / "logs" / "sorter.log", level="DEBUG", rotation="10 MB", encoding="utf-8")

    def _log(s, msg, lv="default"):
        def _i():
            s.log_t.insert(END, msg + "\n", lv)
            if s._as.get(): s.log_t.see(END)

        if threading.current_thread() is threading.main_thread():
            _i()
        else:
            s.after(0, _i)

    def _build(s):
        # ══ Шапка ══
        hd = ctk.CTkFrame(s, fg_color=P["card"], corner_radius=0, height=60)
        hd.pack(fill="x");
        hd.pack_propagate(False)
        hi = ctk.CTkFrame(hd, fg_color="transparent");
        hi.pack(fill="both", expand=True, padx=20)
        tf = ctk.CTkFrame(hi, fg_color="transparent");
        tf.pack(side="left", pady=8)
        ctk.CTkLabel(tf, text=f"Majestic RP Sorter v{APP_VERSION}",
                     font=ctk.CTkFont(size=16, weight="bold"), text_color=P["text"]).pack(anchor="w")
        ctk.CTkLabel(tf, text=f"by {APP_AUTHOR}",
                     font=ctk.CTkFont(size=9), text_color=P["dim"]).pack(anchor="w")
        rf = ctk.CTkFrame(hi, fg_color="transparent");
        rf.pack(side="right", pady=8)
        s.ocr_l = ctk.CTkLabel(rf, text="OCR...", font=ctk.CTkFont(size=9), text_color=P["warn"])
        s.ocr_l.pack(anchor="e")
        s.db_l = ctk.CTkLabel(rf, text="", font=ctk.CTkFont(size=9), text_color=P["gold"])
        s.db_l.pack(anchor="e");
        s._update_db_label()
        ctk.CTkFrame(s, height=2, corner_radius=0, fg_color=P["accent"]).pack(fill="x")

        # ══ Донат ══
        db = ctk.CTkFrame(s, fg_color=P["donate_bg"], corner_radius=0, height=60,
                          border_width=1, border_color=P["donate_border"])
        db.pack(fill="x", side="bottom");
        db.pack_propagate(False)
        di = ctk.CTkFrame(db, fg_color="transparent");
        di.pack(fill="both", expand=True, padx=20)
        dl = ctk.CTkFrame(di, fg_color="transparent");
        dl.pack(side="left", fill="y", pady=8)
        ctk.CTkLabel(dl, text=APP_AUTHOR, font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=P["orange"]).pack(anchor="w")
        dr = ctk.CTkFrame(di, fg_color="transparent");
        dr.pack(side="right", fill="y", pady=8)
        ctk.CTkButton(dr, text="Поддержать автора ❤️", width=200, height=42, fg_color=P["gold"],
                      hover_color="#FFE033", text_color="#1a1a1a",
                      font=ctk.CTkFont(size=13, weight="bold"), corner_radius=8,
                      command=lambda: webbrowser.open(APP_DONATE)).pack(side="right")

        # ══ Основная область ══
        mn = ctk.CTkFrame(s, fg_color="transparent")
        mn.pack(fill="both", expand=True, padx=8, pady=6)
        mn.columnconfigure(0, weight=0, minsize=420);
        mn.columnconfigure(1, weight=1)
        mn.rowconfigure(0, weight=1)
        lp = ctk.CTkScrollableFrame(mn, fg_color="transparent", width=410)
        lp.grid(row=0, column=0, sticky="nsew", padx=(0, 5))

        # ── Папки ──
        fc = Sec(lp, "📁 Папки");
        fc.pack(fill="x", pady=(0, 4))
        s.inp_e = s._fr(fc.body, "Входная (где лежат скриншоты)", "Выбрать папку...", s._bi)
        s.out_e = s._fr(fc.body, "Выходная (куда складывать результат)", "Выбрать папку...", s._bo)

        # ── Настройки ──
        sc2 = Sec(lp, "⚙️ Настройки", P["blue"]);
        sc2.pack(fill="x", pady=(0, 4))
        of = ctk.CTkFrame(sc2.body, fg_color="transparent");
        of.pack(fill="x", padx=12, pady=6)

        f2 = ctk.CTkFrame(of, fg_color="transparent");
        f2.pack(fill="x", pady=(0, 4))
        ctk.CTkLabel(f2, text="Потоки (больше = быстрее, но тяжелее для ПК)",
                     font=ctk.CTkFont(size=10), text_color=P["t2"]).pack(side="left")
        ctk.CTkOptionMenu(f2, values=["1", "2", "4", "8"], variable=s.wk_var, width=60, height=26,
                          fg_color=P["entry"], button_color=P["blue"],
                          dropdown_fg_color=P["card"], text_color=P["text"],
                          font=ctk.CTkFont(size=10)).pack(side="right")
        ctk.CTkButton(of, text="🔑 Активировать PRO", height=28,
                      fg_color=P["gold"], hover_color="#FFE033",
                      text_color="#1a1a1a", font=ctk.CTkFont(size=10),
                      command=s._activate_pro).pack(fill="x", pady=(4, 0))
        ctk.CTkButton(
            of,
            text="🔄 Проверить обновления",
            height=28,
            fg_color=P["blue"],
            hover_color="#2563EB",
            text_color="#fff",
            font=ctk.CTkFont(size=10),
            command=s._check_updates_manual
        ).pack(fill="x", pady=(4, 0))

        for lbl, var, clr, tip in [
            ("Требовать боди-кам", s.bc_var, P["bodycam"],
             "Если вкл — скрины без красной лампочки записи пропускаются"),
            ("Тест-режим (не копировать файлы)", s.dry_var, P["orange"],
             "Если вкл — программа покажет что сделает, но файлы не тронет"),
        ]:
            f2 = ctk.CTkFrame(of, fg_color="transparent");
            f2.pack(fill="x", pady=(0, 4))
            ctk.CTkLabel(f2, text=lbl, font=ctk.CTkFont(size=10), text_color=P["t2"]).pack(side="left")
            ctk.CTkSwitch(f2, text="", variable=var, width=42, height=20,
                          progress_color=clr, button_color=P["text"]).pack(side="right")

        # ── Инструменты ──
        ac = Sec(lp, "🛠 Инструменты", P["purple"]);
        ac.pack(fill="x", pady=(0, 4))
        ab = ctk.CTkFrame(ac.body, fg_color="transparent");
        ab.pack(fill="x", padx=12, pady=6)

        tools = [
            ("🔍 Аналитика скриншота", P["purple"], "#C026D3",
             "Детальный разбор одного скрина: что видит система, какие цвета, OCR текст",
             s._open_analytics),
            ("📚 Пакетное обучение локаций", P["gold"], "#FFE033",
             "[PRO] Папка с подпапками ELSH/Sandy/Paleto — система выучит цвета каждой больницы",
             s._batch_teach),
            ("🏷 Разметить скриншоты", P["bodycam"], "#FF5555",
             "[PRO] Показать скрин и указать категорию и больницу. Можно удалять примеры из базы",
             s._open_label_window),
            ("🖐 Ручная сортировка с запоминанием", P["orange"], P["oh"],
             "[PRO] Смотрите скрины и кнопками раскидывайте по папкам. Система запоминает каждое действие",
             s._open_quick_sort),
            ("📂 Просмотр и исправление", P["blue"], "#2563EB",
             "[PRO] Проверить отсортированные папки. Если скрин не туда — перекиньте и система запомнит",
             s._open_folder_review),
        ]

        for text, fg, hover, tip, cmd in tools:
            tf2 = ctk.CTkFrame(ab, fg_color="transparent");
            tf2.pack(fill="x", pady=(0, 2))
            ctk.CTkButton(tf2, text=text, height=34,
                          fg_color=fg, hover_color=hover,
                          text_color="#fff" if fg != P["gold"] else "#1a1a1a",
                          font=ctk.CTkFont(size=11, weight="bold"),
                          command=cmd).pack(fill="x")
            ctk.CTkLabel(tf2, text=f"   {tip}",
                         font=ctk.CTkFont(size=8), text_color=P["dim"],
                         wraplength=380, justify="left").pack(anchor="w", padx=4)

        s.db_info = ctk.CTkLabel(ab, text="", font=ctk.CTkFont(size=9), text_color=P["dim"])
        s.db_info.pack(anchor="w", pady=(6, 4));
        s._update_db_info()
        ctk.CTkButton(ab, text="🗑 Сбросить базу знаний", height=28,
                      fg_color=P["entry"], hover_color=P["bh"],
                      border_width=1, border_color=P["border"],
                      text_color=P["err"], font=ctk.CTkFont(size=9),
                      command=s._reset_db).pack(fill="x")

        # ── Диагностика ──
        dc = Sec(lp, "🔬 Диагностика", P["blue"]);
        dc.pack(fill="x", pady=(0, 4))
        dbb = ctk.CTkFrame(dc.body, fg_color="transparent");
        dbb.pack(fill="x", padx=12, pady=6)
        ctk.CTkButton(dbb, text="Анализ одного файла (подробный лог)",
                      height=30, fg_color=P["blue"],
                      hover_color="#2563EB", text_color="#fff",
                      font=ctk.CTkFont(size=10), command=s._d1).pack(fill="x", pady=(0, 3))
        ctk.CTkButton(dbb, text="Проверить боди-кам",
                      height=30, fg_color=P["bodycam"],
                      hover_color="#FF5555", text_color="#fff",
                      font=ctk.CTkFont(size=10), command=s._dbc).pack(fill="x")

        # ── Запуск ──
        cc = Sec(lp, "🚀 Запуск");
        cc.pack(fill="x", pady=(0, 4))
        ci = ctk.CTkFrame(cc.body, fg_color="transparent");
        ci.pack(fill="x", padx=12, pady=6)
        pf = ctk.CTkFrame(ci, fg_color="transparent");
        pf.pack(fill="x", pady=(0, 2))
        s.pl = ctk.CTkLabel(pf, text="Готово к работе", font=ctk.CTkFont(size=10), text_color=P["dim"])
        s.pl.pack(side="left")
        s.pp = ctk.CTkLabel(pf, text="", font=ctk.CTkFont(size=10, weight="bold"),
                            text_color=P["accent"])
        s.pp.pack(side="right")
        s.pb = ctk.CTkProgressBar(ci, height=6, progress_color=P["accent"], fg_color=P["entry"])
        s.pb.pack(fill="x", pady=(0, 4));
        s.pb.set(0)
        s.sp = ctk.CTkLabel(ci, text="", font=ctk.CTkFont(size=9, family="Consolas"),
                            text_color=P["dim"])
        s.sp.pack(anchor="w", pady=(0, 4))
        bf2 = ctk.CTkFrame(ci, fg_color="transparent");
        bf2.pack(fill="x", pady=(0, 4))
        s.cs = s._bd(bf2, "ОК", "0", P["ok"]);
        s.ck = s._bd(bf2, "Пропуск", "0", P["warn"])
        s.ce = s._bd(bf2, "Ошибка", "0", P["err"]);
        s.ct_ = s._bd(bf2, "Всего", "0", P["info"])
        s.cbc = s._bd(bf2, "БК", "0", P["bodycam"])
        br2 = ctk.CTkFrame(ci, fg_color="transparent");
        br2.pack(fill="x")
        s.sb = ctk.CTkButton(br2, text="▶ СОРТИРОВАТЬ", height=40,
                             font=ctk.CTkFont(size=12, weight="bold"),
                             fg_color=P["accent"], hover_color=P["ah"], text_color="#fff",
                             corner_radius=10, command=s._go)
        s.sb.pack(side="left", fill="x", expand=True, padx=(0, 4))
        Tooltip(s.sb,
                "Запускает автоматическую сортировку всех\nскриншотов из входной папки.\nГорячая клавиша: Ctrl+Enter")
        s.xb = ctk.CTkButton(br2, text="⏹", width=50, height=40,
                             font=ctk.CTkFont(size=14, weight="bold"),
                             fg_color=P["red"], hover_color=P["rh"], text_color="#fff",
                             corner_radius=10, command=s._st, state="disabled")
        s.xb.pack(side="left", padx=(0, 4))
        Tooltip(s.xb, "Остановить текущую сортировку")
        s.kb = ctk.CTkButton(br2, text="Пропущ.", width=70, height=40,
                             fg_color=P["entry"], hover_color=P["bh"],
                             border_width=1, border_color=P["border"], text_color=P["warn"],
                             corner_radius=10, command=s._skp, state="disabled")
        s.kb.pack(side="left", padx=(0, 4))
        Tooltip(s.kb, "Открыть пропущенные скрины\nдля ручной сортировки")
        ctk.CTkButton(br2, text="📂", width=50, height=40,
                      fg_color=P["entry"], hover_color=P["bh"],
                      border_width=1, border_color=P["border"], text_color=P["blue"],
                      corner_radius=10, command=s._oo).pack(side="right")

        # ══ Лог ══
        rp = ctk.CTkFrame(mn, fg_color=P["card"], corner_radius=12,
                          border_width=1, border_color=P["border"])
        rp.grid(row=0, column=1, sticky="nsew")
        rp.rowconfigure(1, weight=1);
        rp.columnconfigure(0, weight=1)
        lh = ctk.CTkFrame(rp, fg_color="transparent", height=34)
        lh.grid(row=0, column=0, sticky="ew", padx=10, pady=(6, 0));
        lh.pack_propagate(False)
        ctk.CTkLabel(lh, text="📋 Лог", font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=P["text"]).pack(side="left")
        s._as = ctk.BooleanVar(value=True)
        ctk.CTkSwitch(lh, text="Авто", variable=s._as, width=48, height=16,
                      text_color=P["dim"], progress_color=P["accent"],
                      button_color=P["text"], font=ctk.CTkFont(size=8)).pack(side="right")
        for t2, cmd in [("Копир.", s._cl), ("Очист.", s._cr2), ("Сохран.", s._sl)]:
            ctk.CTkButton(lh, text=t2, width=42, height=22, fg_color=P["entry"],
                          hover_color=P["border"], text_color=P["dim"], corner_radius=4,
                          font=ctk.CTkFont(size=9), command=cmd).pack(side="right", padx=(0, 3))
        lf = ctk.CTkFrame(rp, fg_color=P["log"], corner_radius=8)
        lf.grid(row=1, column=0, sticky="nsew", padx=6, pady=(4, 6))
        lf.rowconfigure(0, weight=1);
        lf.columnconfigure(0, weight=1)
        s.log_t = Text(lf, font=("Consolas", 10), bg=P["log"], fg=P["text"],
                       insertbackground=P["log"], selectbackground=P["accent"],
                       selectforeground="#fff", relief="flat", borderwidth=0,
                       padx=8, pady=6, wrap="word", state="normal", cursor="arrow",
                       exportselection=True)
        s.log_t.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)

        def _check_updates_manual(self):
            """Ручная проверка обновлений."""
            self._log("🔄 Проверка обновлений...", "info")

            def check():
                has_update, version, url, description = check_for_updates()

                if has_update and url:
                    self.after(0, lambda: self._show_update_dialog(version, url, description))
                    self.after(0, lambda: self._log(f"✅ Доступна версия {version}", "success"))
                elif version:
                    self.after(0, lambda: self._log(f"✅ У вас последняя версия ({APP_VERSION})", "success"))
                else:
                    self.after(0, lambda: self._log("❌ Не удалось проверить обновления", "error"))

            threading.Thread(target=check, daemon=True).start()


        def _bl(e):
            if e.state & 4 and e.keysym.lower() in ('c', 'a'): return
            if e.keysym in ('Up', 'Down', 'Left', 'Right', 'Home', 'End',
                            'Prior', 'Next', 'Shift_L', 'Shift_R',
                            'Control_L', 'Control_R'): return
            return "break"

        s.log_t.bind("<Key>", _bl);
        s.log_t.bind("<<Paste>>", lambda e: "break")
        sb3 = tk.Scrollbar(lf, orient="vertical", command=s.log_t.yview,
                           bg=P["card"], troughcolor=P["log"])
        sb3.grid(row=0, column=1, sticky="ns", pady=2)
        s.log_t.configure(yscrollcommand=sb3.set)
        for tg, cl in [("success", P["ok"]), ("error", P["err"]), ("warning", P["warn"]),
                       ("info", P["info"]), ("default", P["text"]), ("accent", P["accent"]),
                       ("orange", P["orange"]), ("dim", P["dim"]), ("purple", P["purple"]),
                       ("gold", P["gold"]), ("bodycam", P["bodycam"])]:
            s.log_t.tag_config(tg, foreground=cl)
        s._welcome();
        s._check_for_updates()
        s._ot()
        s.bind_all("<Control-z>", lambda e: s._undo_last())

    def _undo_last(s):
        if not s._undo_history:
            s._log("  Нечего отменять", "warning")
            return
        src, dst = s._undo_history.pop()
        try:
            if dst.exists():
                dst.unlink()
                s._log(f"  ↩️ Отменено: {dst.name} удалён из {dst.parent.name}", "info")
        except Exception as e:
            s._log(f"  ❌ Ошибка отмены: {e}", "error")

    # ══════════════════════════════════════
    #  ВСПОМОГАТЕЛЬНЫЕ
    # ══════════════════════════════════════
    def _update_db_label(s):
        total = len(s.location_db.get("samples", []))
        s.db_l.configure(text=f"БД: {total} примеров")

    def _update_db_info(s):
        db = s.location_db;
        total = len(db.get("samples", []))
        by_loc = {}
        for sample in db.get("samples", []):
            loc = sample.get("location", "?")
            by_loc[loc] = by_loc.get(loc, 0) + 1
        lines = [f"База знаний: {total} примеров"]
        for loc, cnt in sorted(by_loc.items(), key=lambda x: -x[1]):
            lines.append(f"  {loc}: {cnt}")
        if not by_loc: lines.append("  (пусто — обучите систему)")
        s.db_info.configure(text="\n".join(lines))

    def _fr(s, p, l, ph, cmd):
        f = ctk.CTkFrame(p, fg_color="transparent");
        f.pack(fill="x", padx=12, pady=3)
        ctk.CTkLabel(f, text=l, font=ctk.CTkFont(size=9), text_color=P["t2"]).pack(anchor="w")
        r = ctk.CTkFrame(f, fg_color="transparent");
        r.pack(fill="x")
        e = ctk.CTkEntry(r, height=30, fg_color=P["entry"], border_color=P["border"],
                         text_color=P["text"], placeholder_text=ph,
                         placeholder_text_color=P["dim"], corner_radius=6,
                         font=ctk.CTkFont(size=10))
        e.pack(side="left", fill="x", expand=True, padx=(0, 4))
        ctk.CTkButton(r, text="...", width=34, height=30, fg_color=P["entry"],
                      hover_color=P["bh"], border_width=1, border_color=P["border"],
                      text_color=P["t2"], corner_radius=6,
                      font=ctk.CTkFont(size=10), command=cmd).pack(side="right")
        return e

    def _bd(s, p, l, v, c):
        f = ctk.CTkFrame(p, fg_color=P["entry"], corner_radius=6,
                         border_width=1, border_color=P["border"])
        f.pack(side="left", padx=(0, 3), pady=(0, 2))
        ctk.CTkLabel(f, text=l, font=ctk.CTkFont(size=8), text_color=P["dim"]).pack(padx=6, pady=(2, 0))
        lb = ctk.CTkLabel(f, text=v, font=ctk.CTkFont(size=13, weight="bold"), text_color=c)
        lb.pack(padx=6, pady=(0, 2));
        return lb

    def _ot(s):
        if _ocr._ok:
            s.ocr_l.configure(text=_ocr._n, text_color=P["ok"])
        else:
            s.after(400, s._ot)

    def _check_for_updates(s):
        def check():
            try:
                data = _check_update()
                latest = data.get("version", "")
                if latest and latest != APP_VERSION:
                    changelog = data.get("changelog", "")
                    s.after(0, lambda: s._show_update_dialog(latest, changelog))
            except Exception:
                pass

        threading.Thread(target=check, daemon=True).start()

    def _show_update_dialog(s, version, changelog):
        dialog = ctk.CTkToplevel(s)
        dialog.title("Доступно обновление")
        dialog.configure(fg_color=P["bg"])
        dialog.transient(s)
        dialog.grab_set()

        sw, sh = dialog.winfo_screenwidth(), dialog.winfo_screenheight()
        dialog.geometry(f"400x280+{(sw - 400) // 2}+{(sh - 280) // 2}")
        dialog.resizable(False, False)

        ctk.CTkLabel(dialog, text="🔄 Доступно обновление!",
                     font=ctk.CTkFont(size=16, weight="bold"),
                     text_color=P["accent"]).pack(pady=(20, 10))

        ctk.CTkLabel(dialog, text=f"Текущая версия: {APP_VERSION}",
                     font=ctk.CTkFont(size=11),
                     text_color=P["t2"]).pack()

        ctk.CTkLabel(dialog, text=f"Новая версия: {version}",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=P["gold"]).pack(pady=(0, 10))

        if changelog:
            ctk.CTkLabel(dialog, text="Что нового:",
                         font=ctk.CTkFont(size=10, weight="bold"),
                         text_color=P["text"]).pack(anchor="w", padx=30)

            ctk.CTkLabel(dialog, text=changelog,
                         font=ctk.CTkFont(size=10),
                         text_color=P["t2"],
                         justify="left",
                         wraplength=340).pack(anchor="w", padx=30, pady=(0, 15))

        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(fill="x", padx=30, pady=(0, 20))

        def open_download():
            import webbrowser
            webbrowser.open(DOWNLOAD_URL)
            dialog.destroy()

        ctk.CTkButton(btn_frame, text="Позже", height=36,
                      fg_color=P["entry"], hover_color=P["bh"],
                      border_width=1, border_color=P["border"],
                      text_color=P["t2"], font=ctk.CTkFont(size=11),
                      command=dialog.destroy).pack(side="left", fill="x", expand=True, padx=(0, 5))

        ctk.CTkButton(btn_frame, text="⬇️ Скачать", height=36,
                      fg_color=P["accent"], hover_color=P["ah"],
                      text_color="#fff", font=ctk.CTkFont(size=11, weight="bold"),
                      command=open_download).pack(side="right", fill="x", expand=True, padx=(5, 0))

    def _welcome(s):
        s._log(f"Majestic RP Sorter v{APP_VERSION}", "accent")
        s._log(f"by {APP_AUTHOR}", "orange")
        engines = []
        if PADDLEOCR_OK: engines.append("PaddleOCR")
        if EASYOCR_OK: engines.append("EasyOCR")
        if TESSERACT_OK: engines.append("Tesseract")
        if RAPIDOCR_OK: engines.append("RapidOCR")
        s._log(f"OCR движки: {', '.join(engines) if engines else 'не найдены'}", "info")
        total_db = len(s.location_db.get("samples", []))
        if total_db > 0:
            s._log(f"База знаний: {total_db} примеров", "gold")
        else:
            s._log("⚠️ База знаний пуста — откройте 'Разметить скриншоты' или 'Пакетное обучение'", "warning")
        s._log("", "default")

        if s.is_pro:
            s._log("🔑 PRO версия активирована", "gold")
        else:
            s._log("💡 Бесплатная версия. PRO: настройки → активация", "dim")

    # ЭТИ МЕТОДЫ ДОЛЖНЫ БЫТЬ НА УРОВНЕ КЛАССА (тот же отступ что и _welcome)

    def _check_updates_background(s):
        """Проверяет обновления в фоне при запуске."""
        if not GITHUB_REPO:
            return

        time.sleep(3)
        try:
            has_update, version, url, description = check_for_updates()
            if has_update and url:
                s.after(0, lambda: s._show_update_dialog(version, url, description))
        except Exception as e:
            print(f"[UPDATE] Ошибка фоновой проверки: {e}")

    def _check_updates_manual(s):
        """Ручная проверка обновлений по кнопке."""
        if not GITHUB_REPO:
            s._log("⚠️ Проверка обновлений отключена", "warning")
            return

        s._log("🔄 Проверка обновлений...", "info")

        def check():
            try:
                print(f"[DEBUG] Проверяю URL: {UPDATE_CHECK_URL}")
                has_update, version, url, description = check_for_updates()
                print(f"[DEBUG] Результат: has_update={has_update}, version={version}, url={url}")

                if has_update and url:
                    print(f"[DEBUG] Есть обновление! Открываю диалог...")
                    s.after(0, lambda: s._show_update_dialog(version, url, description))
                    s.after(0, lambda: s._log(f"✅ Доступна версия {version}", "success"))
                elif version:
                    print(f"[DEBUG] Обновлений нет, текущая версия актуальна")
                    s.after(0, lambda: s._log(f"✅ У вас последняя версия ({APP_VERSION})", "success"))
                else:
                    print(f"[DEBUG] Не удалось получить версию")
                    s.after(0, lambda: s._log("❌ Не удалось проверить обновления", "error"))
            except Exception as e:
                print(f"[DEBUG] Исключение: {e}")
                s.after(0, lambda: s._log(f"❌ Ошибка: {e}", "error"))

        threading.Thread(target=check, daemon=True).start()

    def _show_update_dialog(s, version, url, description):
        """Показывает диалог обновления."""
        print(f"[DEBUG] _show_update_dialog вызван: version={version}, url={url}")
        try:
            dialog = UpdateDialog(s, version, url, description)
            print(f"[DEBUG] Диалог создан: {dialog}")
        except Exception as e:
            print(f"[DEBUG] Ошибка создания диалога: {e}")
            import traceback
            traceback.print_exc()

    # ══════════════════════════════════════
    #  КНОПКИ ЛОГ
    # ══════════════════════════════════════
    def _cr2(s):
        s.log_t.delete("1.0", END)

    def _sl(s):
        fp = filedialog.asksaveasfilename(defaultextension=".txt")
        if fp: Path(fp).write_text(s.log_t.get("1.0", END), encoding="utf-8")

    def _cl(s):
        try:
            t = s.log_t.get(tk.SEL_FIRST, tk.SEL_LAST)
            s.clipboard_clear();
            s.clipboard_append(t)
        except:
            c = s.log_t.get("1.0", END).strip()
            if c: s.clipboard_clear(); s.clipboard_append(c)

    def _bi(s):
        d = filedialog.askdirectory()
        if d:
            s.inp_e.delete(0, END);
            s.inp_e.insert(0, d)
            if not s.out_e.get():
                s.out_e.delete(0, END);
                s.out_e.insert(0, str(Path(d) / "Sorted"))

    def _bo(s):
        d = filedialog.askdirectory()
        if d: s.out_e.delete(0, END); s.out_e.insert(0, d)

    def _oo(s):
        o = s.out_e.get().strip()
        if o and Path(o).exists(): os.startfile(o)

    # ══════════════════════════════════════
    #  НОВЫЕ ОКНА
    # ══════════════════════════════════════
    def _open_label_window(s):
        if not s.is_pro:
            s._log("  🔒 Разметка скриншотов доступна в PRO версии", "warning")
            s._log("  💡 Настройки → Активировать PRO", "gold")
            return
        LabelWindow(s, s.cfg, s.az, s.trigger_db, s.location_db, s._log)

    def _open_analytics(s):
        fp = filedialog.askopenfilename(title="Выберите скриншот для анализа",
                                        filetypes=[("Изображения", "*.png *.jpg *.jpeg *.bmp")])
        if not fp: return
        s._log(f"\n🔍 Аналитика: {Path(fp).name}", "purple")
        az = Analyzer(s.cfg, require_bodycam=s.bc_var.get(), location_db=s.location_db)
        AnalyticsWindow(s, Path(fp), az, s._log, s.location_db)

    def _open_quick_sort(s):
        if not s.is_pro:
            s._log("  🔒 Ручная сортировка с запоминанием доступна в PRO версии", "warning")
            s._log("  💡 Настройки → Активировать PRO", "gold")
            return
        out = s.out_e.get().strip()
        if not out:
            s._log("  ⚠️ Сначала укажите выходную папку", "warning");
            return
        if s.skipped:
            files = list(s.skipped)
        else:
            d = filedialog.askdirectory(title="Папка со скриншотами для ручной сортировки")
            if not d: return
            files = sorted([p for p in Path(d).iterdir()
                            if p.is_file() and p.suffix.lower() in EXTS])
            if not files: s._log("  Папка пуста", "warning"); return
        s._log(f"  ⚡ Быстрая сортировка: {len(files)} файлов", "info")
        az = Analyzer(s.cfg, require_bodycam=False,
                      location_db=s.location_db, trigger_db=s.trigger_db)
        QuickSortWindow(s, files, s.cfg, az, s._log, out, s.location_db, s.trigger_db)

    def _open_folder_review(s):
        if not s.is_pro:
            s._log("  🔒 Просмотр и исправление доступно в PRO версии", "warning")
            s._log("  💡 Настройки → Активировать PRO", "gold")
            return
        out = s.out_e.get().strip()
        az = Analyzer(s.cfg, require_bodycam=False,
                      location_db=s.location_db, trigger_db=s.trigger_db)
        FolderReviewWindow(s, s.cfg, az, s._log, s.location_db, s.trigger_db,
                           default_dir=out if out else None)

        def _open_auto_learn(s):
            if not s.is_pro:
                s._log("  🔒 Автообучение доступно в PRO версии", "warning")
                s._log("  💡 Настройки → Активировать PRO", "gold")
                return
            AutoLearnWindow(s, s.cfg, s.az, s.location_db, s.trigger_db, s._log)

    # ══════════════════════════════════════
    #  ОБУЧЕНИЕ
    # ══════════════════════════════════════
    def _batch_teach(s):
        if not s.is_pro:
            s._log("  🔒 Пакетное обучение доступно в PRO версии", "warning")
            s._log("  💡 Настройки → Активировать PRO", "gold")
            return
        d = filedialog.askdirectory(title="Папка (подпапки = названия локаций: ELSH, Sandy, Paleto)")
        if not d: return
        loc_map = {"elsh": "ELSH", "элш": "ELSH", "sandy": "Sandy",
                   "санди": "Sandy", "paleto": "Paleto", "палето": "Paleto"}
        threading.Thread(target=s._do_batch_teach, args=(Path(d), loc_map), daemon=True).start()

    def _do_batch_teach(s, folder, loc_map):
        count = 0
        az = Analyzer(s.cfg, require_bodycam=False, location_db=s.location_db)
        for subfolder in folder.iterdir():
            if not subfolder.is_dir(): continue
            loc_name = subfolder.name.lower();
            correct_loc = None
            for key, val in loc_map.items():
                if key in loc_name: correct_loc = val; break
            if not correct_loc:
                s._log(f"  '{subfolder.name}' — не пойму что за локация (назовите ELSH/Sandy/Paleto)", "warning")
                continue
            files = [f for f in subfolder.iterdir() if f.suffix.lower() in EXTS]
            s._log(f"  {subfolder.name} → {correct_loc}: {len(files)} файлов", "info")
            for fp in files:
                feats = az.teach(fp, correct_loc, s._log)
                if feats: count += 1
        s._log(f"\n✅ Обучение завершено: {count} примеров добавлено", "success")
        _play_done_sound()
        s.after(0, s._update_db_info);
        s.after(0, s._update_db_label)

    def _reset_db(s):
        if LOCATION_DB_FILE.exists(): LOCATION_DB_FILE.unlink()
        s.location_db.clear()
        s.location_db.update({"samples": [], "feature_ranges": {}, "version": 1})
        s._log("  🗑 База знаний сброшена", "warning")
        s._update_db_info();
        s._update_db_label()

    # ══════════════════════════════════════
    #  ДИАГНОСТИКА
    # ══════════════════════════════════════
    def _dbc(s):
        fp = filedialog.askopenfilename(filetypes=[("Изображения", "*.png *.jpg *.jpeg *.bmp")])
        if not fp: return
        s._log(f"🔴 Проверка боди-кам: {Path(fp).name}", "bodycam")
        threading.Thread(target=s._dbc2, args=(Path(fp),), daemon=True).start()

    def _dbc2(s, fp):
        img = _ld(fp)
        if img is None: s._log("  ошибка загрузки", "error"); return
        ctx = ImageContext(img, s.cfg)
        s._log(f"  Размер: {ctx.w}x{ctx.h}", "info")
        a, r = check_bodycam(ctx)
        s._log(f"  Результат: {'🔴 ВКЛЮЧЕНА' if a else '⚪ НЕ НАЙДЕНА'} (сила={r:.6f})",
               "success" if a else "error")

    def _d1(s):
        fp = filedialog.askopenfilename(filetypes=[("Изображения", "*.png *.jpg *.jpeg *.bmp")])
        if not fp: return
        s._log(f"\n🔍 Подробный анализ: {Path(fp).name}", "purple")
        threading.Thread(target=s._dd, args=(Path(fp),), daemon=True).start()

    def _dd(s, fp):
        az = Analyzer(s.cfg, require_bodycam=s.bc_var.get(), location_db=s.location_db)
        r = az.run(fp, wd=True)
        for l in r.diag:
            if "[признаки]" in l:
                s._log(f"  {l}", "accent")
            elif "[триг]" in l:
                s._log(f"  {l}", "info")
            elif "[результат]" in l:
                s._log(f"  {l}", "success")
            elif "[бд]" in l:
                s._log(f"  {l}", "gold")
            elif any(x in l for x in ["[E]", "[S]", "[P]", "[скоры]", "[классика]"]):
                s._log(f"  {l}", "accent")
            else:
                s._log(f"  {l}", "dim")
        if r.ok:
            s._log(f"  ✅ {r.cat.value} | {r.hosp.value} | {r.method}", "success")
        else:
            s._log(f"  ❌ {r.err}", "error")

    # ══════════════════════════════════════
    #  СОРТИРОВКА
    # ══════════════════════════════════════
    def _up(s, d, t, ok, sk, er, bc, el):
        def _u():
            v = d / t if t else 0;
            s.pb.set(v);
            s.pp.configure(text=f"{int(v * 100)}%")
            s.pl.configure(text=f"({d}/{t})" if v < 1 else "Готово")
            if v < 1 and d > 0 and el > 0:
                eta = int((t - d) * (el / d))
                s.title(f"Majestic RP Sorter — {int(v * 100)}% ({d}/{t}) ~{eta}с")
            else:
                s.title(f"Majestic RP Sorter v{APP_VERSION}")
            s.cs.configure(text=str(ok));
            s.ck.configure(text=str(sk))
            s.ce.configure(text=str(er));
            s.cbc.configure(text=str(bc))
            if d > 0 and el > 0:
                ms = el / d * 1000;
                s.sp.configure(text=f"{ms:.0f}мс ~{(t - d) * ms / 1000:.0f}с")

        s.after(0, _u)

    def _go(s):
        if s.is_proc: return
        inp = s.inp_e.get().strip();
        out = s.out_e.get().strip()
        if not inp or not Path(inp).is_dir():
            s._log("  ❌ Укажите правильную входную папку", "error");
            return
        if not out: s._log("  ❌ Укажите выходную папку", "error"); return
        s._stop.clear();
        s.is_proc = True;
        s.skipped = []
        s.sb.configure(text="...", fg_color=P["dim"], state="disabled")
        s.xb.configure(state="normal");
        s.kb.configure(state="disabled", text="Пропущ.")
        s.pb.set(0);
        s.pp.configure(text="0%")
        s.title(f"Majestic RP Sorter v{APP_VERSION} — Сортировка...")
        for l in (s.cs, s.ck, s.ce, s.ct_, s.cbc): l.configure(text="0")
        s._log(f"\n▶ Старт: {inp} → {out}", "info")
        s.az.require_bodycam = s.bc_var.get()
        threading.Thread(target=s._sort,
                         args=(inp, out, int(s.wk_var.get()),
                               s.dry_var.get(), s.bc_var.get()),
                         daemon=True).start()

    def _st(s):
        if s.is_proc: s._stop.set(); s.xb.configure(state="disabled")

    def _sort(s, inp, out, wk, dry, rbc):
        idir = Path(inp);
        odir = Path(out);
        odir.mkdir(parents=True, exist_ok=True)
        files = sorted([p for p in idir.iterdir()
                        if p.is_file() and p.suffix.lower() in EXTS])
        if not files:
            s._log("  Папка пуста", "warning");
            s.after(0, s._done);
            return
        total = len(files);
        s.after(0, lambda: s.ct_.configure(text=str(total)))
        az = s.az;
        ok = sk = er = bc = done = 0;
        hc = {};
        t0 = time.monotonic()
        s._pf.prefetch(files[:5]);
        pnb = []

        for i, fp in enumerate(files):
            if s._stop.is_set(): break
            done += 1;
            el = time.monotonic() - t0
            if i + 1 < len(files): s._pf.prefetch(files[i + 1:i + 4])
            try:
                r = az.run(fp)
                if r.ok:
                    fd = r.folder
                    if not dry:
                        dd = odir / fd;
                        dd.mkdir(parents=True, exist_ok=True)
                        dst = dd / fp.name;
                        n = 1
                        while dst.exists():
                            dst = dd / f"{fp.stem}_{n}{fp.suffix}";
                            n += 1
                        shutil.copy2(fp, dst)
                        s._undo_history.append((fp, dst))
                    hc[fd] = hc.get(fd, 0) + 1;
                    ok += 1
                    s._log(f"  ✅ [{r.method}] {fp.name} → {fd}", "success")
                elif r.err == "Нет боди-кам":
                    pnb.append(fp)
                else:
                    sk += 1;
                    s.skipped.append(fp)
                    s._log(f"  ⏭ {fp.name} — {r.err}", "warning")
            except Exception as e:
                er += 1;
                s.skipped.append(fp)
                s._log(f"  ❌ {fp.name}: {str(e)[:60]}", "error")
            s._up(done, total + len(pnb), ok, sk, er, bc, el)

        if pnb and not s._stop.is_set():
            s._log(f"\n  🔄 Проход 2 (боди-кам): {len(pnb)} файлов", "bodycam")
            for fp in pnb:
                if s._stop.is_set(): break
                done += 1;
                el = time.monotonic() - t0
                try:
                    fv = _fh(fp);
                    az._c.pop(fv)
                    r = az.run(fp)
                    if r.ok:
                        fd = r.folder
                        if not dry:
                            dd = odir / fd;
                            dd.mkdir(parents=True, exist_ok=True)
                            dst = dd / fp.name;
                            n = 1
                            while dst.exists():
                                dst = dd / f"{fp.stem}_{n}{fp.suffix}";
                                n += 1
                            shutil.copy2(fp, dst)
                        hc[fd] = hc.get(fd, 0) + 1;
                        ok += 1
                        s._log(f"  ✅ [{r.method}] {fp.name} → {fd}", "success")
                    elif r.err == "Нет боди-кам":
                        bc += 1;
                        s.skipped.append(fp)
                    else:
                        sk += 1;
                        s.skipped.append(fp)
                        s._log(f"  ⏭ {fp.name} — {r.err}", "warning")
                except Exception as e:
                    er += 1;
                    s.skipped.append(fp)
                s._up(done, total + len(pnb), ok, sk, er, bc, el)

        dur = time.monotonic() - t0
        s._log("", "default")
        s._log(f"  ═══════════════════════════════", "accent")
        s._log(f"  ✅ Готово! ОК:{ok} | Пропуск:{sk} | БК:{bc} | Ошибок:{er} | Всего:{total} ({dur:.1f}с)",
               "success" if ok else "warning")
        if hc:
            s._log("  По папкам:", "info")
            for h, c in sorted(hc.items(), key=lambda x: -x[1]):
                s._log(f"    📁 {h}: {c}", "accent")
        if total: s._log(f"  Скорость: {dur / total * 1000:.0f}мс/файл", "info")

        # Подсказка про проверку
        if ok > 0:
            s._log("", "default")
            s._log("  💡 Совет: откройте «Просмотр и исправление» чтобы проверить", "gold")
            s._log("     что все скрины попали в правильные папки.", "gold")
            s._log("     Если что-то не туда — перекиньте кнопкой и система запомнит.", "gold")

        if s.skipped:
            s._log("", "default")
            s._log(f"  ⚡ {len(s.skipped)} скринов пропущено — нажмите «Пропущ.» для быстрой сортировки", "orange")

        if PLYER_OK:
            try:
                _notify.notify(
                    title="Сортировка завершена",
                    message=f"ОК: {ok} | Пропуск: {sk} | БК: {bc} | Ошибок: {er}",
                    timeout=5
                )
            except Exception:
                pass
        _play_done_sound()
        s.after(0, s._done)

    def _done(s):
        s.is_proc = False
        s.sb.configure(text="▶ СОРТИРОВАТЬ", fg_color=P["accent"], state="normal")
        s.xb.configure(state="disabled")
        s.title(f"Majestic RP Sorter v{APP_VERSION}")
        if s.skipped:
            s.kb.configure(state="normal", text=f"Пропущ.({len(s.skipped)})")

    def _skp(s):
        if not s.skipped: return
        out = s.out_e.get().strip()
        if out:
            az = Analyzer(s.cfg, require_bodycam=False,
                          location_db=s.location_db, trigger_db=s.trigger_db)
            QuickSortWindow(s, list(s.skipped), s.cfg, az,
                            s._log, out, s.location_db, s.trigger_db)
        else:
            SkipV(s, list(s.skipped), s.cfg, s.az,
                  s._log, s.bc_var.get(), s.location_db)


def _activate_pro(s):
    dialog = ctk.CTkInputDialog(
        text="Введите ключ активации\n(формат: MJ-XXXX-XXXX-XXXX)",
        title="Активация PRO")
    key = dialog.get_input()
    if not key: return
    key = key.strip().upper()
    if not key.startswith("MJ-") or len(key) != 16:
        s._log("  ❌ Неверный формат ключа", "error");
        return
    data = {"key": key}
    LICENSE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    if _check_license():
        s.is_pro = True
        s._log("  🔑 PRO активирован! Перезапустите программу", "success")
        _play_done_sound()
    else:
        s._log("  ❌ Ключ недействителен", "error")


# ═══════════════════════════════════════════
#  ОКНО ПРОПУЩЕННЫХ
# ═══════════════════════════════════════════
class SkipV(ctk.CTkToplevel):
    def __init__(s, parent, files, cfg, az, log_fn, rbc, location_db):
        super().__init__(parent);
        s.title("Пропущенные");
        s.configure(fg_color=P["bg"])
        s.transient(parent);
        s.grab_set()
        s.files = files;
        s.idx = 0;
        s.photo = None;
        s.cfg = cfg
        s.az = az;
        s._log = log_fn;
        s.rbc = rbc;
        s.location_db = location_db
        sw, sh = s.winfo_screenwidth(), s.winfo_screenheight()
        s.geometry(f"860x650+{(sw - 860) // 2}+{(sh - 650) // 2}")
        s._b()
        if files: s._sh(0)

    def _b(s):
        if not s.files: return
        s.ifr = ctk.CTkFrame(s, fg_color=P["card"], corner_radius=10)
        s.ifr.pack(fill="both", expand=True, padx=10, pady=6)
        s.il = ctk.CTkLabel(s.ifr, text="");
        s.il.pack(expand=True)
        s.fn = ctk.CTkLabel(s, text="", font=ctk.CTkFont(family="Consolas", size=9),
                            text_color=P["t2"], fg_color=P["card"], height=22)
        s.fn.pack(fill="x", padx=10, pady=(0, 3))
        tf = ctk.CTkFrame(s, fg_color=P["entry"], corner_radius=8,
                          border_width=1, border_color=P["border"])
        tf.pack(fill="x", padx=10, pady=(0, 4))
        s.tv = ctk.StringVar(value="ELSH")
        ctk.CTkOptionMenu(tf, values=["ELSH", "Sandy", "Paleto"], variable=s.tv,
                          width=85, height=28, fg_color=P["bg"], button_color=P["gold"],
                          dropdown_fg_color=P["card"], text_color=P["text"],
                          font=ctk.CTkFont(size=10)).pack(side="left", padx=8)
        ctk.CTkButton(tf, text="Обучить", height=28, width=70,
                      fg_color=P["accent"], text_color="#fff",
                      font=ctk.CTkFont(size=10), command=s._te).pack(side="left", padx=4)
        ctk.CTkButton(tf, text="Аналитика", height=28, width=80,
                      fg_color=P["purple"], text_color="#fff",
                      font=ctk.CTkFont(size=10), command=s._analytics).pack(side="left", padx=4)
        ctk.CTkButton(tf, text="Диагн.", height=28, width=60,
                      fg_color=P["blue"], text_color="#fff",
                      font=ctk.CTkFont(size=10), command=s._dg).pack(side="right", padx=8, pady=4)
        nv = ctk.CTkFrame(s, fg_color="transparent", height=44)
        nv.pack(fill="x", padx=10, pady=(0, 8))
        s.pv = ctk.CTkButton(nv, text="<", width=80, height=34, fg_color=P["entry"],
                             hover_color=P["border"], text_color=P["t2"], corner_radius=8,
                             command=lambda: s._sh(s.idx - 1));
        s.pv.pack(side="left")
        ctk.CTkButton(nv, text="Удал.", width=80, height=34, fg_color=P["red"],
                      hover_color=P["rh"], text_color="#fff", corner_radius=8,
                      command=s._dl).pack(side="left", padx=4)
        s.nv = ctk.CTkButton(nv, text=">", width=80, height=34, fg_color=P["accent"],
                             hover_color=P["ah"], text_color="#fff", corner_radius=8,
                             command=lambda: s._sh(s.idx + 1));
        s.nv.pack(side="right")

    def _sh(s, i):
        if not s.files: return
        s.idx = max(0, min(i, len(s.files) - 1));
        fp = s.files[s.idx]
        s.fn.configure(text=f"  {s.idx + 1}/{len(s.files)} {fp.name}")
        try:
            pil = Image.open(fp);
            r = min(830 / pil.width, 300 / pil.height)
            pil = pil.resize((int(pil.width * r), int(pil.height * r)), Image.LANCZOS)
            s.photo = ImageTk.PhotoImage(pil);
            s.il.configure(image=s.photo, text="")
        except:
            s.il.configure(image=None, text="Ошибка")
        s.pv.configure(state="normal" if s.idx > 0 else "disabled")
        s.nv.configure(state="normal" if s.idx < len(s.files) - 1 else "disabled")

    def _te(s):
        if not s.files: return
        fp = s.files[s.idx];
        correct_loc = s.tv.get()
        feats = s.az.teach(fp, correct_loc, s._log)
        if feats: s._log(f"  {fp.name} → {correct_loc}: готово", "success")

    def _analytics(s):
        if not s.files: return
        AnalyticsWindow(s, s.files[s.idx], s.az, s._log, s.location_db)

    def _dg(s):
        if not s.files: return
        fp = s.files[s.idx]

        def _do():
            r = s.az.run(fp, wd=True)
            for l in r.diag:
                if "[признаки]" in l or any(x in l for x in ["[E]", "[S]", "[P]", "[скоры]"]):
                    s._log(f"  {l}", "accent")
                elif "[триг]" in l:
                    s._log(f"  {l}", "info")
                elif "[бд]" in l:
                    s._log(f"  {l}", "gold")
                else:
                    s._log(f"  {l}", "dim")
            if r.ok:
                s._log(f"  {r.cat.value} | {r.hosp.value} | {r.method}", "success")
            else:
                s._log(f"  {r.err}", "error")

        threading.Thread(target=_do, daemon=True).start()

    def _dl(s):
        if not s.files: return
        try:
            s.files[s.idx].unlink();
            s.files.pop(s.idx)
            if not s.files: s.il.configure(image=None, text="Готово"); return
            s.idx = min(s.idx, len(s.files) - 1);
            s._sh(s.idx)
        except:
            pass


# ═══════════════════════════════════════════
#  БЫСТРАЯ СОРТИРОВКА
# ═══════════════════════════════════════════
class QuickSortWindow(ctk.CTkToplevel):

    def _learn_move(s, fp, cat, loc):
        """Обучение системы на основе ручной сортировки."""
        if not PRO_FEATURES:
            return
        try:
            img = _ld(fp)
            if img is None:
                return

            ctx = ImageContext(img, s.cfg)
            feats = extract_features(ctx)

            # Сохраняем локацию
            if loc and loc not in ("suburb", "UNK", ""):
                add_location_sample(s.location_db, feats, loc, fp.name)

            # Сохраняем категорию
            if cat in ("TAB", "VAC", "PMP"):
                ocr_texts = []
                for rx, ry, rw, rh in s.cfg.CHAT_SCAN_ROIS[:1]:
                    roi = ctx.crop(rx, ry, rw, rh)
                    if roi is not None:
                        t, _ = _ocr.read(roi, mc=0.1, mh=3, ml=2)
                        if t:
                            ocr_texts.append(t.lower().strip())
                        break
                add_trigger_sample(s.trigger_db, fp.name, cat, ocr_texts, feats)
        except Exception as e:
            logger.error(f"QuickSort._learn_move: {e}")

    def __init__(s, parent, files, cfg, az, log_fn,
                 output_dir, location_db, trigger_db):
        super().__init__(parent)
        s.title("Быстрая сортировка")
        s.configure(fg_color=P["bg"])
        s.transient(parent)

        s.files = list(files)
        s.idx = 0
        s.photo = None
        s.cfg = cfg
        s.az = az
        s._log = log_fn
        s.output_dir = Path(output_dir)
        s.location_db = location_db
        s.trigger_db = trigger_db
        s.sorted_count = {"ELSH": 0, "Sandy": 0, "Paleto": 0,
                          "PMP_city": 0, "PMP_suburb": 0, "skip": 0}

        sw, sh = s.winfo_screenwidth(), s.winfo_screenheight()
        s.geometry(f"1000x750+{(sw - 1000) // 2}+{(sh - 750) // 2}")

        s._build()
        if files:
            s._show(0)

    def _build(s):
        hf = ctk.CTkFrame(s, fg_color=P["card"], corner_radius=0, height=50)
        hf.pack(fill="x");
        hf.pack_propagate(False)
        ctk.CTkLabel(hf, text="⚡ Быстрая сортировка",
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=P["accent"]).pack(side="left", padx=16)
        s.count_lbl = ctk.CTkLabel(hf, text="",
                                   font=ctk.CTkFont(size=10),
                                   text_color=P["gold"])
        s.count_lbl.pack(side="right", padx=16)

        s.img_frame = ctk.CTkFrame(s, fg_color=P["card"], corner_radius=10)
        s.img_frame.pack(fill="both", expand=True, padx=8, pady=4)
        s.img_lbl = ctk.CTkLabel(s.img_frame, text="")
        s.img_lbl.pack(expand=True)

        s.fname = ctk.CTkLabel(s, text="",
                               font=ctk.CTkFont(family="Consolas", size=9),
                               text_color=P["t2"])
        s.fname.pack(fill="x", padx=8)

        s.auto_lbl = ctk.CTkLabel(s, text="",
                                  font=ctk.CTkFont(size=10),
                                  text_color=P["info"])
        s.auto_lbl.pack(fill="x", padx=8, pady=2)

        s.prog = ctk.CTkProgressBar(s, height=5,
                                    progress_color=P["accent"],
                                    fg_color=P["entry"])
        s.prog.pack(fill="x", padx=8, pady=2)
        s.prog.set(0)

        btn_frame = ctk.CTkFrame(s, fg_color=P["entry"],
                                 corner_radius=10,
                                 border_width=1,
                                 border_color=P["border"])
        btn_frame.pack(fill="x", padx=8, pady=4)

        ctk.CTkLabel(btn_frame, text="Куда отправить?",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=P["text"]).pack(pady=(8, 4))

        row1 = ctk.CTkFrame(btn_frame, fg_color="transparent")
        row1.pack(fill="x", padx=8, pady=2)
        ctk.CTkLabel(row1, text="💊", font=ctk.CTkFont(size=14)).pack(side="left", padx=4)
        for name, loc, color in [("ELSH", "ELSH", P["accent"]),
                                 ("Sandy", "Sandy", P["gold"]),
                                 ("Paleto", "Paleto", P["purple"])]:
            ctk.CTkButton(
                row1, text=f"Табл → {name}", height=36,
                fg_color=color, hover_color=P["bh"],
                text_color="#fff" if color != P["gold"] else "#1a1a1a",
                font=ctk.CTkFont(size=10, weight="bold"),
                corner_radius=8,
                command=lambda l=loc: s._sort_to("TAB", l)
            ).pack(side="left", fill="x", expand=True, padx=2)

        row2 = ctk.CTkFrame(btn_frame, fg_color="transparent")
        row2.pack(fill="x", padx=8, pady=2)
        ctk.CTkLabel(row2, text="💉", font=ctk.CTkFont(size=14)).pack(side="left", padx=4)
        for name, loc, color in [("ELSH", "ELSH", P["accent"]),
                                 ("Sandy", "Sandy", P["gold"]),
                                 ("Paleto", "Paleto", P["purple"])]:
            ctk.CTkButton(
                row2, text=f"Вакц → {name}", height=36,
                fg_color=color, hover_color=P["bh"],
                text_color="#fff" if color != P["gold"] else "#1a1a1a",
                font=ctk.CTkFont(size=10, weight="bold"),
                corner_radius=8,
                command=lambda l=loc: s._sort_to("VAC", l)
            ).pack(side="left", fill="x", expand=True, padx=2)

        row3 = ctk.CTkFrame(btn_frame, fg_color="transparent")
        row3.pack(fill="x", padx=8, pady=2)
        ctk.CTkLabel(row3, text="🚑", font=ctk.CTkFont(size=14)).pack(side="left", padx=4)
        ctk.CTkButton(
            row3, text="ПМП → Город", height=36,
            fg_color=P["accent"], hover_color=P["ah"],
            text_color="#fff", font=ctk.CTkFont(size=10, weight="bold"),
            corner_radius=8, command=lambda: s._sort_to("PMP", "ELSH")
        ).pack(side="left", fill="x", expand=True, padx=2)
        ctk.CTkButton(
            row3, text="ПМП → Пригород", height=36,
            fg_color=P["gold"], hover_color="#FFE033",
            text_color="#1a1a1a", font=ctk.CTkFont(size=10, weight="bold"),
            corner_radius=8, command=lambda: s._sort_to("PMP", "suburb")
        ).pack(side="left", fill="x", expand=True, padx=2)

        row4 = ctk.CTkFrame(btn_frame, fg_color="transparent")
        row4.pack(fill="x", padx=8, pady=(4, 8))
        ctk.CTkButton(
            row4, text="⏭ Пропустить", height=30,
            fg_color=P["entry"], hover_color=P["bh"],
            border_width=1, border_color=P["border"],
            text_color=P["warn"], font=ctk.CTkFont(size=10),
            corner_radius=8, command=s._skip_one
        ).pack(side="left", fill="x", expand=True, padx=2)
        ctk.CTkButton(
            row4, text="🗑 Удалить", height=30,
            fg_color=P["red"], hover_color=P["rh"],
            text_color="#fff", font=ctk.CTkFont(size=10),
            corner_radius=8, command=s._delete_one
        ).pack(side="left", fill="x", expand=True, padx=2)

        s.bind("1", lambda e: s._sort_to("TAB", "ELSH"))
        s.bind("2", lambda e: s._sort_to("TAB", "Sandy"))
        s.bind("3", lambda e: s._sort_to("TAB", "Paleto"))
        s.bind("4", lambda e: s._sort_to("VAC", "ELSH"))
        s.bind("5", lambda e: s._sort_to("VAC", "Sandy"))
        s.bind("6", lambda e: s._sort_to("VAC", "Paleto"))
        s.bind("7", lambda e: s._sort_to("PMP", "ELSH"))
        s.bind("8", lambda e: s._sort_to("PMP", "suburb"))
        s.bind("q", lambda e: s._skip_one())
        s.bind("<Left>", lambda e: s._show(s.idx - 1))
        s.bind("<Right>", lambda e: s._skip_one())
        s.bind("<Delete>", lambda e: s._delete_one())

    def _show(s, idx):
        if not s.files:
            s.img_lbl.configure(image=None, text="Все отсортировано!")
            return
        s.idx = max(0, min(idx, len(s.files) - 1))
        fp = s.files[s.idx]
        total = len(s.files)

        s.fname.configure(text=f"  {s.idx + 1}/{total}  {fp.name}")
        s.prog.set((s.idx + 1) / total)
        s.count_lbl.configure(
            text=" | ".join(f"{k}:{v}" for k, v in s.sorted_count.items() if v > 0)
        )

        try:
            pil = Image.open(fp)
            r = min(960 / pil.width, 420 / pil.height)
            pil = pil.resize((int(pil.width * r), int(pil.height * r)), Image.LANCZOS)
            s.photo = ImageTk.PhotoImage(pil)
            s.img_lbl.configure(image=s.photo, text="")
        except:
            s.img_lbl.configure(image=None, text="Ошибка загрузки")

        s.auto_lbl.configure(text="Анализирую...", text_color=P["warn"])
        threading.Thread(target=s._auto_detect, args=(fp,), daemon=True).start()

    def _auto_detect(s, fp):
        try:
            r = s.az.run(fp, wd=False)
            if r.ok:
                hint = f"💡 Система думает: {r.cat.value} | {r.hosp.value} ({r.method})"
                color = P["ok"]
            else:
                hint = f"❓ Не удалось определить: {r.err or '?'}"
                color = P["warn"]
        except Exception as e:
            hint = f"Ошибка анализа: {e}"
            color = P["err"]

        def safe_update():
            try:
                if s.winfo_exists():
                    s.auto_lbl.configure(text=hint, text_color=color)
            except:
                pass

        try:
            s.after(0, safe_update)
        except:
            pass

    def _skip_one(s):
        if not s.files: return
        s.files.pop(s.idx)
        if not s.files:
            s.img_lbl.configure(image=None, text="Все файлы обработаны!")
            return
        if s.idx >= len(s.files):
            s.idx = max(0, len(s.files) - 1)
        s._show(s.idx)

    def _delete_one(s):
        if not s.files: return
        try:
            s.files[s.idx].unlink()
        except:
            pass
        s.files.pop(s.idx)
        if not s.files:
            s.img_lbl.configure(image=None, text="Все файлы обработаны!")
            return
        if s.idx >= len(s.files):
            s.idx = max(0, len(s.files) - 1)
        s._show(s.idx)

    def _sort_to(s, cat, loc):
        if not s.files:
            return
        fp = s.files[s.idx]

        cat_names = {"TAB": "Таблетки", "VAC": "Вакцины", "PMP": "ПМП"}
        cat_name = cat_names.get(cat, cat)

        if cat == "PMP":
            folder_name = "ПМП - Город" if loc == "ELSH" else "ПМП - Пригород"
        else:
            loc_names = {"ELSH": "ELSH", "Sandy": "Sandy Shores",
                         "Paleto": "Paleto Bay"}
            folder_name = f"{cat_name} - {loc_names.get(loc, loc)}"

        dest_dir = s.output_dir / folder_name
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / fp.name
        n = 1
        while dest.exists():
            dest = dest_dir / f"{fp.stem}_{n}{fp.suffix}"
            n += 1

        try:
            shutil.move(str(fp), str(dest))
        except:
            try:
                shutil.copy2(str(fp), str(dest))
                fp.unlink()
            except:
                s._log(f"  ❌ Ошибка перемещения {fp.name}", "error")
                return

        _play_sort_sound()

        threading.Thread(
            target=s._learn_move,
            args=(dest, cat, loc),
            daemon=True
        ).start()

        key = f"PMP_{'city' if loc == 'ELSH' else 'suburb'}" \
            if cat == "PMP" else loc
        s.sorted_count[key] = s.sorted_count.get(key, 0) + 1
        s._log(f"  ✅ {fp.name} → {folder_name}", "success")

        s.files.pop(s.idx)
        if s.idx >= len(s.files):
            s.idx = max(0, len(s.files) - 1)
        s._show(s.idx)


# ═══════════════════════════════════════════
#  ПРОСМОТР И ИСПРАВЛЕНИЕ ПАПОК
# ═══════════════════════════════════════════
class FolderReviewWindow(ctk.CTkToplevel):
    def __init__(s, parent, cfg, az, log_fn, location_db, trigger_db, default_dir=None):
        super().__init__(parent)
        s.title("Просмотр и исправление")
        s.configure(fg_color=P["bg"])
        s.transient(parent)

        s.cfg = cfg;
        s.az = az;
        s._log = log_fn
        s.location_db = location_db;
        s.trigger_db = trigger_db
        s.base_dir = None;
        s.folders = [];
        s.current_folder = None
        s.files = [];
        s.idx = 0;
        s.photo = None

        sw, sh = s.winfo_screenwidth(), s.winfo_screenheight()
        w = min(1200, sw - 20)
        h = sh - 60
        s.geometry(f"{w}x{h}+{(sw - w) // 2}+0")
        s._build()

        if default_dir and Path(default_dir).is_dir():
            s.base_dir = Path(default_dir)
            s._load_folders()

    def _build(s):
        hf = ctk.CTkFrame(s, fg_color=P["card"], corner_radius=0, height=50)
        hf.pack(fill="x");
        hf.pack_propagate(False)
        ctk.CTkLabel(hf, text="📂 Просмотр и исправление",
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=P["accent"]).pack(side="left", padx=16)
        ctk.CTkButton(hf, text="Выбрать другую папку", height=32,
                      fg_color=P["blue"], hover_color="#2563EB",
                      text_color="#fff", font=ctk.CTkFont(size=10),
                      command=s._select_base).pack(side="right", padx=16)

        tip = ctk.CTkFrame(s, fg_color=P["entry"], corner_radius=6,
                           border_width=1, border_color=P["border"])
        tip.pack(fill="x", padx=8, pady=(4, 2))
        ctk.CTkLabel(tip,
                     text="💡 Выберите папку слева → смотрите скрин → "
                          "если не туда попал нажмите кнопку нужной папки. "
                          "Система запомнит и будет сортировать лучше.",
                     font=ctk.CTkFont(size=9), text_color=P["dim"],
                     wraplength=1060).pack(padx=8, pady=4)

        mn = ctk.CTkFrame(s, fg_color="transparent")
        mn.pack(fill="both", expand=True, padx=8, pady=6)
        mn.columnconfigure(0, weight=0, minsize=220)
        mn.columnconfigure(1, weight=1)
        mn.rowconfigure(0, weight=1)

        # ══ Левая панель — список папок ══
        lp = ctk.CTkFrame(mn, fg_color=P["card"], corner_radius=10)
        lp.grid(row=0, column=0, sticky="nsew", padx=(0, 4))

        ctk.CTkLabel(lp, text="Папки с результатами:",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=P["text"]).pack(padx=8, pady=(8, 4), anchor="w")

        s.folder_frame = ctk.CTkScrollableFrame(lp, fg_color="transparent")
        s.folder_frame.pack(fill="both", expand=True, padx=4, pady=4)

        # ══ Правая панель — скрин + кнопки ══
        rp = ctk.CTkFrame(mn, fg_color=P["card"], corner_radius=10)
        rp.grid(row=0, column=1, sticky="nsew")
        rp.rowconfigure(1, weight=1)
        rp.columnconfigure(0, weight=1)

        # Имя файла + прогресс
        top_f = ctk.CTkFrame(rp, fg_color="transparent")
        top_f.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 0))
        top_f.columnconfigure(0, weight=1)

        s.file_lbl = ctk.CTkLabel(top_f, text="",
                                  font=ctk.CTkFont(family="Consolas", size=9),
                                  text_color=P["t2"])
        s.file_lbl.grid(row=0, column=0, sticky="w")

        s.folder_info_lbl = ctk.CTkLabel(top_f, text="",
                                         font=ctk.CTkFont(size=10, weight="bold"),
                                         text_color=P["info"])
        s.folder_info_lbl.grid(row=1, column=0, sticky="w")

        s.prog_bar = ctk.CTkProgressBar(top_f, height=4,
                                        progress_color=P["accent"],
                                        fg_color=P["entry"])
        s.prog_bar.grid(row=2, column=0, sticky="ew", pady=(4, 0))
        s.prog_bar.set(0)

        # Превью скрина
        s.img_frame = ctk.CTkFrame(rp, fg_color=P["entry"], corner_radius=8)
        s.img_frame.grid(row=1, column=0, sticky="nsew", padx=8, pady=4)
        s.img_lbl = ctk.CTkLabel(s.img_frame, text="← Выберите папку слева")
        s.img_lbl.pack(expand=True)

        # Нижняя панель — кнопки действий
        bot = ctk.CTkFrame(rp, fg_color="transparent")
        bot.grid(row=2, column=0, sticky="ew", padx=8, pady=(0, 8))

        # Навигация
        nav = ctk.CTkFrame(bot, fg_color="transparent")
        nav.pack(fill="x", pady=(0, 4))

        ctk.CTkButton(nav, text="◀ Назад", width=90, height=32,
                      fg_color=P["entry"], hover_color=P["bh"],
                      border_width=1, border_color=P["border"],
                      text_color=P["t2"], corner_radius=8,
                      command=lambda: s._nav(-1)).pack(side="left")

        s.nav_lbl = ctk.CTkLabel(nav, text="0 / 0",
                                 font=ctk.CTkFont(size=10),
                                 text_color=P["dim"])
        s.nav_lbl.pack(side="left", padx=8)

        ctk.CTkButton(nav, text="✓ Верно, дальше", height=32,
                      fg_color=P["accent"], hover_color=P["ah"],
                      text_color="#fff",
                      font=ctk.CTkFont(size=10, weight="bold"),
                      corner_radius=8,
                      command=lambda: s._nav(1)).pack(side="left",
                                                      fill="x", expand=True, padx=4)

        ctk.CTkButton(nav, text="🗑 Удалить", width=90, height=32,
                      fg_color=P["red"], hover_color=P["rh"],
                      text_color="#fff", corner_radius=8,
                      command=s._delete).pack(side="right")

        # Кнопки перемещения — такие же как в QuickSort
        move_sec = ctk.CTkFrame(bot, fg_color=P["entry"],
                                corner_radius=8,
                                border_width=1,
                                border_color=P["border"])
        move_sec.pack(fill="x")

        ctk.CTkLabel(move_sec,
                     text="Не туда попал? Выбери куда переместить:",
                     font=ctk.CTkFont(size=10, weight="bold"),
                     text_color=P["text"]).pack(pady=(6, 4))

        # Таблетки
        row1 = ctk.CTkFrame(move_sec, fg_color="transparent")
        row1.pack(fill="x", padx=8, pady=2)
        ctk.CTkLabel(row1, text="💊",
                     font=ctk.CTkFont(size=13)).pack(side="left", padx=4)
        for name, loc, color in [("Табл→ELSH", "ELSH", P["accent"]),
                                 ("Табл→Sandy", "Sandy", P["gold"]),
                                 ("Табл→Paleto", "Paleto", P["purple"])]:
            ctk.CTkButton(
                row1, text=name, height=32,
                fg_color=color, hover_color=P["bh"],
                text_color="#fff" if color != P["gold"] else "#1a1a1a",
                font=ctk.CTkFont(size=10, weight="bold"),
                corner_radius=8,
                command=lambda l=loc: s._move_to_cat("TAB", l)
            ).pack(side="left", fill="x", expand=True, padx=2)

        # Вакцины
        row2 = ctk.CTkFrame(move_sec, fg_color="transparent")
        row2.pack(fill="x", padx=8, pady=2)
        ctk.CTkLabel(row2, text="💉",
                     font=ctk.CTkFont(size=13)).pack(side="left", padx=4)
        for name, loc, color in [("Вакц→ELSH", "ELSH", P["accent"]),
                                 ("Вакц→Sandy", "Sandy", P["gold"]),
                                 ("Вакц→Paleto", "Paleto", P["purple"])]:
            ctk.CTkButton(
                row2, text=name, height=32,
                fg_color=color, hover_color=P["bh"],
                text_color="#fff" if color != P["gold"] else "#1a1a1a",
                font=ctk.CTkFont(size=10, weight="bold"),
                corner_radius=8,
                command=lambda l=loc: s._move_to_cat("VAC", l)
            ).pack(side="left", fill="x", expand=True, padx=2)

        # ПМП
        row3 = ctk.CTkFrame(move_sec, fg_color="transparent")
        row3.pack(fill="x", padx=8, pady=2)
        ctk.CTkLabel(row3, text="🚑",
                     font=ctk.CTkFont(size=13)).pack(side="left", padx=4)
        ctk.CTkButton(
            row3, text="ПМП → Город", height=32,
            fg_color=P["accent"], hover_color=P["ah"],
            text_color="#fff",
            font=ctk.CTkFont(size=10, weight="bold"),
            corner_radius=8,
            command=lambda: s._move_to_cat("PMP", "ELSH")
        ).pack(side="left", fill="x", expand=True, padx=2)
        ctk.CTkButton(
            row3, text="ПМП → Пригород", height=32,
            fg_color=P["gold"], hover_color="#FFE033",
            text_color="#1a1a1a",
            font=ctk.CTkFont(size=10, weight="bold"),
            corner_radius=8,
            command=lambda: s._move_to_cat("PMP", "suburb")
        ).pack(side="left", fill="x", expand=True, padx=2)

        ctk.CTkFrame(move_sec, height=1,
                     fg_color=P["border"]).pack(fill="x", padx=8, pady=4)

        # Произвольные папки (если есть нестандартные)
        ctk.CTkLabel(move_sec,
                     text="Или в конкретную папку:",
                     font=ctk.CTkFont(size=9),
                     text_color=P["dim"]).pack(anchor="w", padx=8)

        s.move_btns_frame = ctk.CTkScrollableFrame(
            move_sec, fg_color="transparent", height=60)
        s.move_btns_frame.pack(fill="x", padx=8, pady=(0, 8))

        # Горячие клавиши
        s.bind("1", lambda e: s._move_to_cat("TAB", "ELSH"))
        s.bind("2", lambda e: s._move_to_cat("TAB", "Sandy"))
        s.bind("3", lambda e: s._move_to_cat("TAB", "Paleto"))
        s.bind("4", lambda e: s._move_to_cat("VAC", "ELSH"))
        s.bind("5", lambda e: s._move_to_cat("VAC", "Sandy"))
        s.bind("6", lambda e: s._move_to_cat("VAC", "Paleto"))
        s.bind("7", lambda e: s._move_to_cat("PMP", "ELSH"))
        s.bind("8", lambda e: s._move_to_cat("PMP", "suburb"))
        s.bind("<Right>", lambda e: s._nav(1))
        s.bind("<Left>", lambda e: s._nav(-1))
        s.bind("<Delete>", lambda e: s._delete())

    def _select_base(s):
        d = filedialog.askdirectory(title="Папка с результатами сортировки")
        if not d: return
        s.base_dir = Path(d)
        s._load_folders()

    def _load_folders(s):
        for w in s.folder_frame.winfo_children(): w.destroy()
        s.folders = sorted([f for f in s.base_dir.iterdir() if f.is_dir()])
        if not s.folders:
            ctk.CTkLabel(s.folder_frame, text="Папок нет",
                         font=ctk.CTkFont(size=10),
                         text_color=P["dim"]).pack(pady=8)
            return
        for folder in s.folders:
            count = len([f for f in folder.iterdir()
                         if f.is_file() and f.suffix.lower() in EXTS])
            color = P["accent"] if count > 0 else P["dim"]
            ctk.CTkButton(
                s.folder_frame,
                text=f"{folder.name}\n({count} скринов)",
                height=40,
                fg_color=P["entry"], hover_color=P["bh"],
                border_width=1, border_color=P["border"],
                text_color=color,
                font=ctk.CTkFont(size=9), anchor="w",
                command=lambda f=folder: s._open_folder(f)
            ).pack(fill="x", pady=2)

    def _open_folder(s, folder):
        s.current_folder = folder
        s.files = sorted([f for f in folder.iterdir()
                          if f.is_file() and f.suffix.lower() in EXTS])
        s.idx = 0

        # Обновляем кнопки произвольных папок
        for w in s.move_btns_frame.winfo_children(): w.destroy()
        for target in s.folders:
            if target == folder: continue
            ctk.CTkButton(
                s.move_btns_frame,
                text=f"→ {target.name}",
                height=24,
                fg_color=P["entry"], hover_color=P["accent"],
                border_width=1, border_color=P["border"],
                text_color=P["t2"], font=ctk.CTkFont(size=8),
                command=lambda t=target: s._move_to_folder(t)
            ).pack(fill="x", pady=1)

        s._show_file()

    def _show_file(s):
        if not s.files:
            s.img_lbl.configure(image=None, text="✅ В этой папке пусто")
            s.file_lbl.configure(text="")
            s.folder_info_lbl.configure(text="")
            s.nav_lbl.configure(text="0 / 0")
            s.prog_bar.set(0)
            return

        s.idx = max(0, min(s.idx, len(s.files) - 1))
        fp = s.files[s.idx]
        total = len(s.files)

        s.file_lbl.configure(text=f"  {fp.name}")
        s.folder_info_lbl.configure(
            text=f"📁 Папка: {s.current_folder.name}",
            text_color=P["info"])
        s.nav_lbl.configure(text=f"{s.idx + 1} / {total}")
        s.prog_bar.set((s.idx + 1) / total)

        try:
            pil = Image.open(fp)
            # Подбираем размер под окно
            r = min(750 / pil.width, 380 / pil.height)
            pil = pil.resize((int(pil.width * r),
                              int(pil.height * r)), Image.LANCZOS)
            s.photo = ImageTk.PhotoImage(pil)
            s.img_lbl.configure(image=s.photo, text="")
        except:
            s.img_lbl.configure(image=None, text="Ошибка загрузки")

    def _move_to_cat(s, cat, loc):
        """Перемещение в папку по категории и локации."""
        if not s.files: return
        fp = s.files[s.idx]

        cat_names = {"TAB": "Таблетки", "VAC": "Вакцины", "PMP": "ПМП"}
        cat_name = cat_names.get(cat, cat)

        if cat == "PMP":
            folder_name = "ПМП - Город" if loc == "ELSH" else "ПМП - Пригород"
        else:
            loc_names = {"ELSH": "ELSH", "Sandy": "Sandy Shores",
                         "Paleto": "Paleto Bay"}
            folder_name = f"{cat_name} - {loc_names.get(loc, loc)}"

        # Находим или создаём целевую папку
        target = s.base_dir / folder_name
        target.mkdir(parents=True, exist_ok=True)

        # Если это та же папка
        if target == s.current_folder:
            s._log(f"  ℹ️ Скрин уже в {folder_name}", "dim")
            s._nav(1);
            return

        s._do_move(fp, target, cat, loc, folder_name)

    def _move_to_folder(s, target_folder):
        """Перемещение в конкретную папку."""
        if not s.files: return
        fp = s.files[s.idx]
        s._do_move(fp, target_folder, "", "", target_folder.name)

    def _do_move(s, fp, target, cat, loc, folder_name):
        """Общая логика перемещения."""
        dest = target / fp.name
        n = 1
        while dest.exists():
            dest = target / f"{fp.stem}_{n}{fp.suffix}"
            n += 1

        moved_dest = dest  # сохраняем путь назначения

        try:
            shutil.move(str(fp), str(moved_dest))
        except Exception as e:
            try:
                shutil.copy2(str(fp), str(moved_dest))
                fp.unlink()
            except:
                s._log(f"  ❌ Ошибка перемещения: {e}", "error")
                return

        _play_sort_sound()

        s._log(
            f"  🔄 {fp.name}: {s.current_folder.name} → {folder_name}",
            "success")

        # Обучение в фоне — передаём moved_dest как Path
        threading.Thread(
            target=s._learn_move,
            args=(moved_dest, cat, loc, folder_name),
            daemon=True
        ).start()

        s.files.pop(s.idx)
        if s.idx >= len(s.files):
            s.idx = max(0, len(s.files) - 1)
        s._show_file()
        s.after(500, s._load_folders)

    def _learn_move(s, fp, cat, loc, folder_name):
        if not getattr(s.az, 'is_pro', False):
            return
        """Обучение на основе ручного перемещения."""
        try:
            img = _ld(fp)
            if img is None: return
            ctx = ImageContext(img, s.cfg)
            feats = extract_features(ctx)

            # Определяем локацию
            if loc and loc not in ("suburb", "UNK", ""):
                learn_loc = loc
            else:
                loc_map = {"elsh": "ELSH", "sandy": "Sandy", "paleto": "Paleto"}
                learn_loc = None
                fn_lower = folder_name.lower()
                for key, val in loc_map.items():
                    if key in fn_lower:
                        learn_loc = val
                        break

            if learn_loc and feats:
                add_location_sample(s.location_db, feats, learn_loc, fp.name)

            # Определяем категорию
            learn_cat = cat if cat in ("TAB", "VAC", "PMP") else None
            if not learn_cat:
                cat_map = {"таблетки": "TAB", "табл": "TAB",
                           "вакцин": "VAC", "пмп": "PMP"}
                fn_lower = folder_name.lower()
                for key, val in cat_map.items():
                    if key in fn_lower:
                        learn_cat = val
                        break

            if learn_cat:
                ocr_texts = []
                for rx, ry, rw, rh in s.cfg.CHAT_SCAN_ROIS[:1]:
                    roi = ctx.crop(rx, ry, rw, rh)
                    if roi is None:
                        continue
                    t, _ = _ocr.read(roi, mc=0.1, mh=3, ml=2)
                    if t:
                        ocr_texts.append(t.lower().strip())
                    break
                add_trigger_sample(s.trigger_db, fp.name,
                                   learn_cat, ocr_texts, feats)
        except Exception as e:
            logger.error(f"learn_move: {e}")

    def _nav(s, delta):
        s.idx = max(0, min(s.idx + delta, len(s.files) - 1))
        s._show_file()

    def _delete(s):
        if not s.files: return
        try:
            s.files[s.idx].unlink()
        except:
            pass
        s.files.pop(s.idx)
        if s.idx >= len(s.files):
            s.idx = max(0, len(s.files) - 1)
        s._show_file()


# ═══════════════════════════════════════════
#  АВТООБУЧЕНИЕ ИЗ ПАПКИ
# ═══════════════════════════════════════════
class AutoLearnWindow(ctk.CTkToplevel):
    def __init__(s, parent, cfg, az, location_db, trigger_db, log_fn):
        super().__init__(parent)
        s.title("Автообучение из папки")
        s.configure(fg_color=P["bg"])
        s.transient(parent)

        s.cfg = cfg;
        s.az = az
        s.location_db = location_db
        s.trigger_db = trigger_db
        s.log_fn = log_fn

        s.files = []
        s.groups = {}  # {loc: [fp, ...]}
        s.unassigned = []  # скрины которые не удалось определить
        s.photo = None
        s.current_group = None
        s.current_idx = 0
        s._stop = threading.Event()
        s._analyzing = False

        sw, sh = s.winfo_screenwidth(), s.winfo_screenheight()
        s.geometry(f"1200x800+{(sw - 1200) // 2}+{(sh - 800) // 2}")
        s._build()

    def _build(s):
        # Шапка
        hf = ctk.CTkFrame(s, fg_color=P["card"], corner_radius=0, height=55)
        hf.pack(fill="x");
        hf.pack_propagate(False)
        ctk.CTkLabel(hf, text="🤖 Автообучение из папки",
                     font=ctk.CTkFont(size=15, weight="bold"),
                     text_color=P["accent"]).pack(side="left", padx=16, pady=14)
        s.status_lbl = ctk.CTkLabel(hf, text="Выберите папку со скринами",
                                    font=ctk.CTkFont(size=10),
                                    text_color=P["gold"])
        s.status_lbl.pack(side="right", padx=16)

        # Подсказка
        tip = ctk.CTkFrame(s, fg_color=P["entry"], corner_radius=6,
                           border_width=1, border_color=P["border"])
        tip.pack(fill="x", padx=8, pady=(4, 2))
        ctk.CTkLabel(tip,
                     text="💡 Как работает: 1) Выбери папку со скринами  "
                          "2) Программа сама попробует определить больницу по цветам  "
                          "3) Ты подтверждаешь или исправляешь  "
                          "4) Система обучается на каждом скрине",
                     font=ctk.CTkFont(size=9), text_color=P["dim"],
                     wraplength=1140).pack(padx=8, pady=4)

        mn = ctk.CTkFrame(s, fg_color="transparent")
        mn.pack(fill="both", expand=True, padx=8, pady=6)
        mn.columnconfigure(0, weight=0, minsize=280)
        mn.columnconfigure(1, weight=1)
        mn.rowconfigure(0, weight=1)

        # ══ Левая панель — управление ══
        lp = ctk.CTkFrame(mn, fg_color=P["card"], corner_radius=10)
        lp.grid(row=0, column=0, sticky="nsew", padx=(0, 4))

        # Выбор папки и запуск
        ctk.CTkLabel(lp, text="Шаг 1: Выбери папку",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=P["accent"]).pack(padx=12, pady=(12, 4), anchor="w")

        s.folder_lbl = ctk.CTkLabel(lp, text="Папка не выбрана",
                                    font=ctk.CTkFont(size=9),
                                    text_color=P["dim"], wraplength=240)
        s.folder_lbl.pack(padx=12, anchor="w")

        ctk.CTkButton(lp, text="📁 Выбрать папку", height=36,
                      fg_color=P["blue"], hover_color="#2563EB",
                      text_color="#fff",
                      font=ctk.CTkFont(size=11, weight="bold"),
                      command=s._select_folder).pack(fill="x", padx=12, pady=6)

        ctk.CTkFrame(lp, height=1, fg_color=P["border"]).pack(fill="x", padx=8, pady=4)

        ctk.CTkLabel(lp, text="Шаг 2: Анализ",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=P["accent"]).pack(padx=12, pady=(4, 4), anchor="w")

        s.prog = ctk.CTkProgressBar(lp, height=8,
                                    progress_color=P["accent"],
                                    fg_color=P["entry"])
        s.prog.pack(fill="x", padx=12, pady=(0, 4))
        s.prog.set(0)

        s.prog_lbl = ctk.CTkLabel(lp, text="",
                                  font=ctk.CTkFont(size=9),
                                  text_color=P["dim"])
        s.prog_lbl.pack(padx=12, anchor="w")

        bf = ctk.CTkFrame(lp, fg_color="transparent")
        bf.pack(fill="x", padx=12, pady=6)
        s.run_btn = ctk.CTkButton(bf, text="▶ Запустить анализ", height=36,
                                  fg_color=P["accent"], hover_color=P["ah"],
                                  text_color="#fff",
                                  font=ctk.CTkFont(size=11, weight="bold"),
                                  command=s._start_analysis, state="disabled")
        s.run_btn.pack(side="left", fill="x", expand=True, padx=(0, 4))
        s.stop_btn = ctk.CTkButton(bf, text="⏹", height=36, width=40,
                                   fg_color=P["red"], hover_color=P["rh"],
                                   text_color="#fff",
                                   font=ctk.CTkFont(size=12),
                                   command=s._stop_analysis, state="disabled")
        s.stop_btn.pack(side="right")

        ctk.CTkFrame(lp, height=1, fg_color=P["border"]).pack(fill="x", padx=8, pady=4)

        # Результаты по группам
        ctk.CTkLabel(lp, text="Шаг 3: Подтверди группы",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=P["accent"]).pack(padx=12, pady=(4, 4), anchor="w")

        s.groups_frame = ctk.CTkScrollableFrame(lp, fg_color="transparent",
                                                height=200)
        s.groups_frame.pack(fill="x", padx=8, pady=4)

        ctk.CTkFrame(lp, height=1, fg_color=P["border"]).pack(fill="x", padx=8, pady=4)

        # Сохранить всё
        s.save_all_btn = ctk.CTkButton(lp, text="💾 Сохранить всё в базу",
                                       height=40,
                                       fg_color=P["ok"], hover_color="#1ea870",
                                       text_color="#fff",
                                       font=ctk.CTkFont(size=12, weight="bold"),
                                       command=s._save_all, state="disabled")
        s.save_all_btn.pack(fill="x", padx=12, pady=6)

        s.save_lbl = ctk.CTkLabel(lp, text="",
                                  font=ctk.CTkFont(size=9),
                                  text_color=P["dim"])
        s.save_lbl.pack(padx=12, pady=(0, 8))

        # ══ Правая панель — просмотр ══
        rp = ctk.CTkFrame(mn, fg_color=P["card"], corner_radius=10)
        rp.grid(row=0, column=1, sticky="nsew")
        rp.rowconfigure(1, weight=1)
        rp.columnconfigure(0, weight=1)

        # Инфо о текущем скрине
        info_f = ctk.CTkFrame(rp, fg_color="transparent")
        info_f.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 0))
        info_f.columnconfigure(0, weight=1)

        s.img_title = ctk.CTkLabel(info_f, text="",
                                   font=ctk.CTkFont(size=11, weight="bold"),
                                   text_color=P["text"])
        s.img_title.grid(row=0, column=0, sticky="w")

        s.img_sub = ctk.CTkLabel(info_f, text="",
                                 font=ctk.CTkFont(size=9),
                                 text_color=P["dim"])
        s.img_sub.grid(row=1, column=0, sticky="w")

        s.img_nav = ctk.CTkLabel(info_f, text="",
                                 font=ctk.CTkFont(size=10),
                                 text_color=P["t2"])
        s.img_nav.grid(row=0, column=1, sticky="e")

        # Превью
        s.img_frame = ctk.CTkFrame(rp, fg_color=P["entry"], corner_radius=8)
        s.img_frame.grid(row=1, column=0, sticky="nsew", padx=8, pady=4)
        s.img_lbl = ctk.CTkLabel(s.img_frame,
                                 text="После анализа здесь будут скрины")
        s.img_lbl.pack(expand=True)

        # Навигация внутри группы
        nav_f = ctk.CTkFrame(rp, fg_color="transparent")
        nav_f.grid(row=2, column=0, sticky="ew", padx=8, pady=(0, 4))

        ctk.CTkButton(nav_f, text="◀", width=60, height=30,
                      fg_color=P["entry"], hover_color=P["bh"],
                      text_color=P["t2"], corner_radius=8,
                      command=lambda: s._nav_img(-1)).pack(side="left")

        s.img_prog = ctk.CTkProgressBar(nav_f, height=4,
                                        progress_color=P["accent"],
                                        fg_color=P["entry"])
        s.img_prog.pack(side="left", fill="x", expand=True, padx=4)
        s.img_prog.set(0)

        ctk.CTkButton(nav_f, text="▶", width=60, height=30,
                      fg_color=P["accent"], hover_color=P["ah"],
                      text_color="#fff", corner_radius=8,
                      command=lambda: s._nav_img(1)).pack(side="right")

        # Кнопки подтверждения локации
        confirm_f = ctk.CTkFrame(rp, fg_color=P["entry"],
                                 corner_radius=8,
                                 border_width=1,
                                 border_color=P["border"])
        confirm_f.grid(row=3, column=0, sticky="ew", padx=8, pady=(0, 8))

        ctk.CTkLabel(confirm_f,
                     text="Где сделан этот скрин?",
                     font=ctk.CTkFont(size=10, weight="bold"),
                     text_color=P["text"]).pack(pady=(6, 4))

        btn_row = ctk.CTkFrame(confirm_f, fg_color="transparent")
        btn_row.pack(fill="x", padx=8, pady=(0, 8))

        for text, loc, color in [
            ("🏥 ELSH", "ELSH", P["accent"]),
            ("🏜 Sandy", "Sandy", P["gold"]),
            ("🌊 Paleto", "Paleto", P["purple"]),
            ("❓ Не знаю", "UNK", P["dim"]),
        ]:
            ctk.CTkButton(
                btn_row, text=text, height=38,
                fg_color=color, hover_color=P["bh"],
                text_color="#fff" if color != P["gold"] else "#1a1a1a",
                font=ctk.CTkFont(size=11, weight="bold"),
                corner_radius=8,
                command=lambda l=loc: s._assign_current(l)
            ).pack(side="left", fill="x", expand=True, padx=2)

        # Горячие клавиши
        s.bind("1", lambda e: s._assign_current("ELSH"))
        s.bind("2", lambda e: s._assign_current("Sandy"))
        s.bind("3", lambda e: s._assign_current("Paleto"))
        s.bind("4", lambda e: s._assign_current("UNK"))
        s.bind("<Left>", lambda e: s._nav_img(-1))
        s.bind("<Right>", lambda e: s._nav_img(1))

    # ══════════════════════════════════════
    #  ВЫБОР ПАПКИ
    # ══════════════════════════════════════
    def _select_folder(s):
        d = filedialog.askdirectory(title="Папка со скриншотами")
        if not d: return
        files = sorted([
            p for p in Path(d).iterdir()
            if p.is_file() and p.suffix.lower() in EXTS
        ])
        if not files:
            s.log_fn("  Папка пуста", "warning")
            return
        s.files = files
        s.folder_lbl.configure(
            text=f"{Path(d).name}\n{len(files)} скринов")
        s.run_btn.configure(state="normal")
        s.status_lbl.configure(
            text=f"Готово к анализу: {len(files)} скринов",
            text_color=P["ok"])

    # ══════════════════════════════════════
    #  АНАЛИЗ
    # ══════════════════════════════════════
    def _start_analysis(s):
        if not s.files: return
        s._stop.clear()
        s._analyzing = True
        s.groups = {"ELSH": [], "Sandy": [], "Paleto": [], "UNK": []}
        s.run_btn.configure(state="disabled")
        s.stop_btn.configure(state="normal")
        s.save_all_btn.configure(state="disabled")
        s.prog.set(0)
        threading.Thread(target=s._do_analysis, daemon=True).start()

    def _do_analysis(s):
        total = len(s.files)
        done = 0

        for fp in s.files:
            if s._stop.is_set():
                break

            done += 1
            progress = done / total

            try:
                img = _ld(fp)
                if img is None:
                    s.groups["UNK"].append({
                        "fp": fp, "loc": "UNK",
                        "conf": 0, "feats": {}, "auto": "UNK"
                    })
                    continue

                ctx = ImageContext(img, s.cfg)
                feats = extract_features(ctx)

                # Определяем локацию классическим методом
                cr = color_analyze_classic(ctx, feats)

                # Также спрашиваем базу знаний
                db_loc, db_conf, _ = predict_location_from_db(
                    s.location_db, feats)

                # Выбираем лучший вариант
                if db_conf >= 0.1 and db_loc != "Unsorted":
                    auto_loc = db_loc
                    conf = db_conf
                elif cr.winner != s.cfg.F_UNK and cr.conf >= 0.01:
                    loc_map = {
                        s.cfg.F_ELSH: "ELSH",
                        s.cfg.F_SANDY: "Sandy",
                        s.cfg.F_PALETO: "Paleto"
                    }
                    auto_loc = loc_map.get(cr.winner, "UNK")
                    conf = cr.conf
                else:
                    auto_loc = "UNK"
                    conf = 0.0

                entry = {
                    "fp": fp,
                    "loc": auto_loc,  # предсказание (можно изменить)
                    "auto": auto_loc,  # оригинальное предсказание
                    "conf": conf,
                    "feats": feats,
                    "cr_elsh": cr.elsh,
                    "cr_sandy": cr.sandy,
                    "cr_paleto": cr.paleto
                }

                s.groups[auto_loc].append(entry)

            except Exception as e:
                s.groups["UNK"].append({
                    "fp": fp, "loc": "UNK",
                    "conf": 0, "feats": {}, "auto": "UNK"
                })

            # Обновляем UI
            p = progress
            d2 = done
            s.after(0, lambda p=p, d=d2: s._update_progress(p, d, total))

        s.after(0, s._analysis_done)

    def _update_progress(s, progress, done, total):
        s.prog.set(progress)
        s.prog_lbl.configure(
            text=f"Проанализировано: {done}/{total}")

    def _analysis_done(s):
        s._analyzing = False
        s.run_btn.configure(state="normal")
        s.stop_btn.configure(state="disabled")

        total = sum(len(v) for v in s.groups.values())
        elsh = len(s.groups.get("ELSH", []))
        sandy = len(s.groups.get("Sandy", []))
        paleto = len(s.groups.get("Paleto", []))
        unk = len(s.groups.get("UNK", []))

        s.status_lbl.configure(
            text=f"Готово: ELSH={elsh} Sandy={sandy} Paleto={paleto} Не знаю={unk}",
            text_color=P["ok"])
        s.prog.set(1.0)
        s.prog_lbl.configure(text=f"Всего: {total} скринов")

        s._build_groups_ui()
        s.save_all_btn.configure(state="normal")

        # Показываем первую группу
        if elsh > 0:
            s._show_group("ELSH")
        elif sandy > 0:
            s._show_group("Sandy")
        elif paleto > 0:
            s._show_group("Paleto")
        elif unk > 0:
            s._show_group("UNK")

    def _stop_analysis(s):
        s._stop.set()
        s.stop_btn.configure(state="disabled")

    # ══════════════════════════════════════
    #  UI ГРУПП
    # ══════════════════════════════════════
    def _build_groups_ui(s):
        for w in s.groups_frame.winfo_children():
            w.destroy()

        colors = {
            "ELSH": P["accent"], "Sandy": P["gold"],
            "Paleto": P["purple"], "UNK": P["dim"]
        }
        icons = {
            "ELSH": "🏥", "Sandy": "🏜", "Paleto": "🌊", "UNK": "❓"
        }

        for loc in ["ELSH", "Sandy", "Paleto", "UNK"]:
            items = s.groups.get(loc, [])
            if not items: continue

            color = colors[loc]
            icon = icons[loc]

            btn = ctk.CTkButton(
                s.groups_frame,
                text=f"{icon} {loc}: {len(items)} скринов",
                height=36,
                fg_color=color if loc != "UNK" else P["entry"],
                hover_color=P["bh"],
                border_width=1 if loc == "UNK" else 0,
                border_color=P["border"],
                text_color="#fff" if color != P["gold"] else "#1a1a1a",
                font=ctk.CTkFont(size=10, weight="bold"),
                corner_radius=8,
                command=lambda l=loc: s._show_group(l)
            )
            btn.pack(fill="x", pady=2)

    def _show_group(s, loc):
        s.current_group = loc
        s.current_idx = 0
        items = s.groups.get(loc, [])

        colors = {"ELSH": P["accent"], "Sandy": P["gold"],
                  "Paleto": P["purple"], "UNK": P["dim"]}
        icons = {"ELSH": "🏥", "Sandy": "🏜",
                 "Paleto": "🌊", "UNK": "❓"}

        s.img_title.configure(
            text=f"{icons.get(loc, '?')} Группа: {loc}",
            text_color=colors.get(loc, P["text"]))

        if items:
            s._show_img(0)
        else:
            s.img_lbl.configure(image=None, text="Группа пуста")

    def _show_img(s, idx):
        items = s.groups.get(s.current_group, [])
        if not items: return

        s.current_idx = max(0, min(idx, len(items) - 1))
        item = items[s.current_idx]
        fp = item["fp"]
        total = len(items)

        s.img_nav.configure(
            text=f"{s.current_idx + 1} / {total}")
        s.img_prog.set((s.current_idx + 1) / total)

        # Показываем уверенность и предсказание
        conf = item.get("conf", 0)
        auto = item.get("auto", "?")
        assigned = item.get("loc", "?")

        if assigned != auto:
            sub = f"Авто: {auto} → Изменено: {assigned} | {fp.name}"
        else:
            sub = f"Авто: {auto} ({conf:.0%}) | {fp.name}"

        s.img_sub.configure(text=sub)

        try:
            pil = Image.open(fp)
            r = min(800 / pil.width, 400 / pil.height)
            pil = pil.resize((int(pil.width * r),
                              int(pil.height * r)), Image.LANCZOS)
            s.photo = ImageTk.PhotoImage(pil)
            s.img_lbl.configure(image=s.photo, text="")
        except:
            s.img_lbl.configure(image=None, text="Ошибка загрузки")

    def _nav_img(s, delta):
        items = s.groups.get(s.current_group, [])
        if not items: return
        new_idx = s.current_idx + delta
        if 0 <= new_idx < len(items):
            s._show_img(new_idx)

    # ══════════════════════════════════════
    #  НАЗНАЧЕНИЕ ЛОКАЦИИ
    # ══════════════════════════════════════
    def _assign_current(s, loc):
        """Назначаем локацию текущему скрину и переходим к следующему."""
        if not s.current_group: return
        items = s.groups.get(s.current_group, [])
        if not items: return

        item = items[s.current_idx]
        old_loc = item["loc"]

        # Если локация изменилась — перемещаем в другую группу
        if loc != s.current_group:
            item["loc"] = loc
            items.pop(s.current_idx)
            if loc not in s.groups:
                s.groups[loc] = []
            s.groups[loc].append(item)
            s._build_groups_ui()

            s.log_fn(
                f"  🔄 {item['fp'].name}: {old_loc} → {loc}", "info")
        else:
            # Локация та же — просто идём дальше
            pass

        # Переходим к следующему
        remaining = s.groups.get(s.current_group, [])
        if s.current_idx >= len(remaining):
            s.current_idx = max(0, len(remaining) - 1)

        if remaining:
            s._show_img(s.current_idx)
        else:
            s.img_lbl.configure(image=None,
                                text=f"✅ Группа {s.current_group} проверена!")
            s.img_sub.configure(text="")
            s.img_nav.configure(text="")

    # ══════════════════════════════════════
    #  СОХРАНЕНИЕ
    # ══════════════════════════════════════
    def _save_all(s):
        """Сохраняем все размеченные скрины в базу."""
        saved = 0;
        skipped = 0

        for loc, items in s.groups.items():
            if loc == "UNK":
                skipped += len(items)
                continue

            for item in items:
                feats = item.get("feats", {})
                if not feats:
                    skipped += 1
                    continue

                try:
                    add_location_sample(
                        s.location_db, feats, loc, item["fp"].name)
                    saved += 1
                except:
                    skipped += 1

        save_location_db(s.location_db)

        s.save_lbl.configure(
            text=f"✅ Сохранено: {saved} | Пропущено: {skipped}",
            text_color=P["ok"])
        s.log_fn(
            f"  ✅ Автообучение: сохранено {saved} примеров", "success")
        _play_done_sound()

        s.status_lbl.configure(
            text=f"Сохранено {saved} примеров в базу знаний",
            text_color=P["ok"])


# ═══════════════════════════════════════════
#  ОКНО РАЗМЕТКИ СКРИНШОТОВ
# ═══════════════════════════════════════════
class LabelWindow(ctk.CTkToplevel):
    def __init__(s, parent, cfg, az, trigger_db, location_db, log_fn):
        super().__init__(parent)
        s.title("Разметка скриншотов")
        s.configure(fg_color=P["bg"])
        s.transient(parent)

        s.cfg = cfg;
        s.az = az
        s.trigger_db = trigger_db
        s.location_db = location_db
        s.log_fn = log_fn

        s.files = [];
        s.idx = 0;
        s.photo = None
        s.current_features = {};
        s.current_ocr = []
        s.is_batch = False
        s._batch_stop_event = threading.Event()  # ПЕРЕИМЕНОВАНО

        sw, sh = s.winfo_screenwidth(), s.winfo_screenheight()
        s.geometry(f"1250x850+{(sw - 1250) // 2}+{(sh - 850) // 2}")
        s._build();
        s._update_stats()

    def _build(s):
        hf = ctk.CTkFrame(s, fg_color=P["card"], corner_radius=0, height=55)
        hf.pack(fill="x");
        hf.pack_propagate(False)
        ctk.CTkLabel(hf, text="Разметка и обучение",
                     font=ctk.CTkFont(size=15, weight="bold"),
                     text_color=P["accent"]).pack(side="left", padx=16, pady=14)
        s.stats_lbl = ctk.CTkLabel(hf, text="", font=ctk.CTkFont(size=10),
                                   text_color=P["gold"])
        s.stats_lbl.pack(side="right", padx=16)

        mn = ctk.CTkFrame(s, fg_color="transparent")
        mn.pack(fill="both", expand=True, padx=8, pady=6)
        mn.columnconfigure(0, weight=2);
        mn.columnconfigure(1, weight=1)
        mn.rowconfigure(0, weight=1)

        lp = ctk.CTkFrame(mn, fg_color=P["card"], corner_radius=10)
        lp.grid(row=0, column=0, sticky="nsew", padx=(0, 4))

        batch_sec = ctk.CTkFrame(lp, fg_color=P["entry"], corner_radius=8,
                                 border_width=1, border_color=P["border"])
        batch_sec.pack(fill="x", padx=8, pady=(8, 4))

        ctk.CTkLabel(batch_sec, text="⚡ Быстрое обучение (вся папка = одна категория)",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=P["gold"]).pack(padx=8, pady=(6, 2), anchor="w")

        bf1 = ctk.CTkFrame(batch_sec, fg_color="transparent")
        bf1.pack(fill="x", padx=8, pady=2)
        ctk.CTkLabel(bf1, text="Категория:", font=ctk.CTkFont(size=10),
                     text_color=P["t2"]).pack(side="left")
        s.batch_cat_var = ctk.StringVar(value="TAB - Таблетки")
        ctk.CTkOptionMenu(bf1, values=["TAB - Таблетки", "VAC - Вакцины", "PMP - ПМП"],
                          variable=s.batch_cat_var, width=160, height=28,
                          fg_color=P["bg"], button_color=P["accent"],
                          dropdown_fg_color=P["card"], text_color=P["text"],
                          font=ctk.CTkFont(size=10)).pack(side="right")

        bf2 = ctk.CTkFrame(batch_sec, fg_color="transparent")
        bf2.pack(fill="x", padx=8, pady=2)
        ctk.CTkLabel(bf2, text="Больница:", font=ctk.CTkFont(size=10),
                     text_color=P["t2"]).pack(side="left")
        s.batch_loc_var = ctk.StringVar(value="ELSH")
        ctk.CTkOptionMenu(bf2, values=["ELSH", "Sandy", "Paleto", "Неизвестно"],
                          variable=s.batch_loc_var, width=160, height=28,
                          fg_color=P["bg"], button_color=P["gold"],
                          dropdown_fg_color=P["card"], text_color=P["text"],
                          font=ctk.CTkFont(size=10)).pack(side="right")

        s.batch_pmp_frame = ctk.CTkFrame(batch_sec, fg_color="transparent")
        s.batch_pmp_var = ctk.StringVar(value="city")
        ctk.CTkLabel(s.batch_pmp_frame, text="Район ПМП:",
                     font=ctk.CTkFont(size=10), text_color=P["orange"]).pack(side="left", padx=8)
        ctk.CTkRadioButton(s.batch_pmp_frame, text="Город", variable=s.batch_pmp_var,
                           value="city", text_color=P["accent"],
                           font=ctk.CTkFont(size=10)).pack(side="left", padx=4)
        ctk.CTkRadioButton(s.batch_pmp_frame, text="Пригород", variable=s.batch_pmp_var,
                           value="suburb", text_color=P["gold"],
                           font=ctk.CTkFont(size=10)).pack(side="left", padx=4)

        s.batch_cat_var.trace_add("write", s._on_batch_cat_change)

        bf3 = ctk.CTkFrame(batch_sec, fg_color="transparent")
        bf3.pack(fill="x", padx=8, pady=(4, 8))
        s.batch_btn = ctk.CTkButton(
            bf3, text="📁 Выбрать папку и обучить", height=38,
            fg_color=P["gold"], hover_color="#FFE033",
            text_color="#1a1a1a", font=ctk.CTkFont(size=12, weight="bold"),
            corner_radius=8, command=s._batch_train)
        s.batch_btn.pack(side="left", fill="x", expand=True, padx=(0, 4))
        s.batch_stop_btn = ctk.CTkButton(
            bf3, text="Стоп", height=38, width=60,
            fg_color=P["red"], hover_color=P["rh"],
            text_color="#fff", font=ctk.CTkFont(size=11),
            corner_radius=8, command=s._on_batch_stop_click, state="disabled")
        s.batch_stop_btn.pack(side="right")

        s.batch_prog = ctk.CTkProgressBar(batch_sec, height=5,
                                          progress_color=P["gold"], fg_color=P["entry"])
        s.batch_prog.pack(fill="x", padx=8, pady=(0, 4));
        s.batch_prog.set(0)
        s.batch_status = ctk.CTkLabel(batch_sec, text="",
                                      font=ctk.CTkFont(size=9), text_color=P["dim"])
        s.batch_status.pack(padx=8, pady=(0, 6))

        ctk.CTkFrame(lp, height=1, fg_color=P["border"]).pack(fill="x", padx=8, pady=4)

        ctk.CTkLabel(lp, text="Или по одному:",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=P["t2"]).pack(padx=8, anchor="w")

        load_f = ctk.CTkFrame(lp, fg_color="transparent")
        load_f.pack(fill="x", padx=8, pady=(2, 4))
        ctk.CTkButton(load_f, text="Загрузить папку", height=32,
                      fg_color=P["blue"], hover_color="#2563EB",
                      text_color="#fff", font=ctk.CTkFont(size=10),
                      command=s._load_folder).pack(side="left", fill="x", expand=True, padx=(0, 4))
        ctk.CTkButton(load_f, text="Файлы", height=32,
                      fg_color=P["entry"], hover_color=P["bh"],
                      border_width=1, border_color=P["border"],
                      text_color=P["t2"], font=ctk.CTkFont(size=10),
                      command=s._load_files).pack(side="left")

        s.img_frame = ctk.CTkFrame(lp, fg_color=P["entry"], corner_radius=8)
        s.img_frame.pack(fill="both", expand=True, padx=8, pady=4)
        s.img_lbl = ctk.CTkLabel(s.img_frame, text="Загрузите скриншоты",
                                 font=ctk.CTkFont(size=11), text_color=P["dim"])
        s.img_lbl.pack(expand=True)

        s.fname_lbl = ctk.CTkLabel(lp, text="",
                                   font=ctk.CTkFont(family="Consolas", size=9),
                                   text_color=P["t2"])
        s.fname_lbl.pack(fill="x", padx=8, pady=(2, 0))

        prog_f = ctk.CTkFrame(lp, fg_color="transparent")
        prog_f.pack(fill="x", padx=8, pady=(2, 4))
        s.prog_lbl = ctk.CTkLabel(prog_f, text="0/0",
                                  font=ctk.CTkFont(size=10), text_color=P["dim"])
        s.prog_lbl.pack(side="left")
        s.prog_bar = ctk.CTkProgressBar(prog_f, height=5,
                                        progress_color=P["accent"], fg_color=P["entry"])
        s.prog_bar.pack(side="left", fill="x", expand=True, padx=8);
        s.prog_bar.set(0)

        nav_f = ctk.CTkFrame(lp, fg_color="transparent")
        nav_f.pack(fill="x", padx=8, pady=(0, 8))
        s.btn_prev = ctk.CTkButton(nav_f, text="◀", width=60, height=32,
                                   fg_color=P["entry"], hover_color=P["bh"],
                                   border_width=1, border_color=P["border"],
                                   text_color=P["t2"], corner_radius=8,
                                   command=s._prev, state="disabled")
        s.btn_prev.pack(side="left")
        ctk.CTkButton(nav_f, text="Пропустить", width=90, height=32,
                      fg_color=P["entry"], hover_color=P["bh"],
                      border_width=1, border_color=P["border"],
                      text_color=P["warn"], corner_radius=8,
                      command=s._skip).pack(side="left", padx=4)
        s.btn_next = ctk.CTkButton(nav_f, text="▶", width=60, height=32,
                                   fg_color=P["accent"], hover_color=P["ah"],
                                   text_color="#fff", corner_radius=8,
                                   command=s._next, state="disabled")
        s.btn_next.pack(side="right")

        # ══ Правая панель ══
        rp = ctk.CTkFrame(mn, fg_color=P["card"], corner_radius=10)
        rp.grid(row=0, column=1, sticky="nsew")

        ctk.CTkLabel(rp, text="Что на скрине?",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=P["text"]).pack(padx=12, pady=(12, 4), anchor="w")

        ctk.CTkLabel(rp, text="Категория:",
                     font=ctk.CTkFont(size=10), text_color=P["t2"]).pack(padx=12, anchor="w")

        cat_f = ctk.CTkFrame(rp, fg_color="transparent")
        cat_f.pack(fill="x", padx=12, pady=(2, 6))
        s.cat_var = ctk.StringVar(value="")
        for text, val, color in [("💊 Таблетки", "TAB", P["ok"]),
                                 ("💉 Вакцины", "VAC", P["blue"]),
                                 ("🚑 ПМП", "PMP", P["orange"])]:
            ctk.CTkButton(cat_f, text=text, height=36,
                          fg_color=P["entry"], hover_color=color,
                          border_width=2, border_color=P["border"],
                          text_color=P["text"],
                          font=ctk.CTkFont(size=11, weight="bold"),
                          corner_radius=8,
                          command=lambda v=val: s._set_cat(v)).pack(fill="x", pady=1)

        s.cat_display = ctk.CTkLabel(rp, text="Не выбрано",
                                     font=ctk.CTkFont(size=11, weight="bold"),
                                     text_color=P["warn"])
        s.cat_display.pack(padx=12, pady=(0, 6))

        s.pmp_frame = ctk.CTkFrame(rp, fg_color=P["entry"], corner_radius=8,
                                   border_width=1, border_color=P["border"])
        s.pmp_district_var = ctk.StringVar(value="city")
        ctk.CTkLabel(s.pmp_frame, text="Район ПМП:",
                     font=ctk.CTkFont(size=10, weight="bold"),
                     text_color=P["orange"]).pack(padx=8, pady=(6, 2), anchor="w")
        pmp_btns = ctk.CTkFrame(s.pmp_frame, fg_color="transparent")
        pmp_btns.pack(fill="x", padx=8, pady=(0, 6))
        ctk.CTkButton(pmp_btns, text="🏙 Город (ELSH)", height=30,
                      fg_color=P["accent"], hover_color=P["ah"], text_color="#fff",
                      font=ctk.CTkFont(size=10),
                      command=lambda: s._set_pmp_district("city")).pack(fill="x", pady=1)
        ctk.CTkButton(pmp_btns, text="🌄 Пригород (Sandy/Paleto)", height=30,
                      fg_color=P["gold"], hover_color="#FFE033", text_color="#1a1a1a",
                      font=ctk.CTkFont(size=10),
                      command=lambda: s._set_pmp_district("suburb")).pack(fill="x", pady=1)
        s.pmp_district_lbl = ctk.CTkLabel(s.pmp_frame, text="",
                                          font=ctk.CTkFont(size=9), text_color=P["dim"])
        s.pmp_district_lbl.pack(padx=8, pady=(0, 4))

        ctk.CTkLabel(rp, text="Больница:",
                     font=ctk.CTkFont(size=10), text_color=P["t2"]).pack(padx=12, anchor="w")

        loc_f = ctk.CTkFrame(rp, fg_color="transparent")
        loc_f.pack(fill="x", padx=12, pady=(2, 6))
        s.loc_var = ctk.StringVar(value="")
        for text, val, color in [("🏥 ELSH (Город)", "ELSH", P["accent"]),
                                 ("🏜 Sandy Shores", "Sandy", P["gold"]),
                                 ("🌊 Paleto Bay", "Paleto", P["purple"]),
                                 ("❓ Неизвестно", "UNK", P["dim"])]:
            ctk.CTkButton(loc_f, text=text, height=32,
                          fg_color=P["entry"], hover_color=color,
                          border_width=2, border_color=P["border"],
                          text_color=P["text"], font=ctk.CTkFont(size=10),
                          corner_radius=8,
                          command=lambda v=val: s._set_loc(v)).pack(fill="x", pady=1)

        s.loc_display = ctk.CTkLabel(rp, text="Не выбрано",
                                     font=ctk.CTkFont(size=10), text_color=P["warn"])
        s.loc_display.pack(padx=12, pady=(0, 6))

        ctk.CTkFrame(rp, height=1, fg_color=P["border"]).pack(fill="x", padx=8, pady=4)

        s.save_btn = ctk.CTkButton(rp, text="✅ Сохранить", height=40,
                                   fg_color=P["accent"], hover_color=P["ah"],
                                   text_color="#fff",
                                   font=ctk.CTkFont(size=12, weight="bold"),
                                   corner_radius=10, state="disabled",
                                   command=s._save_label)
        s.save_btn.pack(fill="x", padx=12, pady=4)

        ctk.CTkButton(rp, text="⏭ Сохранить + следующий", height=34,
                      fg_color=P["blue"], hover_color="#2563EB",
                      text_color="#fff", font=ctk.CTkFont(size=10),
                      corner_radius=8, command=s._save_and_next).pack(fill="x", padx=12, pady=2)

        ctk.CTkFrame(rp, height=1, fg_color=P["border"]).pack(fill="x", padx=8, pady=4)

        ctk.CTkLabel(rp, text="OCR текст:",
                     font=ctk.CTkFont(size=10), text_color=P["t2"]).pack(padx=12, anchor="w")
        s.ocr_text = Text(rp, font=("Consolas", 8), bg=P["log"], fg=P["t2"],
                          relief="flat", borderwidth=0, padx=4, pady=4, wrap="word", height=5)
        s.ocr_text.pack(fill="x", padx=12, pady=(2, 4))

        s.analysis_lbl = ctk.CTkLabel(rp, text="",
                                      font=ctk.CTkFont(size=10),
                                      text_color=P["dim"], wraplength=280)
        s.analysis_lbl.pack(padx=12, pady=4)

        ctk.CTkFrame(rp, height=1, fg_color=P["border"]).pack(fill="x", padx=8, pady=4)

        # ── Управление базой ──
        db_mgmt = ctk.CTkFrame(rp, fg_color="transparent")
        db_mgmt.pack(fill="x", padx=12, pady=(0, 4))
        ctk.CTkLabel(db_mgmt, text="Управление базой:",
                     font=ctk.CTkFont(size=10, weight="bold"),
                     text_color=P["t2"]).pack(anchor="w", pady=(0, 2))
        ctk.CTkButton(db_mgmt, text="🗑 Удалить все TAB из базы", height=26,
                      fg_color=P["entry"], hover_color=P["bh"],
                      border_width=1, border_color=P["border"],
                      text_color=P["ok"], font=ctk.CTkFont(size=9),
                      command=lambda: s._delete_cat_from_db("TAB")).pack(fill="x", pady=1)
        ctk.CTkButton(db_mgmt, text="🗑 Удалить все VAC из базы", height=26,
                      fg_color=P["entry"], hover_color=P["bh"],
                      border_width=1, border_color=P["border"],
                      text_color=P["blue"], font=ctk.CTkFont(size=9),
                      command=lambda: s._delete_cat_from_db("VAC")).pack(fill="x", pady=1)
        ctk.CTkButton(db_mgmt, text="🗑 Удалить все PMP из базы", height=26,
                      fg_color=P["entry"], hover_color=P["bh"],
                      border_width=1, border_color=P["border"],
                      text_color=P["orange"], font=ctk.CTkFont(size=9),
                      command=lambda: s._delete_cat_from_db("PMP")).pack(fill="x", pady=1)
        ctk.CTkButton(db_mgmt, text="🗑 Удалить выбранный скрин из базы", height=26,
                      fg_color=P["entry"], hover_color=P["rh"],
                      border_width=1, border_color=P["border"],
                      text_color=P["err"], font=ctk.CTkFont(size=9),
                      command=s._delete_current_from_db).pack(fill="x", pady=1)

        s.db_stats_lbl = ctk.CTkLabel(rp, text="",
                                      font=ctk.CTkFont(size=9),
                                      text_color=P["dim"], justify="left")
        s.db_stats_lbl.pack(padx=12, pady=(0, 8), anchor="w")

    def _on_batch_cat_change(s, *args):
        raw = s.batch_cat_var.get()
        if "PMP" in raw:
            s.batch_pmp_frame.pack(fill="x", padx=8, pady=2)
        else:
            s.batch_pmp_frame.pack_forget()

    def _set_cat(s, val):
        s.cat_var.set(val)
        names = {"TAB": "💊 Таблетки", "VAC": "💉 Вакцины", "PMP": "🚑 ПМП"}
        colors = {"TAB": P["ok"], "VAC": P["blue"], "PMP": P["orange"]}
        s.cat_display.configure(text=names.get(val, val),
                                text_color=colors.get(val, P["text"]))
        if val == "PMP":
            s.pmp_frame.pack(fill="x", padx=12, pady=(0, 4), after=s.cat_display)
        else:
            s.pmp_frame.pack_forget()
        s._check_can_save()

    def _set_pmp_district(s, district):
        s.pmp_district_var.set(district)
        if district == "city":
            s._set_loc("ELSH")
            s.pmp_district_lbl.configure(text="→ Город (ELSH)", text_color=P["accent"])
        else:
            s.pmp_district_lbl.configure(text="→ Пригород (выберите Sandy/Paleto)", text_color=P["gold"])

    def _set_loc(s, val):
        s.loc_var.set(val)
        names = {"ELSH": "🏥 ELSH", "Sandy": "🏜 Sandy",
                 "Paleto": "🌊 Paleto", "UNK": "❓ Неизвестно"}
        colors = {"ELSH": P["accent"], "Sandy": P["gold"],
                  "Paleto": P["purple"], "UNK": P["dim"]}
        s.loc_display.configure(text=names.get(val, val),
                                text_color=colors.get(val, P["text"]))
        s._check_can_save()

    def _check_can_save(s):
        s.save_btn.configure(state="normal" if s.cat_var.get() and s.files else "disabled")

    def _on_batch_stop_click(s):
        """Кнопка Стоп для пакетного обучения."""
        s._batch_stop_event.set()
        s.batch_stop_btn.configure(state="disabled")

    def _batch_train(s):
        d = filedialog.askdirectory(title="Папка со скриншотами одной категории")
        if not d: return
        files = sorted([p for p in Path(d).iterdir()
                        if p.is_file() and p.suffix.lower() in EXTS])
        if not files:
            s.log_fn("  Папка пуста", "warning");
            return

        raw_cat = s.batch_cat_var.get()
        cat = raw_cat.split(" - ")[0].strip() if " - " in raw_cat else raw_cat.strip()
        loc = s.batch_loc_var.get()
        if loc == "Неизвестно": loc = "UNK"

        if cat == "PMP":
            pmp_dist = s.batch_pmp_var.get()
            if pmp_dist == "city": loc = "ELSH"

        s.log_fn(f"  Обучение: {len(files)} файлов → {cat} / {loc}", "gold")
        s.is_batch = True
        s._batch_stop_event.clear()
        s.batch_btn.configure(state="disabled")
        s.batch_stop_btn.configure(state="normal")
        s.batch_status.configure(text="Обучение...", text_color=P["warn"])
        threading.Thread(target=s._do_batch_train, args=(files, cat, loc), daemon=True).start()

    def _do_batch_train(s, files, cat, loc):
        total = len(files);
        done = [0];
        ok = [0];
        errors = [0]
        lock = threading.Lock()

        def process_one(fp):
            if s._batch_stop_event.is_set(): return
            try:
                img = _ld(fp)
                if img is None:
                    with lock: errors[0] += 1
                    return
                ctx = ImageContext(img, s.cfg)
                feats = extract_features(ctx)

                ocr_texts = []
                if cat in ("TAB", "VAC", "PMP"):
                    for rx, ry, rw, rh in s.cfg.CHAT_SCAN_ROIS[:1]:
                        roi = ctx.crop(rx, ry, rw, rh)
                        if roi is None: continue
                        gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
                        if float(np.std(gray_roi)) < 10: continue
                        t, conf = _ocr.read(roi, mc=0.1, mh=3, ml=2)
                        if t and len(t) >= 3: ocr_texts.append(t.lower().strip())
                        break

                with lock:
                    add_trigger_sample(s.trigger_db, fp.name, cat, ocr_texts, feats)
                    if loc != "UNK" and feats:
                        add_location_sample(s.location_db, feats, loc, fp.name)
                    for sample in s.trigger_db["labeled"]:
                        if sample["file"] == fp.name:
                            sample["hosp"] = loc;
                            break
                    ok[0] += 1
            except Exception as e:
                with lock:
                    errors[0] += 1
                s.log_fn(f"  Ошибка {fp.name}: {str(e)[:40]}", "error")

            with lock:
                done[0] += 1
                progress = done[0] / total
                d, t, o, er = done[0], total, ok[0], errors[0]
            s.after(0, lambda p=progress, d=d, t=t, o=o, e=er:
            s._update_batch_progress(p, d, t, o, e))

        num_workers = min(4, max(1, len(files) // 2))
        with ThreadPoolExecutor(max_workers=num_workers, thread_name_prefix="batch") as pool:
            futures = [pool.submit(process_one, fp) for fp in files]
            for f in futures:
                if s._batch_stop_event.is_set(): break
                f.result()

        save_trigger_db(s.trigger_db)
        save_location_db(s.location_db)
        s.after(0, lambda: s._batch_done(ok[0], errors[0], total))

    def _update_batch_progress(s, progress, done, total, ok, errors):
        s.batch_prog.set(progress)
        s.batch_status.configure(
            text=f"{done}/{total} — ОК: {ok}, Ошибок: {errors}", text_color=P["info"])

    def _batch_done(s, ok, errors, total):
        s.is_batch = False
        s.batch_btn.configure(state="normal")
        s.batch_stop_btn.configure(state="disabled")
        s.batch_prog.set(1.0)
        s.batch_status.configure(
            text=f"✅ Готово: {ok}/{total} (ошибок: {errors})", text_color=P["ok"])
        s.log_fn(f"  Обучение завершено: {ok}/{total}", "success")
        _play_done_sound()
        s._update_stats()

    def _delete_cat_from_db(s, cat):
        """Удаляет все примеры категории из базы триггеров."""
        before = len(s.trigger_db.get("labeled", []))
        s.trigger_db["labeled"] = [
            item for item in s.trigger_db.get("labeled", [])
            if item.get("cat") != cat
        ]
        if cat in s.trigger_db.get("cat_keywords", {}):
            s.trigger_db["cat_keywords"][cat] = []
        after = len(s.trigger_db["labeled"])
        removed = before - after
        save_trigger_db(s.trigger_db)
        cat_names = {"TAB": "Таблетки", "VAC": "Вакцины", "PMP": "ПМП"}
        s.log_fn(f"  🗑 Удалено {removed} примеров {cat_names.get(cat, cat)} из базы", "warning")
        s._update_stats()

    def _delete_current_from_db(s):
        """Удаляет текущий скрин из базы триггеров."""
        if not s.files: return
        fp = s.files[s.idx]
        before = len(s.trigger_db.get("labeled", []))
        s.trigger_db["labeled"] = [
            item for item in s.trigger_db.get("labeled", [])
            if item.get("file") != fp.name
        ]
        after = len(s.trigger_db["labeled"])
        if before > after:
            save_trigger_db(s.trigger_db)
            s.log_fn(f"  🗑 {fp.name} удалён из базы", "warning")
            s.analysis_lbl.configure(text="Удалён из базы", text_color=P["warn"])
        else:
            s.log_fn(f"  {fp.name} не найден в базе", "dim")
        s._update_stats()

    def _load_folder(s):
        d = filedialog.askdirectory(title="Папка со скриншотами")
        if not d: return
        files = sorted([p for p in Path(d).iterdir()
                        if p.is_file() and p.suffix.lower() in EXTS])
        if not files: s.log_fn("  Папка пуста", "warning"); return
        s.files = files;
        s.idx = 0
        s.log_fn(f"  Загружено {len(files)} файлов", "info")
        s._show_current()

    def _load_files(s):
        fps = filedialog.askopenfilenames(title="Скриншоты",
                                          filetypes=[("Изображения", "*.png *.jpg *.jpeg *.bmp")])
        if not fps: return
        s.files = [Path(f) for f in fps];
        s.idx = 0
        s.log_fn(f"  Загружено {len(s.files)} файлов", "info")
        s._show_current()

    def _show_current(s):
        if not s.files: return
        fp = s.files[s.idx];
        total = len(s.files)
        s.prog_lbl.configure(text=f"{s.idx + 1}/{total}")
        s.prog_bar.set((s.idx + 1) / total)
        s.fname_lbl.configure(text=f"  {fp.name}")
        s.btn_prev.configure(state="normal" if s.idx > 0 else "disabled")
        s.btn_next.configure(state="normal" if s.idx < total - 1 else "disabled")
        s.cat_var.set("");
        s.loc_var.set("")
        s.cat_display.configure(text="Не выбрано", text_color=P["warn"])
        s.loc_display.configure(text="Не выбрано", text_color=P["warn"])
        s.pmp_frame.pack_forget()
        s.save_btn.configure(state="disabled")
        s.ocr_text.delete("1.0", END)
        s.analysis_lbl.configure(text="Анализирую...", text_color=P["warn"])

        labeled = {item["file"]: item for item in s.trigger_db.get("labeled", [])}
        if fp.name in labeled:
            existing = labeled[fp.name]
            if existing.get("cat"): s._set_cat(existing["cat"])
            if existing.get("hosp"): s._set_loc(existing["hosp"])
            s.analysis_lbl.configure(
                text=f"✅ Уже размечен: {existing.get('cat', '')} / {existing.get('hosp', '')}",
                text_color=P["ok"])

        try:
            pil = Image.open(fp)
            r = min(700 / pil.width, 350 / pil.height)
            pil = pil.resize((int(pil.width * r), int(pil.height * r)), Image.LANCZOS)
            s.photo = ImageTk.PhotoImage(pil)
            s.img_lbl.configure(image=s.photo, text="")
        except:
            s.img_lbl.configure(image=None, text="Ошибка")

        threading.Thread(target=s._analyze_current, args=(fp,), daemon=True).start()

    def _analyze_current(s, fp):
        try:
            img = _ld(fp)
            if img is None: return
            ctx = ImageContext(img, s.cfg)
            feats = extract_features(ctx);
            s.current_features = feats
            found, cat_code, txts = find_trigger(ctx, trigger_db=s.trigger_db)
            s.current_ocr = txts
            db_cat, db_conf, db_words = predict_cat_from_db(s.trigger_db, txts)

            def update():
                s.ocr_text.delete("1.0", END)
                if txts:
                    for t in txts: s.ocr_text.insert(END, t + "\n")
                else:
                    s.ocr_text.insert(END, "(OCR пусто)")
                parts = []
                if found:
                    cat_names = {"TAB": "Таблетки", "VAC": "Вакцины", "PMP": "ПМП"}
                    parts.append(f"Авто: {cat_names.get(cat_code, cat_code)}")
                    s._set_cat(cat_code)
                else:
                    parts.append("Авто: не найден")
                if db_cat:
                    parts.append(f"БД: {db_cat} ({db_conf:.0%})")
                    if not found: s._set_cat(db_cat)
                s.analysis_lbl.configure(text="\n".join(parts),
                                         text_color=P["ok"] if found else P["warn"])

            s.after(0, update)
        except Exception as e:
            s.after(0, lambda: s.analysis_lbl.configure(
                text=f"Ошибка: {str(e)[:50]}", text_color=P["err"]))

    def _save_label(s):
        if not s.files: return
        cat = s.cat_var.get();
        loc = s.loc_var.get() or "UNK"
        if not cat: s.log_fn("  Выберите категорию!", "warning"); return
        fp = s.files[s.idx]
        add_trigger_sample(s.trigger_db, fp.name, cat, s.current_ocr, s.current_features)
        if loc and loc != "UNK" and s.current_features:
            add_location_sample(s.location_db, s.current_features, loc, fp.name)
        for sample in s.trigger_db["labeled"]:
            if sample["file"] == fp.name: sample["hosp"] = loc; break
        save_trigger_db(s.trigger_db)
        s.log_fn(f"  ✅ {fp.name} → {cat} / {loc}", "success")
        s._update_stats()
        s.analysis_lbl.configure(text=f"✅ Сохранено: {cat} / {loc}", text_color=P["ok"])

    def _save_and_next(s):
        s._save_label()
        if s.idx < len(s.files) - 1: s.idx += 1; s._show_current()

    def _prev(s):
        if s.idx > 0: s.idx -= 1; s._show_current()

    def _next(s):
        if s.idx < len(s.files) - 1: s.idx += 1; s._show_current()

    def _skip(s):
        if s.idx < len(s.files) - 1: s.idx += 1; s._show_current()

    def _update_stats(s):
        labeled = s.trigger_db.get("labeled", [])
        total = len(labeled);
        by_cat = {};
        by_loc = {}
        for item in labeled:
            cat = item.get("cat", "?");
            loc = item.get("hosp", "?")
            by_cat[cat] = by_cat.get(cat, 0) + 1
            by_loc[loc] = by_loc.get(loc, 0) + 1
        kws = s.trigger_db.get("cat_keywords", {})
        kw_counts = {k: len(v) for k, v in kws.items()}
        lines = [f"Размечено: {total}"]
        cat_names = {"TAB": "Табл", "VAC": "Вакц", "PMP": "ПМП"}
        for cat, cnt in sorted(by_cat.items()):
            kw_cnt = kw_counts.get(cat, 0)
            lines.append(f"  {cat_names.get(cat, cat)}: {cnt} ({kw_cnt} сл.)")
        lines.append("")
        for loc, cnt in sorted(by_loc.items()):
            lines.append(f"  {loc}: {cnt}")
        loc_total = len(s.location_db.get("samples", []))
        lines.append(f"\nЛокации: {loc_total}")
        s.stats_lbl.configure(text=f"Размечено: {total} | Локации: {loc_total}")
        s.db_stats_lbl.configure(text="\n".join(lines))


def main():
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("dark-blue")
    App().mainloop()


if __name__ == "__main__":
    main()


