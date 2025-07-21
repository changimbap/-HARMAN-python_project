# my_app.py (모듈화 적용 버전)
import subprocess
import sys

def install_if_missing(package_name, import_name=None):
    import_name = import_name or package_name
    try:
        __import__(import_name)
    except ImportError:
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", package_name])
        except Exception as e:
            import tkinter.messagebox as msg
            msg.showerror("패키지 설치 오류", f"'{package_name}' 설치에 실패했습니다.\n{e}")
            sys.exit(1)


import ttkbootstrap as ttk
from ttkbootstrap.dialogs import dialogs
import tkinter as tk
from tkinter import filedialog, scrolledtext
import threading
import time
import requests
import base64
import os
import json
import queue
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import webbrowser
import problem_finder # ⭐️ 1. 우리가 만든 크롤러 모듈을 import 합니다.

# --- 설정 관리 기능 ---
CONFIG_FILE = "config.json"

def save_settings(settings):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=4)
        return True
    except Exception as e:
        dialogs.Messagebox.show_error(f"설정을 저장하는 데 실패했습니다: {e}", title="저장 오류")
        return False

def load_settings():
    default_settings = {"token": "", "username": "", "repo": "", "folder": "", "theme": "litera"}
    if not os.path.exists(CONFIG_FILE):
        return default_settings
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            settings = json.load(f)
            if "theme" not in settings:
                settings["theme"] = "litera"
            return settings
    except (json.JSONDecodeError, FileNotFoundError):
        return default_settings

# --- 깃허브 API 로직 ---
def get_github_repo_file_list(settings, log_queue):
    api_url = f"https://api.github.com/repos/{settings['username']}/{settings['repo']}/git/trees/main?recursive=1"
    headers = {"Authorization": f"token {settings['token']}"}
    try:
        response = requests.get(api_url, headers=headers)
        response.raise_for_status()
        data = response.json()
        return {item['path'] for item in data['tree'] if item['type'] == 'blob'}
    except Exception as e:
        log_queue.put(f"❌ 깃허브 파일 목록 조회 실패: {e}")
        return None
    
def upload_file_to_github(local_path, repo_path, settings, log_queue):
    log_queue.put(f"- 처리 대상 (추가/수정): {os.path.basename(local_path)}")
    url = f"https://api.github.com/repos/{settings['username']}/{settings['repo']}/contents/{repo_path}"
    headers = {"Authorization": f"token {settings['token']}"}
    try:
        with open(local_path, "rb") as file:
            content_encoded = base64.b64encode(file.read()).decode('utf-8')
    except (FileNotFoundError, PermissionError) as e:
        log_queue.put(f"   ❌ 파일 읽기 오류: {e}")
        return
    sha = None
    try:
        response_get = requests.get(url, headers=headers)
        if response_get.status_code == 200: sha = response_get.json().get('sha')
    except: pass
    data = {"message": f"Sync: Update {repo_path}", "content": content_encoded}
    if sha: data["sha"] = sha
    log_queue.put(f"   🚀 '{repo_path}' 경로로 업로드를 시도합니다...")
    try:
        response_put = requests.put(url, headers=headers, data=json.dumps(data))
        if response_put.status_code in [200, 201]:
            log_queue.put(f"   ✅ '{os.path.basename(local_path)}' 업로드 성공!")
        else:
            log_queue.put(f"   ❌ 업로드 실패! (코드: {response_put.status_code})")
    except Exception as e:
        log_queue.put(f"   ❌ 네트워크 오류 (업로드 중): {e}")

def delete_file_from_github(repo_path, settings, log_queue):
    log_queue.put(f"- 처리 대상 (삭제): {os.path.basename(repo_path)}")
    url = f"https://api.github.com/repos/{settings['username']}/{settings['repo']}/contents/{repo_path}"
    headers = {"Authorization": f"token {settings['token']}"}
    sha = None
    try:
        response_get = requests.get(url, headers=headers)
        if response_get.status_code == 200:
            sha = response_get.json().get('sha')
        else:
            log_queue.put(f"   ℹ️ '{repo_path}' 파일이 깃허브에 없어 삭제를 건너뜁니다.")
            return
    except Exception as e:
        log_queue.put(f"   ❌ 파일 정보 조회 중 오류: {e}")
        return
    data = {"message": f"Sync: Delete {repo_path}", "sha": sha}
    log_queue.put(f"   🗑️ '{repo_path}' 경로의 파일 삭제를 시도합니다...")
    try:
        response_del = requests.delete(url, headers=headers, data=json.dumps(data))
        if response_del.status_code == 200:
            log_queue.put(f"   ✅ '{os.path.basename(repo_path)}' 삭제 성공!")
        else:
            log_queue.put(f"   ❌ 삭제 실패! (코드: {response_del.status_code})")
    except Exception as e:
        log_queue.put(f"   ❌ 네트워크 오류 (삭제 중): {e}")

