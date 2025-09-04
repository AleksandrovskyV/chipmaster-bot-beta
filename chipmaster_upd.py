# ===============================

# chipmaster_upd.py [ > chipmaster_upd.spec > ChatSPT-Updater.exe ]

# Процесс работы:

# chipmaster_upd.py > пакуется через свой .spec в ChatSPT-Updater.exe 
# Содержит все методы для работы с обновлениями \ собственное GUI окно

# chipmaster_bot.py > пакуется через свой .spec в ChatSPT.exe 
# Cодержит ссылки на chipmaster-upd.py, пакуется вместе с ним
# Способен вызывать ChatSPT-Updater.exe из USER_PATH\TEMP_PATH

# Финальный вид:
# В релизе на гит выкладывается актуальная сброка ChatSPT.exe + ChatSPT-Updater.exe

# Сценарий работы:
# Пользователь качает отдельно ChatSPT.exe с гита в любую папку которую хочет. Если отказывает от выбора USER_PATH (кастомной директивы - работаем только на уровне TEMP_PATH)

# ChatSPT.exe на старте выполняет updater.check_silent_spt_update(current_exe=exe_path), который:
# Если не находит "./TEMP_PATH/updater-config.json"
# > всплывает вспомогательное окно, спрашивает пользователя о выборе пользовательской директории (куда пореместить ChatSPT.exe): 
# > Если пользователь отказывается - закрытие вспомогательного окна > конфиг создаётся в TEMP-директории, USER_PATH=TEMP_PATH
# > Если пользователь соглашается  - выбор места создания USER_PATH (имя предложено как ChatSPT_User) > ОК > конфиг создаётся в TEMP_PATH, но USER_PATH=только что выбранная папка. Создаётся копия текущего ChatSPT.exe в USER_PATH.

# Если находит "./TEMP_PATH/updater-config.json":
# > запускает проверку текущей версии/версии с гита ChatSPT.exe > если версия новая > спрашивает об обновлении > если Пользователь соглашается:
# > Проверка наличия ChatSPT-Updater.exe по UPD_PATH > если отсутствует - пробует скачать с гита, если присутствует:
# > Происходит скачивание обновления ChatSPT_new.exe в USER_PATH и открытие ChatSPT-Updater.exe в режиме silent как помощника по закрытию\перезаписи\перезапуску текущего ChatSPT.exe


# ===============================

import sys, os, subprocess, shutil, requests, json, time, tempfile
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

from PySide6.QtCore import Qt, QUrl, QThread, Signal,QTimer
from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox, QFileDialog, QPushButton, QLabel, QVBoxLayout,  QHBoxLayout, QWidget,QDialog,QProgressBar
from PySide6.QtGui import QPalette, QColor, QIcon, QFontMetrics, QDesktopServices


MODE = "gui"

TARGET_EXE = None
SOURCE_EXE = None
LATEST_TAG = None
GLOBAL_CFG = None
SPT_PATH = None


args = sys.argv[1:]
for i in range(len(args)):
    if args[i] == "--mode" and i + 1 < len(args):
        MODE = args[i + 1]
    elif args[i] == "--target" and i + 1 < len(args):
        TARGET_EXE = args[i + 1]
    elif args[i] == "--source" and i + 1 < len(args):
        SOURCE_EXE = args[i + 1]
    elif args[i] == "--version" and i + 1 < len(args):
        LATEST_TAG = args[i + 1]

# ===============================


GITHUB_USER = "AleksandrovskyV"
GITHUB_REPO = "chipmaster-bot-beta"
RELEASE_API_ALL = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/releases"
RELEASE_API_LATEST = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/releases/latest"
prerelease = True

# в релиз кладём оба exe
VERSION = "v0.1.2"
PACK_UPD_VERSION = VERSION
PACK_SPT_VERSION = VERSION
DEF_LANGUAGE = "US"

TEMP_PATH = Path(os.getenv("LOCALAPPDATA")) / "Temp" / "ChatSPT_Temp"
TEMP_PATH.mkdir(parents=True, exist_ok=True)

CONFIG_FILE = TEMP_PATH / "updater-config.json"

def init_config(user_path = None, upd_path = None, spt_path = None, lang = None):
    # Базовация инициализация updater-config.json, если его нет
    default_config = {
        "TEMP_PATH": str(TEMP_PATH),
        "USER_PATH": str(user_path) if user_path is not None else None,
        "UPD_PATH": str(upd_path) if upd_path is not None else None,
        "SPT_PATH": str(spt_path) if spt_path is not None else None,
        "CUSTOM_DIR_FLAG": False,
        "UPD_VERSION": PACK_UPD_VERSION,
        "SPT_VERSION": PACK_SPT_VERSION,       
        "DECL_SPT": None,
        "DECL_UPD": None,
        "LAST_CHECK": None,
        "LANGUAGE": lang if lang is not None else DEF_LANGUAGE
    }
    atomic_save_config(default_config)
    return default_config

def load_config():
    if not CONFIG_FILE.exists():
        return init_config()
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception as e:
        print("Ошибка чтения конфига:", e)
        return init_config()

    return cfg

def save_config(cfg):
    # cfg содержит только JSON-serializable типы (str, None, bool и т.д.)
    atomic_save_config(cfg)

def atomic_save_config(cfg: dict):
    """Атомарно записать CONFIG_FILE: сначала .tmp, затем os.replace."""
    tmp = CONFIG_FILE.with_suffix(".tmp")
    tmp.parent.mkdir(parents=True, exist_ok=True)
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    os.replace(str(tmp), str(CONFIG_FILE))

def resource_path(filename):
    if getattr(sys, "frozen", False):
        # frozen exe → берем из MePass
        return os.path.join(sys._MEIPASS, filename)
    # обычный запуск → берем из исходников
    return os.path.join("assets", filename)

GLOBAL_CFG = load_config() 
SPT_PATH = GLOBAL_CFG.get("SPT_PATH")
CHATSPT_VERSION = GLOBAL_CFG.get("SPT_VERSION")
UPDATER_VERSION = GLOBAL_CFG.get("UPD_VERSION")
LANGUAGE = GLOBAL_CFG.get("LANGUAGE")

# ===============================

# ChatSPT-Updater.exe (silent mode): 
# Helper for replace TARGET_EXE file (kill SOURCE_EXE process, but if fail after wait 25s > warning user and cancel)

