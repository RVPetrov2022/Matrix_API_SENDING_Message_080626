import os, re, time, json, requests
import pandas as pd
from watchdog.observers.polling import PollingObserver as Observer
from watchdog.events import FileSystemEventHandler
import threading
from datetime import datetime


# --- НАСТРОЙКИ СИСТЕМНЫХ ПУТЕЙ ---
LOGS_DIR = "C:/config/Matrix_projects_2026/log_matrix"
EXCEL_FILE = "C:/config/Matrix_projects_2026/output_with_matrix_ids.xlsx"
TOKEN_FILE = "C:/config/Matrix_projects_2026/token.txt"
# Сюда пишется ТОЛЬКО минутный TIME STAMP (файл всегда весит 1 строку)
HISTORY_LOG_FILE = "C:/config/Matrix_projects_2026/sent_messages_history.txt"
MATRIX_URL = "http://192.168.10.15:8008"

# Данные авторизации для автоматического получения токена
MATRIX_USER = "petrov_rv1"
MATRIX_PASS = "Kolondaik_454"

# Настройки Анти-спама
MAX_MSG_PER_MINUTE = 3    

OBJECT_TO_ROOM, OBJECT_TO_ADDRESS, FILE_POSITIONS, CURRENT_TOKEN = {}, {}, {}, ""
MSG_HISTORY = {}
FLOOD_BUFFER = {}


# --- МОДУЛЬ ЖИВУЧЕСТИ TIME STAMP) ---
def run_heartbeat():
    """Фоновая функция для записи временной метки (TIME STAMP) раз в 1 минуту"""
    while True:
        try:
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Перезаписываем файл (режим "w"), чтобы он не разрастался
            with open(HISTORY_LOG_FILE, "w", encoding="utf-8") as f:
                f.write(f"TIME STAMP: {current_time}\n")

        except Exception as e:
            print(f"Ошибка записи пинга активности: {e}")

        # Засыпаем на 1 минуту (60 секунд)
        time.sleep(60)


# Запуск независимого потока-пинга активности
heartbeat_thread = threading.Thread(target=run_heartbeat, daemon=True)
heartbeat_thread.start()


# --- СИСТЕМНЫЕ ФУНКЦИИ ---
def log_to_history_file(text):
    """Используется только для редких критических логов (например, получение токена)"""
    ts = time.strftime("%d.%m.%Y %H:%M:%S")
    try:
        with open(HISTORY_LOG_FILE, "a", encoding="utf-8") as f: 
            f.write(f"[{ts}] {text}\n")
    except Exception: 
        pass

def load_token_from_disk():
    """Принудительное динамическое чтение токена с диска перед отправкой."""
    global CURRENT_TOKEN
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "r", encoding="utf-8") as f:
            CURRENT_TOKEN = f.read().strip()
    return CURRENT_TOKEN

def get_new_token_via_login():
    global CURRENT_TOKEN
    print("[КРИЗИС] Запрашиваю новый токен через /login...")
    try:
        url = f"{MATRIX_URL}/_matrix/client/r0/login"
        payload = {"type": "m.login.password", "user": MATRIX_USER, "password": MATRIX_PASS}
        res = requests.post(url, json=payload, timeout=10)
        if res.status_code == 200:
            CURRENT_TOKEN = res.json().get("access_token")
            with open(TOKEN_FILE, "w", encoding="utf-8") as f: f.write(CURRENT_TOKEN)
            print(f" [+] АВТО-ВОССТАНОВЛЕНИЕ: Новый токен успешно сохранен в token.txt! ({CURRENT_TOKEN[:10]}...)")
            log_to_history_file("Автоматически обновлен токен доступа через API Login.")
            return True
        print(f" [!] Сервер Matrix отклонил пароль: {res.text}"); return False
    except Exception as e: print(f" [!] Ошибка сети при авто-логине: {e}"); return False