# --- 감시 로직 ---
class MyEventHandler(FileSystemEventHandler):
    def __init__(self, settings, log_queue):
        super().__init__()
        self.settings = settings
        self.log_queue = log_queue
        self.last_processed_time = {}
    def _should_process(self, path):
        now = time.time()
        if now - self.last_processed_time.get(path, 0) < 2: return False
        self.last_processed_time[path] = now
        return True
    def on_created(self, event):
        if not event.is_directory and self._should_process(event.src_path):
            time.sleep(1)
            file_name = os.path.basename(event.src_path)
            self.log_queue.put(("notification", file_name))
            repo_file_path = os.path.relpath(event.src_path, self.settings['folder']).replace("\\", "/")
            upload_file_to_github(event.src_path, repo_file_path, self.settings, self.log_queue)
    def on_modified(self, event):
        if not event.is_directory and self._should_process(event.src_path):
            time.sleep(1)
            repo_file_path = os.path.relpath(event.src_path, self.settings['folder']).replace("\\", "/")
            upload_file_to_github(event.src_path, repo_file_path, self.settings, self.log_queue)
    def on_deleted(self, event):
        if not event.is_directory and self._should_process(event.src_path):
            repo_file_path = os.path.relpath(event.src_path, self.settings['folder']).replace("\\", "/")
            delete_file_from_github(repo_file_path, self.settings, self.log_queue)

def initial_sync_and_start_monitoring(settings, log_queue, stop_event):
    log_queue.put("🔄 초기 동기화를 시작합니다...")
    remote_files = get_github_repo_file_list(settings, log_queue)
    if remote_files is None:
        log_queue.put("초기 동기화 실패. 감시를 시작하지 않습니다.")
        log_queue.put("STOP_MONITORING_UI")
        return
    watch_folder = settings['folder']
    if not os.path.isdir(watch_folder):
        log_queue.put(f"오류: '{watch_folder}'는 유효한 폴더가 아닙니다.")
        log_queue.put("STOP_MONITORING_UI")
        return
    local_files = set()
    for root, _, files in os.walk(watch_folder):
        for filename in files:
            local_path = os.path.join(root, filename)
            repo_path = os.path.relpath(local_path, watch_folder).replace("\\", "/")
            local_files.add(repo_path)
    files_to_delete = remote_files - local_files
    files_to_upload = local_files - remote_files
    if not files_to_delete and not files_to_upload:
        log_queue.put("✅ 로컬과 깃허브 저장소가 이미 동기화 상태입니다.")
    else:
        for repo_path in files_to_delete:
            delete_file_from_github(repo_path, settings, log_queue)
        for repo_path in files_to_upload:
            local_path = os.path.join(watch_folder, repo_path.replace("/", os.sep))
            upload_file_to_github(local_path, repo_path, settings, log_queue)
    if stop_event.is_set():
        log_queue.put("⏹️ 동기화 중단됨. 감시를 시작하지 않습니다.")
        return
    log_queue.put("✅ 초기 동기화 완료.")
    log_queue.put(f"📂 폴더 실시간 감시를 시작합니다: {watch_folder}")
    observer = Observer()
    observer.schedule(MyEventHandler(settings, log_queue), watch_folder, recursive=True)
    observer.start()
    stop_event.wait()
    observer.stop()
    observer.join()
    log_queue.put("⏹️ 감시가 중단되었습니다.")