if MODE == "silent" and TARGET_EXE and SOURCE_EXE:
    try:
        src = Path(SOURCE_EXE); 
        dst = Path(TARGET_EXE)
        
        if not src.exists():
            #print(f"[Updater] Не найден файл-источник: {src}")
            sys.exit(2)

        name = src.name
        def exists_proc(n):
            try:
                out = subprocess.run(["tasklist","/FI",f"IMAGENAME eq {n}","/NH"], capture_output=True, text=True, timeout=3).stdout.lower()
                return bool(out) and "no tasks are running" not in out
            except Exception:
                return False

        def kill_soft(n):
            try:
                subprocess.run(["taskkill","/IM",n], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3)
            except Exception:
                pass

        if exists_proc(name):
            kill_soft(name)
            deadline = time.time() + 25.0
            while time.time() < deadline and exists_proc(name):
                time.sleep(0.5)
            if exists_proc(name):
                app = QApplication.instance() or QApplication([])
                QMessageBox.warning(None, "Updater", "ChatSPT.exe открыт и мы не можем закрыть его.\n Закройте самостоятельно и пробуйте снова.")
                sys.exit(1)

        try:
            os.replace(str(src), str(dst))

            # Только после успешной замены — обновляем конфиг
            cfg = load_config()
            cfg["SPT_VERSION"] = LATEST_TAG
            save_config(cfg)

            sys.exit(0)
        except Exception:
            app = QApplication.instance() or QApplication([])
            QMessageBox.warning(None, "Updater", "Не удалось заменить файл. Закройте приложение и попробуйте снова.")
            sys.exit(1)

    except Exception as e:
        try:
            app = QApplication.instance() or QApplication([]); QMessageBox.critical(None, "Ошибка", f"Ошибка в режиме silent:\n{e}")
        except Exception:
            print(f"Ошибка: {e}", file=sys.stderr)
        sys.exit(10)

# ===============================

# Методы работы с GitHub

def get_latest_asset(asset_name: str):
    try:
        if prerelease:
            r = requests.get(RELEASE_API_ALL, timeout=5)
            r.raise_for_status()
            data = r.json()
            if not data:
                return "empty", None
            latest_release = data[0]
        else:
            r = requests.get(RELEASE_API_LATEST, timeout=5)
            r.raise_for_status()
            latest_release = r.json()

        latest_tag = latest_release.get("tag_name")
        download_url = None
        for asset in latest_release.get("assets", []):
            if asset["name"] == asset_name:
                download_url = asset["browser_download_url"]
                break

        return latest_tag, download_url

    except requests.exceptions.HTTPError as e:
        status = e.response.status_code
        return f"http_error_{status}", None
    except requests.exceptions.Timeout:
        return "timeout", None
    except Exception as e:
        return f"error_{type(e).__name__}", None


def download_update(url, save_path):
    try:
        r = requests.get(url, stream=True)
        r.raise_for_status()
        total_size = int(r.headers.get('content-length', 0))  # общий размер файла
        downloaded = 0
        chunk_size = 8192

        with open(save_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=chunk_size):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        progress = downloaded / total_size * 100
                        # Печатаем прогресс в процентах, перезаписывая строку
                        sys.stdout.write(f"\rСкачано: {progress:.2f}%")
                        sys.stdout.flush()

        print("\nСкачивание завершено!")
        return True
    except Exception as e:
        print("Ошибка при скачивании обновления:", e)
        return False

# ===============================

# Special methods

def _is_frozen() -> bool:
    return getattr(sys, "frozen", False)

# добавлял, чтобы искать Updater по соседству с ChatSPT если он устанавливается в конкретную директорию
def get_embedded_path(rel_name: str) -> Path:
    """
    Возвращает путь к встроенному ресурсу (работает в onefile через sys._MEIPASS).
    В режиме запуска из исходников ищет рядом со скриптом.
    """
    if _is_frozen() and hasattr(sys, "_MEIPASS"):
        base = Path(sys._MEIPASS)
    else:
        base = Path(__file__).parent
    return base / rel_name

def try_handoff(current_exe: str = None, path_config_key: str = None) -> bool:
    # Передаём управление программе из кастомной директории, 
    # Если существует кастомная директория и в ней есть файл 

    if not CONFIG_FILE.exists():
    # Если нет конфига — нечего передавать
        return False
    else:
        cfg = load_config()

    installed_upd = cfg.get(path_config_key)
    install_flag = cfg.get("CUSTOM_DIR_FLAG")
    if install_flag == False:
        return False

    if not installed_upd:
        return False

    installed = Path(installed_upd)
    current = Path(current_exe)

    # --- ВАША ПРОСЬБА: сравниваем имена файлов и только при совпадении продолжаем ---
    # если имена файлов (basename) не совпадают — не выполнять handoff
    if installed.name.lower() != current.name.lower():
        print(f"[UPD] filename mismatch: {installed.name} != {current.name} — skipping handoff")
        return False

    if installed_upd == None:
        return False
    
    if installed.exists() and installed.resolve() != current.resolve():
        try:
            subprocess.Popen([str(installed)])
            return True
        except Exception as e:
            print("Не удалось сделать handoff:", e)
    return False


# SILENT - внешние вызовы из chimpaster_bot.py | ChatSPT.exe

