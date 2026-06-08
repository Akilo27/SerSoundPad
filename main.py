#!/usr/bin/env python3
"""
SerSoundPad — простой SoundPad для Linux
Выбери свои устройства в настройках — и всё заработает.
"""

import json
import os
import sys
import threading
import subprocess
import pygame
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from pynput import keyboard

# ---------- Конфиг ----------
CONFIG_FILE = "config.json"
SOUNDS_DIR = "sounds"
os.makedirs(SOUNDS_DIR, exist_ok=True)

hotkeys = {}          # {имя_клавиши: путь_к_звуку}
loopback_id = None
running = True

# ---------- Звук ----------
pygame.mixer.init(frequency=48000, size=-16, channels=2, buffer=1024)
pygame.mixer.set_num_channels(32)

def play_sound(path):
    def _play():
        try:
            s = pygame.mixer.Sound(path)
            s.play()
            print(f"🔊 {os.path.basename(path)}")
        except Exception as e:
            print(f"Ошибка: {e}")
    threading.Thread(target=_play, daemon=True).start()

def stop_sound():
    pygame.mixer.stop()
    print("⏹ Стоп")

# ---------- Глобальные хоткеи ----------
def on_press(key):
    if not running:
        return False
    try:
        if hasattr(key, 'char') and key.char:
            k = key.char.lower()
        elif hasattr(key, 'name'):
            k = key.name.lower()
        else:
            return
        if k in ('shift', 'ctrl', 'alt', 'cmd'):
            return
        if k in hotkeys:
            play_sound(hotkeys[k])
    except:
        pass

def start_listener():
    listener = keyboard.Listener(on_press=on_press)
    listener.daemon = True
    listener.start()

# ---------- Loopback (отправка звука в микрофон) ----------
def get_sinks():
    """Список устройств вывода (колонки, наушники)"""
    sinks = []
    try:
        out = subprocess.check_output(['pactl', 'list', 'short', 'sinks'], text=True)
        for line in out.strip().split('\n'):
            if line:
                parts = line.split('\t')
                sinks.append(parts[1])
    except:
        pass
    return sinks

def get_sources():
    """Список устройств ввода (микрофоны)"""
    sources = []
    try:
        out = subprocess.check_output(['pactl', 'list', 'short', 'sources'], text=True)
        for line in out.strip().split('\n'):
            if line and 'monitor' not in line:
                parts = line.split('\t')
                sources.append(parts[1])
    except:
        pass
    return sources

def set_loopback(enable, sink_name=None, source_name=None):
    global loopback_id
    if not enable and loopback_id:
        subprocess.run(['pactl', 'unload-module', loopback_id])
        loopback_id = None
        return True
    if enable and sink_name and source_name:
        if loopback_id:
            set_loopback(False)
        res = subprocess.run(
            ['pactl', 'load-module', 'module-loopback',
             f'source={sink_name}.monitor', f'sink={source_name}', 'latency_msec=1'],
            capture_output=True, text=True
        )
        if res.returncode == 0:
            loopback_id = res.stdout.strip()
            return True
    return False

