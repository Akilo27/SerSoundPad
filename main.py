#!/usr/bin/env python3
"""
SerSoundPad - SoundPad для Linux
Исправленное определение микрофона и устройства вывода
"""

import json
import os
import sys
import threading
import time
import subprocess
from pathlib import Path

import pygame
import numpy as np
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *

try:
    from pynput import keyboard as pynput_keyboard
    PYNPUT_AVAILABLE = True
except ImportError:
    PYNPUT_AVAILABLE = False

# ========== КОНФИГ ==========
CONFIG_FILE = "config.json"
SOUNDS_DIR = "sounds"
os.makedirs(SOUNDS_DIR, exist_ok=True)

hotkey_map = {}
running = True
loopback_module_id = None

# ========== УПРАВЛЕНИЕ ВОСПРОИЗВЕДЕНИЕМ ==========
class SoundManager:
    def __init__(self):
        self.channels = {}
        self.sounds = {}
        self.playing = {}
        self.lock = threading.Lock()

    def play_or_stop(self, key_name, file_path):
        with self.lock:
            if key_name in self.playing and self.playing[key_name]:
                if key_name in self.channels and self.channels[key_name]:
                    self.channels[key_name].stop()
                self.playing[key_name] = False
                print(f"⏹ [{key_name}]")
                return False

            try:
                if key_name not in self.sounds or self.sounds[key_name] is None:
                    self.sounds[key_name] = pygame.mixer.Sound(file_path)

                for i in range(pygame.mixer.get_num_channels()):
                    ch = pygame.mixer.Channel(i)
                    if not ch.get_busy():
                        channel = ch
                        break
                else:
                    channel = pygame.mixer.Channel(0)

                channel.play(self.sounds[key_name])
                self.channels[key_name] = channel
                self.playing[key_name] = True
                print(f"▶ [{key_name}]")

                def reset_playing():
                    time.sleep(self.sounds[key_name].get_length() + 0.1)
                    with self.lock:
                        if key_name in self.playing and self.playing[key_name]:
                            if not (key_name in self.channels and self.channels[key_name].get_busy()):
                                self.playing[key_name] = False

                threading.Thread(target=reset_playing, daemon=True).start()
                return True
            except Exception as e:
                print(f"❌ Ошибка: {e}")
                return False

    def stop_all(self):
        with self.lock:
            for i in range(pygame.mixer.get_num_channels()):
                pygame.mixer.Channel(i).stop()
            for key in self.playing:
                self.playing[key] = False
            print("⏹ Все остановлены")

sound_manager = SoundManager()

# ========== ОПРЕДЕЛЕНИЕ УСТРОЙСТВ ==========
def get_running_sink():
    """Находит активное устройство вывода (наушники/колонки) по состоянию RUNNING"""
    try:
        result = subprocess.run(['pactl', 'list', 'sinks'], capture_output=True, text=True)
        lines = result.stdout.split('\n')
        name = None
        for i, line in enumerate(lines):
            if 'State:' in line and 'RUNNING' in line:
                for j in range(i-1, -1, -1):
                    if 'Name:' in lines[j]:
                        name = lines[j].split('Name:')[1].strip()
                        return name
    except Exception as e:
        print(f"Ошибка получения sink: {e}")
    return None

def get_running_source():
    """Находит активное устройство ввода (микрофон) по состоянию RUNNING"""
    try:
        result = subprocess.run(['pactl', 'list', 'sources'], capture_output=True, text=True)
        lines = result.stdout.split('\n')
        name = None
        for i, line in enumerate(lines):
            if 'State:' in line and 'RUNNING' in line:
                for j in range(i-1, -1, -1):
                    if 'Name:' in lines[j]:
                        name = lines[j].split('Name:')[1].strip()
                        return name
    except Exception as e:
        print(f"Ошибка получения source: {e}")
    return None