def load_mapping():
    global OBJECT_TO_ROOM, OBJECT_TO_ADDRESS
    if not os.path.exists(EXCEL_FILE): print(f"[ОШИБКА] {EXCEL_FILE} не найден!"); return False
    try:
        df = pd.read_excel(EXCEL_FILE, header=None, engine='openpyxl')
        for _, row in df.iterrows():
            raw_obj, itp_addr, room_id = str(row[1]).strip(), str(row[3]).strip(), str(row[4]).strip()
            match = re.search(r"\d+", raw_obj)
            if match and room_id and pd.notna(room_id) and room_id != "nan":
                clean_id = str(int(match.group(0)))
                OBJECT_TO_ROOM[clean_id] = room_id
                OBJECT_TO_ADDRESS[clean_id] = itp_addr
        print(f"[ИНФО] УСПЕШНО: Загружена база сопоставлений на {len(OBJECT_TO_ROOM)} объектов."); return True
    except Exception as e: print(f"[ОШИБКА] Excel: {e}"); return False
################################################################
def parse_and_format_log(filename, obj_id, ip_address, itp_address, raw_line):
    parts = {}
    for item in raw_line.split(';'):
        if '=' in item: k, v = item.split('=', 1); parts[k.strip()] = v.strip()
    dt = parts.get("DATATIME", "Не указано")
    st = str(parts.get("STATE", "unknown")).lower()
    msg = parts.get("MESSAGE", raw_line)
    hdr = "🟢 **СТАТУС: В НОРМЕ**" if st == "off" else ("🔴 **СТАТУС: АВАРИЯ**" if st == "on" else "⚪ **ОБНОВЛЕНИЕ**")
    return f"{hdr}\nID_{obj_id} IP: {ip_address}\nАдрес ИТП: {itp_address}\nTime: {dt}\n📧 Событие: {msg}\n📌 *Лог: {filename}*"

def send_to_matrix(room_id, text, filename, obj_id, retry=True):
    global CURRENT_TOKEN
    url = f"{MATRIX_URL}/_matrix/client/r0/rooms/{room_id}/send/m.room.message"
    
    # Перед отправкой ВСЕГДА проверяем, что написано в файле на диске
    token_on_disk = load_token_from_disk()
    
    # Если файл token.txt пустой, принудительно вызываем авторизацию до отправки запроса
    if not token_on_disk:
        print("[ИНФО] Обнаружен пустой файл token.txt. Запускаю упреждающую авторизацию...")
        if not get_new_token_via_login():
            return False
            
    headers = {"Authorization": f"Bearer {CURRENT_TOKEN}", "Content-Type": "application/json; charset=utf-8"}
    txn_id = f"py_txn_{int(time.time() * 1000)}"
    
    try:
        data_bytes = json.dumps({"msgtype": "m.text", "body": text}, ensure_ascii=False).encode("utf-8")
        res = requests.put(f"{url}/{txn_id}", data=data_bytes, headers=headers, timeout=10)
        if res.status_code == 200:
            print(f" [+] УСПЕШНО ОТПРАВЛЕНО: id{obj_id} ушло в чат.")
            log_to_history_file(f"УСПЕШНО: id{obj_id} -> {room_id}"); return True
        elif (res.status_code == 401 or "token" in str(res.text).lower()) and retry:
            if get_new_token_via_login(): return send_to_matrix(room_id, text, filename, obj_id, retry=False)
        print(f" [!] ОШИБКА MATRIX (Код {res.status_code}): {res.text}"); return False
    except Exception as e: print(f" [!] СЕТЕВАЯ ОШИБКА: {e}"); return False

def parse_filename(filename):
    match = re.match(r"ID[-_](\d+)_(.+)\.alarms", filename, re.IGNORECASE)
    if match: return str(int(match.group(1))), ".".join([str(int(x)) for x in match.group(2).split("_")])
    return None, None