# ---------- GUI ----------
class SettingsWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Настройки звука")
        self.setFixedSize(500, 300)
        self.setStyleSheet("background:#2d2d2d; color:white;")

        layout = QVBoxLayout()

        layout.addWidget(QLabel("🎧 Устройство вывода (твои наушники/колонки):"))
        self.sink_combo = QComboBox()
        self.sink_combo.addItems(get_sinks())
        layout.addWidget(self.sink_combo)

        layout.addWidget(QLabel("🎤 Микрофон (куда отправлять звук):"))
        self.source_combo = QComboBox()
        self.source_combo.addItems(get_sources())
        layout.addWidget(self.source_combo)

        self.cb = QCheckBox("🔊 Отправлять звуки в микрофон (слышат другие)")
        self.cb.stateChanged.connect(self.on_toggle)
        layout.addWidget(self.cb)

        self.status = QLabel("Статус: ❌ не активен")
        layout.addWidget(self.status)

        btn_test = QPushButton("🔊 Тест")
        btn_test.clicked.connect(self.test)
        layout.addWidget(btn_test)

        btn_refresh = QPushButton("🔄 Обновить список")
        btn_refresh.clicked.connect(self.refresh)
        layout.addWidget(btn_refresh)

        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        box.accepted.connect(self.accept)
        box.rejected.connect(self.reject)
        layout.addWidget(box)

        self.setLayout(layout)
        self.update_status()

    def refresh(self):
        self.sink_combo.clear()
        self.source_combo.clear()
        self.sink_combo.addItems(get_sinks())
        self.source_combo.addItems(get_sources())
        self.update_status()

    def update_status(self):
        if loopback_id:
            self.status.setText("Статус: ✅ активен")
            self.status.setStyleSheet("color:#4CAF50;")
            self.cb.setChecked(True)
        else:
            self.status.setText("Статус: ❌ не активен")
            self.status.setStyleSheet("color:#f44336;")
            self.cb.setChecked(False)

    def on_toggle(self, state):
        if state:
            sink = self.sink_combo.currentText()
            src = self.source_combo.currentText()
            if sink and src:
                ok = set_loopback(True, sink, src)
                if not ok:
                    self.cb.setChecked(False)
                    QMessageBox.warning(self, "Ошибка", "Не удалось создать loopback")
            else:
                self.cb.setChecked(False)
                QMessageBox.warning(self, "Ошибка", "Выберите устройства")
        else:
            set_loopback(False)
        self.update_status()

    def test(self):
        try:
            duration = 0.3
            freq = 440
            sr = 48000
            import numpy as np
            t = np.linspace(0, duration, int(sr * duration))
            wave = (np.sin(2 * np.pi * freq * t) * 32767).astype(np.int16)
            wave = np.ascontiguousarray(wave)
            stereo = np.array([wave, wave]).T
            snd = pygame.sndarray.make_sound(stereo)
            snd.play()
        except Exception as e:
            QMessageBox.warning(self, "Ошибка", f"Тест не удался: {e}")

    def accept(self):
        if self.cb.isChecked():
            sink = self.sink_combo.currentText()
            src = self.source_combo.currentText()
            if sink and src:
                set_loopback(True, sink, src)
            else:
                set_loopback(False)
        else:
            set_loopback(False)
        super().accept()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SerSoundPad")
        self.setGeometry(100, 100, 800, 500)
        self.setStyleSheet("background:#2d2d2d;")

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # Кнопки
        bar = QHBoxLayout()
        add_btn = QPushButton("➕ Добавить звук")
        add_btn.clicked.connect(self.add_sound)
        set_btn = QPushButton("⚙ Настройки")
        set_btn.clicked.connect(self.open_settings)
        stop_btn = QPushButton("⏹ Остановить всё")
        stop_btn.clicked.connect(lambda: pygame.mixer.stop())
        bar.addWidget(add_btn)
        bar.addWidget(set_btn)
        bar.addWidget(stop_btn)
        bar.addStretch()
        layout.addLayout(bar)

        # Список звуков
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("border:none;")
        self.container = QWidget()
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll.setWidget(self.container)
        layout.addWidget(self.scroll)

        self.statusBar().showMessage("Готов. Добавь звуки и включи отправку в микрофон в настройках.")
        self.refresh_list()

    def add_sound(self):
        path, _ = QFileDialog.getOpenFileName(self, "Выбери звук", SOUNDS_DIR,
                                             "Аудио (*.mp3 *.wav *.ogg)")
        if not path:
            return
        dest = os.path.join(SOUNDS_DIR, os.path.basename(path))
        if not os.path.exists(dest):
            import shutil
            shutil.copy(path, dest)

        # Назначить клавишу
        dlg = QInputDialog(self)
        dlg.setWindowTitle("Назначить клавишу")
        dlg.setLabelText("Нажми клавишу (букву, цифру, F1, Home...)\nПовторное нажатие остановит звук.")
        dlg.setTextValue("")
        dlg.setStyleSheet("background:#2d2d2d; color:white;")
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        key = dlg.textValue().strip().lower()
        if not key:
            return
        if key in hotkeys:
            QMessageBox.warning(self, "Ошибка", f"Клавиша '{key}' уже используется")
            return
        hotkeys[key] = dest
        self.save_config()
        self.refresh_list()

    def open_settings(self):
        dlg = SettingsWindow(self)
        dlg.exec()

    def refresh_list(self):
        # очистить
        while self.container_layout.count():
            child = self.container_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        if not hotkeys:
            lbl = QLabel("🎵 Нет звуков. Нажми 'Добавить звук'")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet("color:#888; padding:50px;")
            self.container_layout.addWidget(lbl)
        else:
            for k, path in sorted(hotkeys.items()):
                card = QFrame()
                card.setFixedHeight(60)
                card.setStyleSheet("background:#3c3c3c; border-radius:8px; margin:4px;")
                layout = QHBoxLayout(card)
                layout.setContentsMargins(15,0,10,0)
                name = os.path.basename(path)
                lbl = QLabel(f"<b style='color:#FF9800'>[{k.upper()}]</b>  {name}")
                lbl.setStyleSheet("color:white;")
                layout.addWidget(lbl, stretch=1)

                play_btn = QPushButton("▶")
                play_btn.setFixedSize(35,35)
                play_btn.setStyleSheet("background:#4CAF50; border-radius:17px;")
                play_btn.clicked.connect(lambda p=path: play_sound(p))
                layout.addWidget(play_btn)

                del_btn = QPushButton("✖")
                del_btn.setFixedSize(35,35)
                del_btn.setStyleSheet("background:#f44336; border-radius:17px;")
                del_btn.clicked.connect(lambda key=k: self.remove_sound(key))
                layout.addWidget(del_btn)

                self.container_layout.addWidget(card)

    def remove_sound(self, key):
        if key in hotkeys:
            del hotkeys[key]
            self.save_config()
            self.refresh_list()

    def save_config(self):
        with open(CONFIG_FILE, 'w') as f:
            json.dump(hotkeys, f, indent=2)

    def load_config(self):
        global hotkeys
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE) as f:
                    hotkeys = json.load(f)
            except:
                hotkeys = {}
        hotkeys = {k:v for k,v in hotkeys.items() if os.path.exists(v)}

    def closeEvent(self, event):
        global running
        running = False
        set_loopback(False)
        self.save_config()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    win = MainWindow()
    win.load_config()
    win.refresh_list()
    start_listener()
    win.show()
    sys.exit(app.exec())