MESSAGE_TEXT = {
    "initTitle": {
        "US": "Initialизация.",
        "RU": "Инициалization",
    },
    "initQuest": {
        "US": "Set custom folder or work from Shortcut?",
        "RU": "Задать свою папку или работать от ярлыка?",
    }, 
    "install_btn": {
        "US": "Install..",
        "RU": "Установка",
    },  
    "shortcut_btn": {
        "US": "Shortcut!",
        "RU": "от Ярлыка",
    },  
    "notConnection": {
        "US": "I cannot connection to GITHUB     \n or can't find repository... Sorry!",
        "RU": "Не удалось установить соединение    \nили найти репозиторию GIT.. Увы!",
    },
    "PipeClogged": {
        "US": "Well...\nPipe is clogged?! Hmm… try again later!",
        "RU": "Такое дело...\nПоходу труба забита, попробуй позже!",
    },
    "updateQuest": {
        "US": "Update available...\nDownload & refresh?",
        "RU": "Доступно обновление...\nСкачать и установить?",
    },      
    "instllUpdater": {
        "US": "Need install ChatSPT-Updater...\nDownload & install?",
        "RU": "Требуется установить Updater...\nСкачать и установить?",
    },
    "needUpdater": {
        "US": "Update available... But...\nNeed install Updater... Install?",
        "RU": "Доступно обновление ChatSPT, но...\nНеобходим Updater. Установить его?",
    },
    "SelectLanguage": {
        "US": "Предпочитаемый language?",
        "RU": "Предпочитаемый language?",
    },
    "yes": {
        "US": "Yes!",
        "RU": "Да!",
    },
    "no": {
        "US": "No.",
        "RU": "Нет.",
    },
    "startDownload": {
        "US": "Starting downloads...",
        "RU": "Начинаю скачивание...",
    },   
    "succesDownload": {
        "US": "Update downloaded...\nRestart?",
        "RU": "Обновление загружено.\nПерезапустить?",
    },  
    "installedDirectly": {
        "US": "Update downloaded...",
        "RU": "Обновление загружено.",
    },
    "error": {
        "US": "Error",
        "RU": "Ошибка",
    },
    "ok": {
        "US": "Ok!",
        "RU": "Ок.",
    },
    "error_text": {
        "US": "Failed to download update!",
        "RU": "Не удалось скачать обновление!",
    },
    "error_text_a": {
        "US": "I couldn't download\nChatSPT-Updater.exe!",
        "RU": "Не удалось скачать\nChatSPT-Updater.exe",
    },
    "error_text_b": {
        "US": "I couldn't find\nChatSPT-Updater.exe!",
        "RU": "Не удалось найти\nChatSPT-Updater.exe",
    },
    "error_text_c": {
        "US": "I couldn't run\nChatSPT-Updater.exe!",
        "RU": "Не удалось запустить\nChatSPT-Updater.exe",
    }
}

class DownloadThread(QThread):
    progress = Signal(float)           # процент 0..100
    finished = Signal(bool, str)       # (success, error_message_or_empty)

    def __init__(self, url: str, save_path: Path, parent=None):
        super().__init__(parent)
        self.url = url
        self.save_path = Path(save_path)

    def run(self):
        try:
            r = requests.get(self.url, stream=True, timeout=30)
            r.raise_for_status()
            total = int(r.headers.get("content-length", 0))
            downloaded = 0
            chunk = 8192
            with open(self.save_path, "wb") as f:
                for data in r.iter_content(chunk_size=chunk):
                    if not data:
                        continue
                    f.write(data)
                    downloaded += len(data)
                    if total:
                        pct = downloaded / total * 100.0
                        self.progress.emit(pct)
            self.finished.emit(True, "")
        except Exception as e:
            self.finished.emit(False, str(e))

@dataclass
class UpdateContext:
    url: Optional[str] = None
    exe_path: Optional[Path] = None
    temp_file: bool = False
    latest_tag: Optional[str] = None
    message: Optional[str] = None