# --- UI 로직 ---
class App:
    def __init__(self, root):
        self.root = root
        self.root.title("자동 업로드 프로그램")
        self.root.geometry("600x480")
        self.settings = load_settings()
        self.log_queue = queue.Queue()
        self.stop_event = threading.Event()

        header_frame = ttk.Frame(root, padding=(10, 10, 10, 0))
        header_frame.pack(fill="x")
        header_frame.grid_columnconfigure(0, weight=1)
        btn_settings = ttk.Button(header_frame, text="⚙️ 설정", command=self.open_settings_window)
        btn_settings.grid(row=0, column=1, sticky="e", ipady=8, padx=5)
        btn_exit = ttk.Button(header_frame, text="🚪 종료", command=self.on_closing, bootstyle="secondary")
        btn_exit.grid(row=0, column=2, sticky="e", ipady=8)

        control_frame = ttk.Frame(root, padding=(10, 10))
        control_frame.pack(fill="x")
        control_frame.grid_columnconfigure((0, 1, 2), weight=1)
        self.btn_start = ttk.Button(control_frame, text="감시 시작", command=self.start_action, bootstyle="success")
        self.btn_start.grid(row=0, column=0, sticky="ew", padx=(0, 5), ipady=10)
        self.btn_stop = ttk.Button(control_frame, text="감시 종료", state="disabled", command=self.stop_action, bootstyle="danger")
        self.btn_stop.grid(row=0, column=1, sticky="ew", padx=(5, 5), ipady=10)
        self.btn_problem = ttk.Button(control_frame, text="백준 문제 찾기", command=self.open_problem_finder_window, bootstyle="info")
        self.btn_problem.grid(row=0, column=2, sticky="ew", padx=(5, 0), ipady=10)

        log_frame = ttk.Labelframe(root, text="실시간 로그", padding=(10, 5))
        log_frame.pack(expand=True, fill="both", padx=10, pady=(0, 10))
        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, state="disabled", font=("Malgun Gothic", 9))
        self.log_text.pack(expand=True, fill="both")
        
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.check_log_queue()

    def open_settings_window(self):
        settings_win = ttk.Toplevel(self.root)
        settings_win.title("설정")
        settings_win.geometry("500x300")
        settings_win.transient(self.root)
        settings_win.grab_set()
        frame = ttk.Frame(settings_win, padding=(15, 15))
        frame.pack(expand=True, fill="both")
        frame.grid_columnconfigure(1, weight=1)
        fields = ["GitHub 토큰:", "사용자 이름:", "저장소 이름:", "감시할 폴더:"]
        entries = {}
        keys = ["token", "username", "repo", "folder"]
        for i, (label_text, key) in enumerate(zip(fields, keys)):
            label = ttk.Label(frame, text=label_text)
            label.grid(row=i, column=0, sticky="w", pady=5)
            entry = ttk.Entry(frame, show="*" if key == "token" else "")
            entry.grid(row=i, column=1, columnspan=2, sticky="ew", padx=(10, 0))
            entry.insert(0, self.settings.get(key, ""))
            entries[key] = entry
        def select_folder_path():
            folder_selected = filedialog.askdirectory()
            if folder_selected:
                entries["folder"].delete(0, tk.END)
                entries["folder"].insert(0, folder_selected)
        btn_select = ttk.Button(frame, text="폴더 선택", command=select_folder_path, bootstyle="outline")
        btn_select.grid(row=3, column=3, padx=(5,0))
        theme_label = ttk.Label(frame, text="테마 선택:")
        theme_label.grid(row=4, column=0, sticky="w", pady=15)
        theme_names = self.root.style.theme_names()
        theme_combo = ttk.Combobox(frame, values=theme_names, state="readonly")
        theme_combo.grid(row=4, column=1, columnspan=2, sticky="ew", padx=(10, 0))
        theme_combo.set(self.settings.get("theme", "litera"))
        def save_and_close():
            new_settings = {key: entries[key].get() for key in keys}
            new_settings["theme"] = theme_combo.get()
            if save_settings(new_settings):
                self.settings = new_settings
                dialogs.Messagebox.show_info("설정이 저장되었습니다.\n테마 변경은 프로그램을 재시작해야 적용됩니다.", title="저장 완료", parent=settings_win)
                settings_win.destroy()
        btn_save = ttk.Button(settings_win, text="저장하고 닫기", command=save_and_close, bootstyle="primary")
        btn_save.pack(pady=(0, 15), ipadx=10)
    
    # ⭐️ 2. 백준 문제 찾기 관련 로직을 모듈 호출로 변경합니다.
    def open_problem_finder_window(self):
        problem_finder.launch(self.root)

    def start_action(self):
        if not all(self.settings.get(key) for key in ["token", "username", "repo", "folder"]):
            dialogs.Messagebox.show_error("'⚙️ 설정'에서 모든 정보를 입력해야 합니다.", "오류")
            return
        self.log_text.config(state="normal"); self.log_text.delete(1.0, tk.END); self.log_text.config(state="disabled")
        self.btn_start.config(state="disabled"); self.btn_stop.config(state="normal")
        self.stop_event.clear()
        threading.Thread(target=initial_sync_and_start_monitoring, args=(self.settings, self.log_queue, self.stop_event), daemon=True).start()

    def stop_action(self):
        self.stop_event.set()
        self.reset_ui_to_idle()
    
    def reset_ui_to_idle(self):
        self.btn_start.config(state="normal"); self.btn_stop.config(state="disabled")

    def on_closing(self):
        if dialogs.Messagebox.show_question("프로그램을 종료하시겠습니까?", "종료 확인") == "Yes":
            self.stop_event.set()
            self.root.after(200, self.root.destroy)

    def check_log_queue(self):
        while not self.log_queue.empty():
            message = self.log_queue.get_nowait()
            if isinstance(message, tuple) and message[0] == "notification":
                dialogs.Messagebox.show_info(f"새로운 파일이 생성되었습니다: {message[1]}", "파일 생성 감지")
                continue
            if message == "STOP_MONITORING_UI":
                self.reset_ui_to_idle()
                continue
            self.log_text.config(state="normal")
            self.log_text.insert(tk.END, str(message) + "\n")
            self.log_text.see(tk.END)
            self.log_text.config(state="disabled")
        self.root.after(100, self.check_log_queue)

# --- 애플리케이션 실행 ---
if __name__ == "__main__":
    settings = load_settings()
    root = ttk.Window(themename=settings.get("theme", "litera"))
    app = App(root)
    root.mainloop()