import os
import subprocess
import sys
import time
from datetime import datetime

# --- КОНФИГУРАЦИЯ WATCHDOG ---
TARGET_SCRIPT = "matrix_logger_v9.py"  # Имя вашей новой версии основного скрипта
HISTORY_LOG_FILE = "C:/config/Matrix_projects_2026/sent_messages_history.txt"

# Новый вечный лог только для фиксации запусков и остановок
WATCHDOG_LOG_FILE = "C:/config/Matrix_projects_2026/watchdog_history.txt"

CHECK_INTERVAL_SEC = 30       # Как часто проверять основной скрипт (раз в 30 секунд)
MAX_SILENCE_MINUTES = 15      # Если файл не менялся более 15 минут — перезапуск

process = None

def log_to_watchdog_history(event_type, details):
    """Функция для ведения постоянной истории запусков/остановок"""
    ts = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    log_message = f"[{ts}] [{event_type}] {details}\n"
    try:
        # Пишем в режиме "a" (дозапись), этот файл никогда не затрется основным скриптом
        with open(WATCHDOG_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(log_message)
        print(f"Событие [{event_type}] успешно записано в {WATCHDOG_LOG_FILE}")
    except Exception as e:
        print(f"Не удалось записать событие в лог вочдога: {e}")

def start_matrix_logger(reason=None):
    """Запуск или перезапуск основного скрипта"""
    global process
    
    if process:
        print(f"[{datetime.now():%d.%m.%Y %H:%M:%S}] Завершаем старый процесс...")
        log_to_watchdog_history("ОСТАНОВКА", f"Причина: {reason if reason else 'Принудительный перезапуск'}")
        
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()  # Жесткое уничтожение, если процесс завис намертво
    else:
        # Самый первый запуск при включении самого вочдога
        log_to_watchdog_history("СТАРТ", "Первичный запуск системы мониторинга.")

    print(f"[{datetime.now():%d.%m.%Y %H:%M:%S}] Запуск скрипта: {TARGET_SCRIPT}")
    
    # Записываем в лог факт успешного старта процесса
    if reason: 
        log_to_watchdog_history("ЗАПУСК", f"Скрипт {TARGET_SCRIPT} запущен заново после сбоя.")
        
    process = subprocess.Popen([sys.executable, TARGET_SCRIPT])

# Первый запуск при старте вочдога
start_matrix_logger()

while True:
    time.sleep(CHECK_INTERVAL_SEC)

    # 1. Проверка: не упал ли скрипт полностью на уровне ОС (ошибка в коде, синтаксис и т.д.)
    if process.poll() is not None:
        reason_msg = "Процесс полностью упал или аварийно завершил работу на уровне ОС."
        print(f"[{datetime.now():%d.%m.%Y %H:%M:%S}] КРИТИЧЕСКИЙ СБОЙ: {reason_msg}")
        start_matrix_logger(reason=reason_msg)
        continue

    # 2. Проверка: не зависла ли логика (проверка времени изменения лога)
    if not os.path.exists(HISTORY_LOG_FILE):
        # Если основного файла пинга еще нет, ждем его появления
        continue

    try:
        # Считаем, сколько минут назад изменялся файл пинга
        last_modified_timestamp = os.path.getmtime(HISTORY_LOG_FILE)
        minutes_since_update = (time.time() - last_modified_timestamp) / 60

        if minutes_since_update > MAX_SILENCE_MINUTES:
            reason_msg = f"Лог активности не обновлялся {minutes_since_update:.1f} мин. Скрипт завис."
            print(f"[{datetime.now():%d.%m.%Y %H:%M:%S}] КРИТИЧЕСКИЙ СБОЙ: {reason_msg}")
            start_matrix_logger(reason=reason_msg)

    except Exception as e:
        print(f"Ошибка при анализе файла логов активности: {e}")