class QuestionDialog(QDialog):
    """
    Универсальный диалог: 
    режим 'init' - первичный вопрос о работе ChatSPT: либо работать с ярлыка, куда скачан ChatSPT, либо выбрать кастомную директиву
    режим 'update' - при выходе новой версии: увидеомление пользователя. Если пользователь соглашается > скачка > предложение о перезапуске
    """
    def __init__(self, dialog_state: str, config: dict = None, context: UpdateContext = None, parent=None):
        super().__init__(parent)
        
        self.lang = LANGUAGE

        self.setWindowTitle(MESSAGE_TEXT["initTitle"][self.lang])
        self.setFixedSize(420, 160)
        self.cfg = config or {}
        self.context = context
        self.temp = bool(getattr(self.context, "temp_file", False))
        self.dialog_state = dialog_state

        # UI
        self.layout = QVBoxLayout(self)
        self.label = QLabel("")
        self.label.setAlignment(Qt.AlignCenter)

        if self.context and getattr(self.context, "message", None):
            self.label.setText(self.context.message)

        # Это текст, который ты называешь "status_label" — оставляем как отдельный QLabel
        self.status_label = QLabel("")
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)

        self.layout.addWidget(self.label)
        self.layout.addWidget(self.status_label)
        self.layout.addWidget(self.progress)

        # Buttons area
        self.button_layout = QHBoxLayout()
        self.layout.addLayout(self.button_layout)

        # init buttons
        self.lang_eng = QPushButton("BRITISH")
        self.lang_rus = QPushButton("РУССКИЙ")

        self.install_btn = QPushButton(MESSAGE_TEXT["install_btn"][self.lang])
        self.install_btn.setEnabled(False)   # заблокировать

        self.shortcut_btn = QPushButton(MESSAGE_TEXT["shortcut_btn"][self.lang])

        # start-update buttons
        self.start_update_btn = QPushButton(MESSAGE_TEXT["yes"][self.lang]) 
        self.cancel_update_btn = QPushButton(MESSAGE_TEXT["no"][self.lang])  
        self.update_no_btn = QPushButton(MESSAGE_TEXT["no"][self.lang])
        self.update_ys_btn = QPushButton(MESSAGE_TEXT["yes"][self.lang])

        # message\error apply btn
        self.ok_btn = QPushButton(MESSAGE_TEXT["ok"][self.lang]) 
        
        # Скрываем все
        for w in (self.lang_eng, self.lang_rus, self.install_btn, self.shortcut_btn, self.start_update_btn, self.cancel_update_btn,
                  self.update_no_btn, self.update_ys_btn,self.ok_btn):
            self.button_layout.addWidget(w)
            w.hide()

        # сигналы 
        self.ok_btn.clicked.connect(self.accept)

        # Подключения для начального состояния
        self.lang_rus.clicked.connect(self.switch_lang_toRU)
        self.lang_eng.clicked.connect(self.nextState)

        self.install_btn.clicked.connect(self._on_install_clicked)
        self.shortcut_btn.clicked.connect(self.reject)
        self.start_update_btn.clicked.connect(self.start_update)
        self.cancel_update_btn.clicked.connect(self.reject)

        # Подключения для подтверждения после скачивания
        self.update_no_btn.clicked.connect(self.reject)
        self.update_ys_btn.clicked.connect(self.acceptUpdate_clicked)

        # thread holder & pending launch args
        self._download_thread = None
        self._pending_temp_file: Path | None = None
        self._pending_exe_path: Path | None = None

        # применяем стили ко всему окну
        self.setStyleSheet("""
            QWidget { background-color: black;  color: white; font-size: 16px; }
            QPushButton { background-color: black; color: white; font-size: 14px;
                border: 1px solid grey;
                border-radius: 5px;
                padding: 5px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #222; }
            QPushButton:pressed { background-color: #444; }
        """)
        self.install_btn.setStyleSheet("color: grey;")
        # apply initial UI state
        self._apply_state(self.dialog_state)

    def switch_lang_toRU(self):
        #if new_lang == "RU":
        global LANGUAGE
        self.lang = "RU"
        LANGUAGE = "RU"

        self.install_btn.setText(MESSAGE_TEXT["install_btn"][self.lang])
        self.shortcut_btn.setText(MESSAGE_TEXT["shortcut_btn"][self.lang])
        self.setWindowTitle(MESSAGE_TEXT["initTitle"]["US"])
        self.label.setText(MESSAGE_TEXT["initQuest"][self.lang])
        self.lang_eng.hide()
        self.lang_rus.hide() 

        self.install_btn.show()
        self.shortcut_btn.show()     

    def nextState(self):
        self.label.setText(MESSAGE_TEXT["initQuest"][self.lang])
        self.setWindowTitle(MESSAGE_TEXT["initTitle"]["RU"])
        self.lang_eng.hide()
        self.lang_rus.hide() 
        self.install_btn.show()
        self.shortcut_btn.show()  

    def reject(self):
        # Перед закрытием диалога можно обновить конфиг
        if self.dialog_state == "init":
            if self.cfg is not None:
                self.cfg['LANGUAGE'] = self.lang  # сохраняем выбранный язык
        super().reject()

    def _apply_state(self, state: str):
        # hide all optional widgets first
        self.status_label.hide()
        self.progress.hide()
        self.install_btn.hide()
        self.shortcut_btn.hide()
        self.start_update_btn.hide()
        self.cancel_update_btn.hide()
        self.update_no_btn.hide()
        self.update_ys_btn.hide()
        self.ok_btn.hide()

        if state == "init":
            self.label.setText(MESSAGE_TEXT["SelectLanguage"][self.lang])
            self.lang_eng.show()
            self.lang_rus.show()
            #self.install_btn.show()
            #self.shortcut_btn.show()

        elif state == "update":
            if self.context and getattr(self.context, "message", None):
                self.label.setText(self.context.message)
            else:
                self.label.setText(MESSAGE_TEXT["updateQuest"][self.lang])
            self.start_update_btn.show()
            self.cancel_update_btn.show()
            self.status_label.setText("")
            self.status_label.show()
            self.progress.hide()

        elif state == "error":
            self.ok_btn.show()
            self.label.setText(MESSAGE_TEXT["error"][self.lang])
        elif state == "message":
            self.ok_btn.show()
        else:
            self.label.setText("")

    def _on_install_clicked(self):
        self.accept()

    def start_update(self):
        # стартуем загрузку: закрыть процесс, запустить поток

        if not self.context or not self.context.url or not self.context.exe_path:
            print("[QuestionDialog] - Missing update context")
            return

        url = self.context.url
        exe_path = Path(self.context.exe_path)

        # защита чтобы не переписывал py файлы во времят теста
        if exe_path.name not in ("ChatSPT.exe", "ChatSPT-Updater.exe"):
            self.status_label.setText("Target Name Diffirent - Sorry")
            self.ok_btn.show()             # OK закрывает диалог (accept)
            self.update_no_btn.hide()
            self.update_ys_btn.hide()
            self.start_update_btn.hide()
            self.cancel_update_btn.hide()
            exe_path = None
            url = None
            return

        temp_file = None
        if self.temp:
            # это проверил, корректно
            temp_file = exe_path.parent / (exe_path.stem + "_new" + exe_path.suffix)


        ### Я думаю здесь проблема
        print(f"exe_path = {exe_path}, temp_file = {temp_file}")

        if temp_file == None:
            # 1) закрываем процесс если без temp
            if not ensure_process_closed(exe_path):
                self.status_label.setText(STATUS_TEXT["error_c"][self.lang])
                return

        # блокируем кнопки
        self.start_update_btn.setEnabled(False)
        self.cancel_update_btn.setEnabled(False)
        self.status_label.setText(MESSAGE_TEXT["startDownload"][self.lang])
        self.progress.setValue(0)
        self.status_label.show()
        self.progress.show()

        save_target = temp_file if self.temp else exe_path
        if save_target is None:
            # защита: если по какой-то причине temp ожидается, но не сформирован
            self.status_label.setText(MESSAGE_TEXT["error"][self.lang])
            self.start_update_btn.setEnabled(True)
            self.cancel_update_btn.setEnabled(True)
            return

        self._download_thread = DownloadThread(url, save_target)
        self._download_thread.progress.connect(self.progress_download)
        self._download_thread.finished.connect(lambda ok, err: self.download_finished(ok, err, temp_file, exe_path))
        self._download_thread.start()

    def progress_download(self, pct: float):
        self.progress.setValue(int(pct))
        self.status_label.setText(f"{int(pct)}%")

    def download_finished(self, success: bool, error_msg: str, temp_file: Optional[Path], exe_path: Path):

        if not success:
            # Ошибка — вернуться в исходное состояние, разрешив повтор
            self.status_label.setText(MESSAGE_TEXT["error"][self.lang])
            self.start_update_btn.setEnabled(True)
            self.cancel_update_btn.setEnabled(True)
            return

        # Если это updater — обновляем конфиг (сохранение пути/версии)
        try:
            if exe_path.name.lower() == "chatspt-updater.exe":
                # используем self.cfg (оно инициализировано в __init__)
                self.cfg["UPD_PATH"] = str(exe_path)

                if getattr(self.context, "latest_tag", None):
                    self.cfg["UPD_VERSION"] = self.context.latest_tag
                save_config(self.cfg)
        except Exception as e:
            print("[QuestionDialog] - failed to save updater cfg:", e)

        # Успешно скачано: оставляем прогресс 100% и просим подтверждения перезапуска
        self.progress.setValue(100)
        
        # обновляем основной вопрос (label)
        
        self.status_label.setText("100%")

        # Сохраняем аргументы для запуска апдейтера при нажатии "Да"
        self._pending_temp_file = temp_file
        self._pending_exe_path = exe_path

        # Если скачали "в место" (нет temp) — уведомляем пользователя и показываем OK.
        if temp_file is None:
            # Скрываем прежние кнопки подтверждения (если были)
            self.start_update_btn.hide()
            self.cancel_update_btn.hide()
            self.update_no_btn.hide()
            self.update_ys_btn.hide()

            # Показываем информационный текст (используем ключ, если есть; иначе простой текст)
            self.label.setText(MESSAGE_TEXT["installedDirectly"][self.lang])
            self.ok_btn.show()
            # ждём нажания OK пользователем
            return


        self.label.setText(MESSAGE_TEXT["succesDownload"][self.lang])
        # Скрываем кнопки старого состояния и показываем подтверждение: NO | YES

        self.start_update_btn.hide()
        self.cancel_update_btn.hide()
        self.update_no_btn.show()
        self.update_ys_btn.show()
        # убеждаемся, что кнопки активны
        self.update_no_btn.setEnabled(True)
        self.update_ys_btn.setEnabled(True)

    def acceptUpdate_clicked(self):
        #  User > [YES] — startUpdater (используем сохранённые pending args)
        if self._pending_temp_file == None: # Скачивание было напрямую, Confirm просто закрывает окно без запуск процесса
            self.label.setText(MESSAGE_TEXT["installedDirectly"][self.lang])
            self.ok_btn.show()             # OK закрывает диалог (accept)
            self.update_no_btn.hide()
            self.update_ys_btn.hide()
            return
        else: 
            if not self._pending_temp_file or not self._pending_exe_path:
                print("[QuestionDialog] - Missing temp_file or exe_path")
                self.reject() # > close QuestionDialog
                return
            self.laucnhUpdater(self._pending_temp_file, self._pending_exe_path)

    def laucnhUpdater(self, temp_file: Path, exe_path: Path):
        # Start  ChatSPT-Updater.exe in Silent Mode

        upd_path_str = self.cfg.get("UPD_PATH")
        updater_path = Path(upd_path_str) if upd_path_str else None
        

        if not updater_path or not updater_path.exists():
            if not ensure_updater_exists():
                print("[QuestionDialog] - ChatSPT-Updater.exe not found")
                self.reject() # > close QuestionDialog
                return
            # пробуем ещё после ensure_updater_exists?
            updater_path = Path(self.cfg.get("UPD_PATH"))

        try:
            # SPT_VERSION в конфиге обновится через процесс
            subprocess.Popen([str(updater_path), "--mode", "silent",
                              "--target", str(exe_path),
                              "--source", str(temp_file)])
            # start process - > close 
            sys.exit(0)
            #self.accept()
        except Exception as e:
            message = MESSAGE_TEXT["error_text_c"][self.lang]
            print(f"[QuestionDialog] - {message}") 
            self.reject() # > close QuestionDialog