def process_flood_buffer_daemon():
    now = time.time()
    for obj_id, lines in list(FLOOD_BUFFER.items()):
        if not lines: continue
        room_id = OBJECT_TO_ROOM.get(obj_id)
        if room_id:
            itp_address = OBJECT_TO_ADDRESS.get(obj_id, "Адрес отсутствует")
            print(f"\n[АНТИСПАМ] Разгрузка буфера для id{obj_id}. Склеено строк: {len(lines)}")
            header = f"⚠️ 📊 **[ПАКЕТ ПРЕДУПРЕЖДЕНИЙ] Сводный лог флуда**\nID_{obj_id}\nАдрес ИТП: {itp_address}\n-----------------------------------\n"
            final_text = header + "\n\n".join(lines)
            send_to_matrix(room_id, final_text, "Антиспам", obj_id)
            FLOOD_BUFFER[obj_id] = []
            MSG_HISTORY[obj_id] = [now]

class LogUpdateHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if event.is_directory or not event.src_path.lower().endswith('.alarms'): return
        filepath = event.src_path
        filename = os.path.basename(filepath)
        time.sleep(0.12)
        
        obj_id, ip_address = parse_filename(filename)
        if not obj_id or obj_id not in OBJECT_TO_ROOM: return
        room_id = OBJECT_TO_ROOM[obj_id]
        itp_address = OBJECT_TO_ADDRESS.get(obj_id, "Адрес отсутствует")
        
        try:
            current_size = os.path.getsize(filepath)
            old_size = FILE_POSITIONS.get(filepath, 0)
            if current_size == 0 or current_size <= old_size: return
            
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                f.seek(old_size)
                new_lines = f.readlines()
            
            FILE_POSITIONS[filepath] = current_size
            
            for line in new_lines:
                clean_line = line.strip()
                if not clean_line: continue
                
                now = time.time()
                if obj_id not in MSG_HISTORY: MSG_HISTORY[obj_id] = []
                MSG_HISTORY[obj_id] = [t for t in MSG_HISTORY[obj_id] if now - t < 60]
                
                formatted_msg = parse_and_format_log(filename, obj_id, ip_address, itp_address, clean_line)
                
                if len(MSG_HISTORY[obj_id]) >= MAX_MSG_PER_MINUTE or (obj_id in FLOOD_BUFFER and FLOOD_BUFFER[obj_id]):
                    if obj_id not in FLOOD_BUFFER: FLOOD_BUFFER[obj_id] = []
                    FLOOD_BUFFER[obj_id].append(formatted_msg)
                    print(f" [ЗАЩИТА] Флуд на id{obj_id}! Строка добавлена в буфер склейки.")
                else:
                    print(f"\n====== ИЗМЕНЕНИЕ ИТП: id{obj_id} ======")
                    send_to_matrix(room_id, formatted_msg, filename, obj_id)
                    MSG_HISTORY[obj_id].append(now)
                    time.sleep(0.05)
                    
        except Exception as e: print(f" [!] Сбой файла {filename}: {e}")

if __name__ == "__main__":
    print("=========================================================")
    print(" Запуск ИТП-Мониторинга V15.0 (Динамический Контроль)")
    print("=========================================================")
    t_key = load_token_from_disk()
    print(f"[ИНФО] Текущий ключ из token.txt: {t_key[:10]}...{t_key[-6:] if t_key else ''}")
    if load_mapping():
        if os.path.exists(LOGS_DIR):
            for f in os.listdir(LOGS_DIR):
                if f.lower().endswith(".alarms"): FILE_POSITIONS[os.path.join(LOGS_DIR, f)] = os.path.getsize(os.path.join(LOGS_DIR, f))
            print(f"[ИНФО] Контролируем файлов: {len(FILE_POSITIONS)}")
            handler = LogUpdateHandler()
            observer = Observer(timeout=1.0)
            observer.schedule(handler, path=LOGS_DIR, recursive=False)
            observer.start()
            print("[РАБОТА] Ожидаю обновлений файлов автоматики...")
            try:
                while True: 
                    time.sleep(1)
                    process_flood_buffer_daemon()
            except KeyboardInterrupt: observer.stop()
            observer.join()
