# 1. Скачай проект
cd ~
git clone https://github.com/yourusername/SerSoundPad.git
# или просто создай папку вручную

# 2. Перейди в папку
cd SerSoundPad

# 3. Создай виртуальное окружение
python3 -m venv .venv
source .venv/bin/activate

# 4. Установи зависимости
pip install pygame evdev

# 5. Установи системные зависимости (один раз)
sudo apt install pulseaudio libsdl2-mixer-2.0-0

# 6. Добавь себя в группу input (для доступа к клавиатуре)
sudo usermod -a -G input $USER

# 7. Перезагрузись или выйди и зайди заново!

# 8. Запусти
python main.py