def check_silent_spt_update(exe: str = None):
    """
    Check config in TEMP_PATH and new version ChatSPT.exe from GIT 
    """
    cfg = load_config()
    current_exe_cfg = cfg.get("SPT_PATH")
    current_exe = exe

    # init step
    if current_exe_cfg is None or current_exe != current_exe_cfg:
        init_ctx = UpdateContext(url="", exe_path=Path(current_exe) if current_exe else Path(TEMP_PATH))
        init_dlg = QuestionDialog(dialog_state="init", config=cfg, context=init_ctx)
        result = init_dlg.exec()
        print("Выбранный язык:", cfg.get("LANGUAGE"))
        if result != QDialog.Accepted:
            init_config(user_path=TEMP_PATH, spt_path=str(current_exe), lang=cfg.get("LANGUAGE"))
            GLOBAL_CFG["LANGUAGE"] = cfg.get("LANGUAGE")
            #init_config(user_path=TEMP_PATH, spt_path=str(current_exe))
        else:
            set_user_path(current_exe=current_exe)
        # первая инициализация не мучаем обновлениями
        return False

    curent_version = cfg.get("SPT_VERSION") or PACK_SPT_VERSION
    exe_path = Path(current_exe) if current_exe else Path(cfg.get("SPT_PATH"))

    latest_tag, url = get_latest_asset("ChatSPT.exe")
    if not latest_tag or not url:
        return False

    declined_version = cfg.get("DECL_SPT")
    if declined_version == latest_tag:
        return False

    need_update = not exe_path.exists() or curent_version != latest_tag
    if not need_update:
        return False

    if not ensure_updater_exists("ChatSPT"):
        cfg["DECL_SPT"] = latest_tag
        save_config(cfg)
        return False

    # preparing context and dialog for download ChatSPT.exe
    #temp_file = Path(TEMP_PATH) / "ChatSPT-new.exe"
    update_context = UpdateContext(url=url, exe_path=exe_path, latest_tag=latest_tag, temp_file=True) 
    update_dlg = QuestionDialog(dialog_state="update", config=cfg, context=update_context)
    reply = update_dlg.exec()

    if reply == QDialog.Accepted:
        # QDialog start ChatSPT-Updater.exe
        return True
    else:
        # error or decline > save declined version ChatSPT.exe
        cfg["DECL_SPT"] = latest_tag
        save_config(cfg)
        return False