def send_sound_to_mic(enabled):
    """Включить/выключить отправку звука в микрофон"""
    global loopback_module_id

    if not enabled:
        if loopback_module_id:
            try:
                subprocess.run(['pactl', 'unload-module', loopback_module_id], capture_output=True)
                loopback_module_id = None
                print("❌ Отправка в микрофон отключена")
            except:
                pass
        return True

    sink = get_running_sink()
    mic = get_running_source()

    if not sink:
        print("❌ Не найдено активное устройство вывода (наушники/колонки).")
        return False
    if not mic:
        print("❌ Не найден активный микрофон. Проверь, что микрофон используется.")
        return False

    monitor = f"{sink}.monitor"
    print(f"🔊 Устройство вывода: {sink}")
    print(f"🎤 Микрофон: {mic}")

    try:
        result = subprocess.run(
            ['pactl', 'load-module', 'module-loopback',
             f'source={monitor}',
             f'sink={mic}',
             'latency_msec=1'],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            loopback_module_id = result.stdout.strip()
            print(f"✅ Отправка в микрофон включена (ID {loopback_module_id})")
            return True
        else:
            print(f"❌ Ошибка: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False

# ========== ЗВУК (исправлено: частота 44100, тест без шума) ==========
def init_sound():
    try:
        pygame.mixer.pre_init(frequency=44100, size=-16, channels=2, buffer=512)
        pygame.init()
        pygame.mixer.init()
        pygame.mixer.set_num_channels(32)
        print("✅ Звук готов (44100 Гц, стерео)")
        return True
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False

def test_sound():
    try:
        duration = 0.3
        freq = 440
        sr = 44100
        t = np.linspace(0, duration, int(sr * duration))
        wave = (np.sin(2 * np.pi * freq * t) * 32767).astype(np.int16)
        wave = np.ascontiguousarray(wave)
        stereo = np.array([wave, wave]).T
        sound = pygame.sndarray.make_sound(stereo)
        sound.play()
        print("🔊 Тест (чистый звук)")
    except Exception as e:
        print(f"❌ Ошибка теста: {e}")

def play_or_stop_sound(key_name, file_path):
    sound_manager.play_or_stop(key_name, file_path)

# ========== ПЕРЕХВАТ КЛАВИШ ==========
def listen_pynput():
    global running
    def on_press(key):
        if not running:
            return False
        try:
            if hasattr(key, 'char') and key.char:
                key_name = key.char.lower()
            elif hasattr(key, 'name'):
                key_name = key.name.lower()
            else:
                return
            if key_name in ['shift', 'ctrl', 'alt', 'cmd', 'win',
                           'shift_r', 'ctrl_r', 'alt_r', 'alt_gr']:
                return
            if key_name in hotkey_map:
                play_or_stop_sound(key_name, hotkey_map[key_name])
        except:
            pass
    print("✅ Глобальный перехват активен")
    with pynput_keyboard.Listener(on_press=on_press) as listener:
        listener.join()

def start_keyboard_listener():
    if PYNPUT_AVAILABLE:
        threading.Thread(target=listen_pynput, daemon=True).start()
        return True
    return False

# ========== GUI (остаётся без изменений) ==========
class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Аудионастройки")
        self.setFixedSize(550, 450)
        self.setStyleSheet("""
            QDialog { background-color: #2d2d2d; }
            QLabel { color: white; font-size: 13px; }
            QCheckBox { color: #FF9800; font-size: 13px; spacing: 8px; }
            QPushButton { background-color: #4CAF50; color: white; border: none; padding: 8px 16px; border-radius: 6px; font-weight: bold; }
            QPushButton:hover { background-color: #45a049; }
            QGroupBox { color: white; border: 1px solid #555; margin-top: 10px; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }
        """)

        layout = QVBoxLayout()
        self.send_checkbox = QCheckBox("🔊 Отправлять звуки в реальный микрофон (слышат другие)")
        self.send_checkbox.stateChanged.connect(self.on_send_toggle)
        layout.addWidget(self.send_checkbox)

        info_group = QGroupBox("Информация")
        info_layout = QVBoxLayout()
        self.mic_label = QLabel("Микрофон: определение...")
        self.sink_label = QLabel("Устройство вывода: определение...")
        self.status_label = QLabel("Статус: ❌ не активен")
        info_layout.addWidget(self.mic_label)
        info_layout.addWidget(self.sink_label)
        info_layout.addWidget(self.status_label)
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)

        layout.addSpacing(20)
        layout.addWidget(QLabel("💡 Как это работает:"))
        info = QLabel(
            "✓ Включи отправку → твои звуки будут слышны другим в Discord/VK/Telegram\n"
            "✓ Ты НЕ слышишь себя (нет эха)\n"
            "✓ Твой голос в микрофон передаётся как обычно\n\n"
            "ВАЖНО: Не включай 'Прослушивание' микрофона в настройках системы!\n"
            "Если слышишь себя - отключи его."
        )
        info.setStyleSheet("color: #aaa; font-size: 11px;")
        info.setWordWrap(True)
        layout.addWidget(info)

        layout.addSpacing(20)
        test_btn = QPushButton("🔊 Тест звука")
        test_btn.clicked.connect(self.test_sound)
        layout.addWidget(test_btn)

        refresh_btn = QPushButton("🔄 Обновить информацию")
        refresh_btn.clicked.connect(self.refresh_info)
        refresh_btn.setStyleSheet("background-color: #2196F3;")
        layout.addWidget(refresh_btn)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        buttons.setStyleSheet("QPushButton { background-color: #3c3c3c; }")
        layout.addWidget(buttons)

        self.setLayout(layout)
        self.refresh_info()
        self.update_loopback_status()

    def refresh_info(self):
        sink = get_running_sink()
        mic = get_running_source()
        self.sink_label.setText(f"🔊 Устройство вывода: {sink if sink else 'не найдено'}")
        self.mic_label.setText(f"🎤 Микрофон: {mic if mic else 'не найден'}")
        self.update_loopback_status()

    def update_loopback_status(self):
        try:
            result = subprocess.run(['pactl', 'list', 'short', 'modules'], capture_output=True, text=True)
            if loopback_module_id and loopback_module_id in result.stdout:
                self.status_label.setText("Статус: ✅ активен (звук идёт в микрофон)")
                self.status_label.setStyleSheet("color: #4CAF50;")
                self.send_checkbox.setChecked(True)
            else:
                self.status_label.setText("Статус: ❌ не активен")
                self.status_label.setStyleSheet("color: #f44336;")
                self.send_checkbox.setChecked(False)
        except:
            pass

    def on_send_toggle(self, state):
        if state == Qt.CheckState.Checked.value:
            if send_sound_to_mic(True):
                self.status_label.setText("Статус: ✅ активен")
                self.status_label.setStyleSheet("color: #4CAF50;")
            else:
                self.send_checkbox.setChecked(False)
        else:
            send_sound_to_mic(False)
            self.status_label.setText("Статус: ❌ не активен")
            self.status_label.setStyleSheet("color: #f44336;")

    def test_sound(self):
        test_sound()

    def accept(self):
        super().accept()


class HotkeyDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.hotkey = None
        self.setWindowTitle("Назначить клавишу")
        self.setFixedSize(450, 200)
        self.setStyleSheet("background-color: #2d2d2d; QLabel { color: white; }")
        layout = QVBoxLayout()
        self.label = QLabel("Нажми ЛЮБУЮ клавишу...")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setStyleSheet("font-size: 20px; font-weight: bold; padding: 20px; color: #FF9800;")
        layout.addWidget(self.label)
        self.info = QLabel("Повторное нажатие останавливает звук")
        self.info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.info.setStyleSheet("color: #4CAF50; font-size: 12px;")
        layout.addWidget(self.info)
        self.setLayout(layout)
        self.grabKeyboard()

    def keyPressEvent(self, event):
        key = event.key()
        key_text = event.text()
        if key_text and key_text.isprintable():
            self.hotkey = key_text.lower()
        else:
            key_map = {
                Qt.Key.Key_Space: 'space', Qt.Key.Key_Return: 'enter', Qt.Key.Key_Escape: 'esc',
                Qt.Key.Key_Tab: 'tab', Qt.Key.Key_Backspace: 'backspace', Qt.Key.Key_Delete: 'delete',
                Qt.Key.Key_Insert: 'insert', Qt.Key.Key_Home: 'home', Qt.Key.Key_End: 'end',
                Qt.Key.Key_PageUp: 'page_up', Qt.Key.Key_PageDown: 'page_down',
                Qt.Key.Key_Up: 'up', Qt.Key.Key_Down: 'down', Qt.Key.Key_Left: 'left', Qt.Key.Key_Right: 'right',
                Qt.Key.Key_F1: 'f1', Qt.Key.Key_F2: 'f2', Qt.Key.Key_F3: 'f3', Qt.Key.Key_F4: 'f4',
                Qt.Key.Key_F5: 'f5', Qt.Key.Key_F6: 'f6', Qt.Key.Key_F7: 'f7', Qt.Key.Key_F8: 'f8',
                Qt.Key.Key_F9: 'f9', Qt.Key.Key_F10: 'f10', Qt.Key.Key_F11: 'f11', Qt.Key.Key_F12: 'f12',
            }
            self.hotkey = key_map.get(key, None)
        if self.hotkey:
            self.label.setText(f"✓ Назначено: {self.hotkey.upper()}")
            self.label.setStyleSheet("color: #4CAF50; font-size: 20px; font-weight: bold;")
            QTimer.singleShot(400, self.accept)


class SoundCard(QFrame):
    def __init__(self, hotkey, file_path, parent):
        super().__init__(parent)
        self.hotkey = hotkey
        self.file_path = file_path
        self.parent = parent
        self.init_ui()

    def init_ui(self):
        self.setFixedHeight(65)
        self.setStyleSheet("""
            SoundCard { background-color: #3c3c3c; border-radius: 10px; margin: 4px; }
            SoundCard:hover { background-color: #454545; border: 1px solid #FF9800; }
        """)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 0, 10, 0)
        icon = QLabel("🔊")
        icon.setStyleSheet("font-size: 28px;")
        layout.addWidget(icon)
        name = os.path.basename(self.file_path)
        info = QLabel(f"<b style='color:#FF9800; font-size:14px'>[{self.hotkey.upper()}]</b>  <span style='color:#ffffff'>{name}</span>")
        layout.addWidget(info, stretch=1)
        self.status_icon = QLabel("⏹")
        self.status_icon.setStyleSheet("font-size: 16px; color: #888;")
        layout.addWidget(self.status_icon)
        play_btn = QPushButton("▶")
        play_btn.setFixedSize(36, 36)
        play_btn.setStyleSheet("background-color: #4CAF50; border-radius: 18px; color: white; font-weight: bold;")
        play_btn.clicked.connect(lambda: play_or_stop_sound(self.hotkey, self.file_path))
        layout.addWidget(play_btn)
        change_btn = QPushButton("⌨")
        change_btn.setFixedSize(36, 36)
        change_btn.setStyleSheet("background-color: #FF9800; border-radius: 18px; color: white; font-weight: bold;")
        change_btn.clicked.connect(self.change_hotkey)
        layout.addWidget(change_btn)
        delete_btn = QPushButton("✖")
        delete_btn.setFixedSize(36, 36)
        delete_btn.setStyleSheet("background-color: #f44336; border-radius: 18px; color: white; font-weight: bold;")
        delete_btn.clicked.connect(self.delete_sound)
        layout.addWidget(delete_btn)
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.update_status)
        self.update_timer.start(100)

    def update_status(self):
        if self.hotkey in sound_manager.playing and sound_manager.playing[self.hotkey]:
            self.status_icon.setText("▶")
            self.status_icon.setStyleSheet("font-size: 16px; color: #4CAF50;")
        else:
            self.status_icon.setText("⏹")
            self.status_icon.setStyleSheet("font-size: 16px; color: #888;")

    def change_hotkey(self):
        dialog = HotkeyDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.hotkey:
            if dialog.hotkey in hotkey_map and dialog.hotkey != self.hotkey:
                QMessageBox.warning(self, "Ошибка", f"Клавиша {dialog.hotkey} уже занята!")
                return
            del hotkey_map[self.hotkey]
            self.hotkey = dialog.hotkey
            hotkey_map[self.hotkey] = self.file_path
            save_config()
            self.parent.refresh_sounds()

    def delete_sound(self):
        reply = QMessageBox.question(self, 'Удаление', f'Удалить звук для клавиши {self.hotkey.upper()}?',
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            del hotkey_map[self.hotkey]
            save_config()
            self.parent.refresh_sounds()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SerSoundPad")
        self.setGeometry(100, 100, 900, 600)
        self.setStyleSheet("background-color: #2d2d2d;")
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(10, 10, 10, 10)
        top = QFrame()
        top.setStyleSheet("background-color: #3c3c3c; border-radius: 10px;")
        top_layout = QHBoxLayout(top)
        for text, color, handler in [
            ("➕ Добавить звук", "#4CAF50", self.add_sound),
            ("⚙ Настройки", "#2196F3", self.open_settings),
            ("⏹ Остановить всё", "#f44336", self.stop_all),
        ]:
            btn = QPushButton(text)
            btn.setStyleSheet(f"background-color: {color}; color: white; border: none; border-radius: 8px; padding: 8px 16px; font-weight: bold;")
            btn.clicked.connect(handler)
            top_layout.addWidget(btn)
        self.status_label = QLabel("🟢 Готов")
        self.status_label.setStyleSheet("color: #4CAF50; padding: 5px; font-weight: bold;")
        top_layout.addWidget(self.status_label)
        top_layout.addStretch()
        layout.addWidget(top)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("border: none; background-color: #2d2d2d;")
        self.sounds_container = QWidget()
        self.sounds_layout = QVBoxLayout(self.sounds_container)
        self.sounds_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.sounds_layout.setSpacing(5)
        self.scroll.setWidget(self.sounds_container)
        layout.addWidget(self.scroll)
        self.statusBar().setStyleSheet("QStatusBar { background-color: #3c3c3c; color: #aaa; }")
        load_config()
        self.refresh_sounds()
        init_sound()
        start_keyboard_listener()
        self.statusBar().showMessage("✅ Готов! Включи отправку в микрофон в настройках", 5000)

    def add_sound(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Выбери звук", SOUNDS_DIR, "Аудио (*.mp3 *.wav *.ogg);;Все файлы (*.*)")
        if not file_path:
            return
        dest = os.path.join(SOUNDS_DIR, os.path.basename(file_path))
        if not os.path.exists(dest):
            import shutil
            shutil.copy(file_path, dest)
        dialog = HotkeyDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.hotkey:
            if dialog.hotkey in hotkey_map:
                QMessageBox.warning(self, "Ошибка", f"Клавиша {dialog.hotkey} уже занята!")
                return
            hotkey_map[dialog.hotkey] = dest
            save_config()
            self.refresh_sounds()
            self.statusBar().showMessage(f"✅ Добавлен: [{dialog.hotkey}]", 2000)

    def open_settings(self):
        dialog = SettingsDialog(self)
        dialog.exec()

    def stop_all(self):
        sound_manager.stop_all()
        self.statusBar().showMessage("⏹ Все остановлены", 2000)

    def refresh_sounds(self):
        while self.sounds_layout.count():
            child = self.sounds_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        if not hotkey_map:
            empty = QLabel("🎵 Нет звуков\nНажмите 'Добавить звук'")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet("color: #888; font-size: 16px; padding: 50px;")
            self.sounds_layout.addWidget(empty)
        else:
            for key, path in sorted(hotkey_map.items()):
                if os.path.exists(path):
                    self.sounds_layout.addWidget(SoundCard(key, path, self))

    def closeEvent(self, event):
        global running
        running = False
        sound_manager.stop_all()
        send_sound_to_mic(False)
        save_config()
        event.accept()


def load_config():
    global hotkey_map
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                hotkey_map = json.load(f)
        except:
            hotkey_map = {}
    hotkey_map = {k: v for k, v in hotkey_map.items() if os.path.exists(v)}

def save_config():
    with open(CONFIG_FILE, 'w') as f:
        json.dump(hotkey_map, f, indent=2)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    window = MainWindow()
    window.show()
    sys.exit(app.exec())