def ensure_updater_exists(loadfrom=None):
    """
    # Call from ChatSPT.exe
    Check ChatSPT-Updater.exe in USER_PATH/TEMP_PATH.
    Если файла нет > пытаемся скачать с гита > если неудачно > пишем, что не можем подсоединиться к гиту
    Если файл есть > сверяет текущую версию с последней из GitHub. > предложит пользователю установку более новой версии
    Если пользователь откажется -> запишет в конфиг как отмененная версия
    Если пользователь согласится > скачает новую версию с гита и заменить по пути UPD_PATH взятого из конфига
    Возвращает True если Updater гарантированно есть после вызова.
    """
    cfg = load_config()

    ins_path_str = cfg.get("USER_PATH")
    upd_path_str = cfg.get("UPD_PATH")  # может быть None
    
    install_path = Path(ins_path_str) if ins_path_str else None
    updater_path = Path(upd_path_str) if upd_path_str else None
    
    declined_version = cfg.get("DECL_UPD")
    curent_version = cfg.get("UPD_VERSION") or PACK_UPD_VERSION

    latest_tag, url = get_latest_asset("ChatSPT-Updater.exe")

    print(f"A = latest_tag = {latest_tag}, url = {url}, updater_path ={updater_path}")

    # к гиту не подключились, апдейтера нет
    if not updater_path and (not latest_tag or not url):
        print("Updater: Not connection to Github")
        
        
        if latest_tag == "http_error_403":
            NotConnectionMessage = MESSAGE_TEXT["PipeClogged"][LANGUAGE]
        else:
            NotConnectionMessage = MESSAGE_TEXT["notConnection"][LANGUAGE]

        NotConnectionContext = UpdateContext(message=NotConnectionMessage)
        NotConnectionDialog = QuestionDialog(dialog_state="message", config=cfg, context=NotConnectionContext)
        NotConnectionDialog.exec()
        return False

    # У пользователя нет апдейтера - просто качаем с гита в его директиву
    if not updater_path:
        upd_file = Path(install_path) / "ChatSPT-Updater.exe"
        
        if loadfrom == "ChatSPT":
            upd_message = MESSAGE_TEXT["needUpdater"][LANGUAGE]
        else:
            upd_message = MESSAGE_TEXT["instllUpdater"][LANGUAGE]

        updatedown_contxt = UpdateContext(message=upd_message, url=url, exe_path=upd_file, latest_tag=latest_tag, temp_file=False)
        updatedown_dialog = QuestionDialog(dialog_state="update", config=cfg, context=updatedown_contxt)
        answer = updatedown_dialog.exec()

        # вот здесь если пользователь отменил (reject) нужно просто сделать 
        #retun False (иначе пойдем дальше и у нас не будет апдейтера)
        
        if answer == QDialog.Rejected:
            if loadfrom == "ChatSPT":
                pass

            return False
        else:
            if upd_file.exists():
                subprocess.Popen([upd_file])
                return False



    # последний релиз = текущему
    if latest_tag==curent_version:
        print("[INFO] latest_tag==curent_version ")
        return True

    # последний релиз = отменененному
    if latest_tag==declined_version:
        print("[INFO] latest_tag==declined_version ")
        return True


    # спрашиваем об обновлении ChatSPT-Updater.exe
    # preparing context and dialog for download ChatSPT-Updater.exe
    update_context = UpdateContext(url=url, exe_path=updater_path, latest_tag=latest_tag, temp_file=False)
    update_dialog = QuestionDialog(dialog_state="update", config=cfg, context=update_context)
    update_reply  = update_dialog .exec()

    if update_reply == QDialog.Accepted:
        # Скачивание происходит через QuestionDialog
        return True
    else:
        # Пользователь отказался — устанавливаем declined для UPD, сохраняем конфиг
        cfg["DECL_UPD"] = latest_tag
        save_config(cfg)

        # Если файл уже есть — всё ок
        if updater_path != None:
            if updater_path.exists():
                return True
            else:
                return False


def run_updater_process():
    # Запускает ChatSPT-Updater.exe
    if CONFIG_FILE.exists():
        try:
            cfg = load_config()
            updater_path = cfg.get("UPD_PATH")
            if updater_path and Path(updater_path).exists():
                print("ЗАПУСКАЮ ПРОЦЕСС:", updater_path)
                subprocess.Popen([updater_path])
                return True
        except Exception as e:
            print("Ошибка запуска апдейтера:", e)
    return False


def set_user_path(parent=None, current_exe: str = None):
    # Ключевая логика задавания USER_PATH (пользовательской директивы)
    # Пользователь задаёт папку > туда копируется актуальный ChatSPT.exe

    # если передан текущий .exe — используем его, иначе ставим стандартное место установки (из конфига)
    if current_exe:
        exe_path = Path(current_exe) # Передаём путь на текущий .exe
    else:
        exe_path = Path(GLOBAL_CFG.get("SPT_PATH") or "") # Передаём путь на .exe из конфига

    folder = QFileDialog.getExistingDirectory(parent, "Задайте папку", str(Path.home() / "ChatSPT_User"))
    if not folder:
        return

    install_dir = Path(folder)

    exe_name = exe_path.name
    src_chatspt = exe_path 
    dst_chatspt = install_dir / exe_name

    # если пользователь меняет директиву через апдейтер, копируем и апдейтере по соседству
    # Ззадел на будущее - удаление прошлой папки

    updater_name = "ChatSPT-Updater.exe"
    src_updater = exe_path.parent / updater_name
    dst_updater = install_dir / updater_name

    try:
        # Копируем ChatSPT.exe
        if not dst_chatspt.exists():
            shutil.copy2(src_chatspt, dst_chatspt)

        if src_updater.exists() and not dst_updater.exists():
            shutil.copy2(src_updater, dst_updater)


    except Exception as e:
        QMessageBox.warning(parent, "Ошибка копирования", f"Не удалось копировать файлы:\n{e}")
        return False

    # Обновляем конфиг: ChatSPT и апдейтер теперь в пользовательской директории 
    GLOBAL_CFG["USER_PATH"] = str(install_dir)
    GLOBAL_CFG["SPT_PATH"]  = str(dst_chatspt)
    GLOBAL_CFG["CUSTOM_DIR_FLAG"] = True
    if dst_updater.exists():
        GLOBAL_CFG["UPD_PATH"] = str(dst_updater)
    
    save_config(GLOBAL_CFG)
    return folder


def call_updater():
    # Вызов с кнопки из ChatSPT.exe ( вызов GUI MODE, т.е отдельного окна)
    if ensure_updater_exists():
        print("Проверили апдейтер")
        run_updater_process()


# GUI обёртка для ChatSPT-Updater.exe

INFO_TEXT = {
    "descr_text": {
        "US": "No updates are expected,\nbut who knows...?",
        "RU": "Обновлений не подразумевается,\nно кто его знает...?",
    },
    "config_text": {
        "US": "Config _?",
        "RU": "Конфиг _?",
    },
    "storage_text": {
        "US": "Data storage in folder:",
        "RU": "Данные хранятся в папке :",
    }
}

BUTTON_TEXT = {
    "setFolder": {
        "US": "Set storage folder!",
        "RU": "Задать место установки!",
    },
    "update": {
        "US": "Check for updates!",
        "RU": "Проверить обновление!",
    },
    "install": {
        "US": "Install!",
        "RU": "Установить!",
    },
    "decline": {
        "US": "Decline!",
        "RU": "Не в этот раз!",
    },
    "accept": {
        "US": "Accept!",
        "RU": "Давай попробуем!",
    },
    "close": {
        "US": "Close!",
        "RU": "Закрыть!",
    }
}

STATUS_TEXT = {
    "installing": {
        "US": "Installing update...",
        "RU": "Устанавливаю обновление...",
    },    
    "succes_inst": {
        "US": "Complete!\nCheck this...",
        "RU": "Успешно! Потестируем! ",
    },
    "error_a": {
        "US": "Hey!\nStorage folder is not set...",
        "RU": "Слушай!\nПапка хранения не определена...",
    },
    "error_b": {
        "US": "Well...\nI couldn't find any updates",
        "RU": "Такое дело...\nЯ Не смог найти обновления",
    },
    "error_c": {
        "US": "Well...\nI couldn't stop ChatSPT process",
        "RU": "Такое дело...\nЯ Не смог закрыть ChatSPT...",
    },
    "error_с": {
        "US": "Well...\nPipe is clogged?! Hmm… try again later!",
        "RU": "Такое дело...\nПоходу труба забита, попробуй позже!",
    },
    "replace_quest": {
        "US": "I see updates!\nInstall ChatSPT",
        "RU": "Вижу обновления!\nУстановить ChatSPT",
    },
    "to": {
        "US": "to",
        "RU": "на",
    },
    "download": {
        "US": "Download updates: ",
        "RU": "Скачиваю обновления: ",
    },
    "notUpdates": {
        "US": "Not updates...",
        "RU": "Обновлений нет...",
    },
    "reply_decline": {
        "US": "Okay...",
        "RU": "Ладно...",
    }
}

def ensure_process_closed(exe_path):
    """Проверяет, запущен ли exe, и пытается его закрыть."""

    name = Path(exe_path).name
    
    print (f"Закрываем {name}")

    def exists_proc(n):
        try:
            out = subprocess.run(
                ["tasklist", "/FI", f"IMAGENAME eq {n}", "/NH"],
                capture_output=True,
                text=True,
                timeout=3
            ).stdout.lower()
            return bool(out) and "no tasks are running" not in out
        except Exception:
            return False

    def kill_soft(n):
        try:
            subprocess.run(
                ["taskkill", "/IM", n],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=3
            )
        except Exception:
            pass

    if exists_proc(name):
        kill_soft(name)
        deadline = time.time() + 25.0
        while time.time() < deadline and exists_proc(name):
            time.sleep(0.5)
        if exists_proc(name):
            app = QApplication.instance() or QApplication([])
            QMessageBox.warning(
                None,
                "Updater",
                f"{name} открыт и мы не можем закрыть его.\nЗакройте самостоятельно и попробуйте снова."
            )
            return False
    return True

class UpdaterWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ChatSPT Updater")
        self.setFixedSize(400, 400)
        icon_path = resource_path("ChatSPT-Updater.ico")
        self.setWindowIcon(QIcon(icon_path))

        layout = QVBoxLayout()
        layout.setContentsMargins(35, 40, 35, 40)
        layout.setSpacing(10)  # расстояние между виджетами

        self.lang = LANGUAGE
        self.user_path = GLOBAL_CFG.get("USER_PATH")
        self.url = None
        self.exe_path = None

        self.descr_label = QLabel()
        self.descr_label.setText(INFO_TEXT["descr_text"][self.lang])

        self.version_label = QLabel(f"ChatSPT {CHATSPT_VERSION}  :  Updater {UPDATER_VERSION}")
        self.storage_label = QLabel()

        self.status_label  = QLabel() # STATUS_TEXT

        self.btn_setFolder = QPushButton() 
        self.btn_setFolder.setText(BUTTON_TEXT["setFolder"][self.lang])
        self.btn_setFolder.clicked.connect(self.check_SetFolder)
        self.btn_setFolder.setEnabled(False) 

        self.btn_update = QPushButton()
        self.btn_update.setText(BUTTON_TEXT["update"][self.lang]) 
        self.btn_update.clicked.connect(self.check_update)

        self.btn_decline = QPushButton()
        self.btn_decline.setText(BUTTON_TEXT["decline"][self.lang]) 
        self.btn_decline.clicked.connect(self.check_decline)  
        self.btn_decline.hide()

        self.btn_install = QPushButton()
        self.btn_install.setText(BUTTON_TEXT["install"][self.lang])
        self.btn_install.clicked.connect(self.start_Update)
        self.btn_install.hide()

        self.btn_close = QPushButton()
        self.btn_close.setText(BUTTON_TEXT["close"][self.lang])
        self.btn_close.clicked.connect(self.close)
        self.btn_close.hide()

        layout.addWidget(self.descr_label)
        layout.addWidget(self.version_label)
        layout.addSpacing(10)
        layout.addWidget(self.storage_label)
        layout.addSpacing(10)
        layout.addWidget(self.status_label)
        #layout.addSpacing(50)
        layout.addStretch(1)

        layout.addWidget(self.btn_setFolder)
        layout.addWidget(self.btn_update)
        layout.addWidget(self.btn_close)

        layout.addWidget(self.btn_decline)
        layout.addWidget(self.btn_install)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        # применяем стили ко всему окну
        self.setStyleSheet("""
            QWidget {
                background-color: black;
                color: white;
                font-size: 16px; 
            }

            QPushButton {
                background-color: black;
                color: white;
                border: 1px solid grey;
                border-radius: 5px;
                padding: 5px;
                font-size: 14px;
                font-weight: bold;
            }

            QPushButton:hover {
                background-color: #222;
            }

            QPushButton:pressed {
                background-color: #444;
            }
        """)

        self.btn_setFolder.setStyleSheet("color: grey;")



    def open_path(self, url):
        print("Activated URL:", url)
        QDesktopServices.openUrl(QUrl.fromLocalFile(url))
        
        self.storage_label.clearFocus()

    def update_storage_label(self):
        if not self.user_path:
            self.storage_label.setText(INFO_TEXT["config_text"][self.lang])
        else:
            pretext = INFO_TEXT['storage_text'][self.lang]
            path = self.user_path or ""
            fm = QFontMetrics(self.storage_label.font())
            elided_path = fm.elidedText(path, Qt.ElideLeft, self.storage_label.width())

            html = f"""
            {pretext}<br>
            <a href="file:///{path}" style="color: gray; text-decoration: underline;">
                {elided_path}
            </a>
            """

            self.storage_label.setText(html)
            self.storage_label.setTextInteractionFlags(Qt.TextBrowserInteraction)
            self.storage_label.setOpenExternalLinks(False)  # обрабатываем сами
            self.storage_label.linkActivated.connect(self.open_path)

            
    def switch_lang(self, new_lang):
        
        # Обновляем status_label, если текст совпадает с одним из текущих статусов
        current_text = self.status_label.text()
        for key, translations in STATUS_TEXT.items():
            if current_text == translations.get(self.lang, ""):
                self.status_label.setText(translations[new_lang])
                break

        self.lang = new_lang

        # Обновляем лейблы
        self.descr_label.setText(INFO_TEXT["descr_text"][self.lang])
        if not self.user_path:
            self.storage_label.setText(INFO_TEXT["config_text"][self.lang])
        else:
            self.storage_label.setText(f"{INFO_TEXT['storage_text'][self.lang]}\n{self.user_path}")

        # Обновляем кнопки
        self.btn_setFolder.setText(BUTTON_TEXT["setFolder"][self.lang])
        self.btn_update.setText(BUTTON_TEXT["update"][self.lang])
        self.btn_install.setText(BUTTON_TEXT["install"][self.lang])
        self.btn_decline.setText(BUTTON_TEXT["decline"][self.lang])


    def check_SetFolder(self):
        folder = set_user_path(parent=self)
        self.user_path = GLOBAL_CFG.get("USER_PATH")


    def resetButtons(self):
        self.btn_setFolder.show()
        self.btn_update.show()

        self.btn_decline.hide()
        self.btn_install.hide()

    def check_decline(self):
        # reset window stat
        #self.resetButtons()
        self.RefreshStatus()
        text = STATUS_TEXT["reply_decline"][self.lang]
        # Block Button
        self.btn_update.setEnabled(False) 
        self.btn_update.setStyleSheet("color: grey;")
        self.CloseButtonState(text=text)
        #QTimer.singleShot(500, lambda: self.CloseButtonState(text=text))

        return False


    def start_Update(self):
        if not self.url or not self.exe_path:
            return

        #print(f"url={self.url},\nexe_path = {self.exe_path}")

        # 1. Закрываем процесс, если он запущен
        if not ensure_process_closed(self.exe_path):
            self.status_label.setText(STATUS_TEXT["error_c"][self.lang])
            return

        self.download_thread = DownloadThread(self.url, self.exe_path)
        self.download_thread.progress.connect(self.on_progress)
        self.download_thread.finished.connect(self.download_finished)
        self.download_thread.start()


    def on_progress(self, percent):
        pre_text = STATUS_TEXT["download"][self.lang]
        self.status_label.setText(f"{pre_text}{percent:.2f}%")

    def download_finished(self, success):
        if success:
            if self.latest_tag != None:
                self.curent_version = self.latest_tag
                GLOBAL_CFG["SPT_VERSION"] = self.curent_version
                save_config(GLOBAL_CFG)

            #self.status_label.setText(text)
            text = STATUS_TEXT["succes_inst"][self.lang]
            print (f"set text = {text}")
            self.waitState(text=text, mode="now")
            QTimer.singleShot(300, self.LaunchChatSPT)
            
        else:
            self.status_label.setText(STATUS_TEXT["error_b"][self.lang])

    def RefreshStatus(self):
        self.status_label.setText("...")


    def LaunchChatSPT(self):
        print (f"start spt  = {self.exe_path}")
        subprocess.Popen([self.exe_path])
        sys.exit(0)
        #QTimer.singleShot(2000, self.RefreshStatus)

    def waitState(self, text=str, mode=None):
        # Block Button
        self.btn_update.setEnabled(False) 
        self.btn_update.setStyleSheet("color: grey;")
        if mode==None:
            self.RefreshStatus()
            QTimer.singleShot(500, lambda: self.CloseButtonState(text=text))
        elif mode=="now":
            self.CloseButtonState(text=text)

    def CloseButtonState(self, text = str):
            self.resetButtons()
            #self.exe_path = None
            self.url = None
            self.btn_update.hide()
            self.btn_close.show()
            self.status_label.setText(text)

    def check_update(self):
        if not self.user_path:
            self.status_label.setText(STATUS_TEXT["error_a"][self.lang])
            return

        self.exe_path = Path(GLOBAL_CFG.get("SPT_PATH"))
        self.curent_version = GLOBAL_CFG.get("SPT_VERSION") or PACK_SPT_VERSION
        self.latest_tag, self.url = get_latest_asset("ChatSPT.exe")
        
        #print(f"latest_tag = {self.latest_tag}")
        if self.latest_tag == "http_error_403":
            print("403")
            text = STATUS_TEXT["error_с"][self.lang]

            self.waitState(text=text)
            return

        self.need_update = self.curent_version != self.latest_tag
        # print(f"latest_tag = {self.latest_tag}, current_vers = {self.curent_version}, need_update = {self.need_update}")

        if not self.need_update:
            text = STATUS_TEXT["notUpdates"][self.lang]
            self.waitState(text=text)
            return

        if self.exe_path.name != "ChatSPT.exe":
            text="[SYS] Target Name Diffirent - Sorry"
            self.waitState(text=text)
            return

        if not self.latest_tag or not self.url:
            text = STATUS_TEXT["error_b"][self.lang]
            self.waitState(text=text)
            return
        
        if self.exe_path.exists():
            quest  = STATUS_TEXT["replace_quest"][self.lang]
            self.status_label.setText(f"{quest} {self.latest_tag}?")
            
            self.btn_setFolder.hide()
            self.btn_update.hide()
            self.btn_decline.show()
            self.btn_install.show()


# ===============================

# Запуск как ChatSPT-Updater.exe как отдельного процесса (GUI)

# Выполняем handoff до старта GUI (раз мы не в silent)
exe_path = str(Path(sys.argv[0]).resolve())
path_key = "UPD_PATH"
if try_handoff(current_exe=exe_path, path_config_key=path_key):
    sys.exit(0)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = UpdaterWindow()
    window.show()
    window.update_storage_label()
    sys.exit(app.exec())
