# Github Auto Uploader!

# ---- 없는 패키지 설치 ----
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
install_if_missing("ttkbootstrap")
install_if_missing("watchdog")
install_if_missing("requests")
install_if_missing("keyring")

# ---- 필요한 모듈 import ----
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
import keyring # keyring을 사용해 OS 보안 저장소에 토큰을 저장
import problem_finder # 백준 문제 불러오기(problem_finder) 모듈 import


# 1. 개인 설정 관리(github 토큰, 사용자명, repo, etc...)

application_path = os.path.dirname(os.path.abspath(__file__)) # 현재 파일의 절대 경로
CONFIG_FILE = os.path.join(application_path, "config.json")

def save_settings(settings):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=4)
        return True
    except Exception as e:
        dialogs.Messagebox.show_error(f"설정을 저장하는 데 실패했습니다: {e}", title="저장 오류")
        return False

def load_settings():
    # default setting 정의 해주기
    # 기본 브랜치(branch)를 main으로 설정 : GitHub의 기본 브랜치 main으로 쓰기 때문
    default_settings = {"token": "", "username": "", "repo": "", "folder": "", "theme": "litera", "branch": "main"}
    if not os.path.exists(CONFIG_FILE):
        return default_settings
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            settings = json.load(f)
            if "theme" not in settings: settings["theme"] = "litera"
            if "branch" not in settings: settings["branch"] = "main"
            return settings
    except (json.JSONDecodeError, FileNotFoundError):
        return default_settings


# 2. Github API 로직

api_session = requests.Session()
def get_github_repo_file_list(settings, log_queue):
    # Git Trees API를 사용하여 저장소의 모든 파일 목록을 재귀적으로 가져온다
    branch = settings.get("branch", "main")
    api_url = f"https://api.github.com/repos/{settings['username']}/{settings['repo']}/git/trees/{branch}?recursive=1"
    headers = {"Authorization": f"token {settings['token']}"}
    try:
        response = api_session.get(api_url, headers=headers)
        response.raise_for_status()
        data = response.json()
        
        # '_recycle_bin/'으로 시작하는 경로는 목록에서 제외(휴지통 폴더여서 지워지지않게)
        return {item['path'] for item in data['tree'] 
                if item['type'] == 'blob' and not item['path'].startswith('_recycle_bin/')}
    
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            log_queue.put("ℹ️ 깃허브 저장소 또는 브랜치를 찾을 수 없습니다. (빈 저장소일 수 있음)")
            return set() # 빈 저장소 일 경우 동기화가 안되는 문제
        else:
            log_queue.put(f"❌ 깃허브 파일 목록 조회 실패 (HTTP 오류): {e}")
            return None
    except Exception as e:
        log_queue.put(f"❌ 깃허브 파일 목록 조회 실패 (일반 오류): {e}")
        return None
    
# 3. Github 업로드 로직   

# 3-(1) 파일 업로드 함수
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
    sha = None # sha : 파일의 고유 식별자 (GitHub)
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

# 3-(2) 파일 삭제 함수
def move_file_to_recycle_bin(repo_path, settings, log_queue):
    # 지정된 경로의 파일을 깃허브의 _recycle_bin 폴더로 이동
    log_queue.put(f"- 처리 대상 (휴지통 이동): {os.path.basename(repo_path)}")
    
    get_url = f"https://api.github.com/repos/{settings['username']}/{settings['repo']}/contents/{repo_path}"
    headers = {"Authorization": f"token {settings['token']}"}
    
    original_content_encoded = None
    original_sha = None
    try:
        response_get = requests.get(get_url, headers=headers)
        if response_get.status_code == 200:
            data = response_get.json()

            if isinstance(data, list):
                log_queue.put(f"  ℹ️ '{repo_path}'는 폴더이므로 건너뜁니다.")
                return

            original_sha = data.get('sha')
            original_content_encoded = data.get('content')
        else:
            log_queue.put(f"  ℹ️ '{repo_path}' 파일이 깃허브에 없어 처리를 건너뜁니다.")
            return
    except Exception as e:
        log_queue.put(f"  ❌ 원본 파일 정보 조회 중 오류: {e}")
        return

    # 3-(2.1). 휴지통에 저장할 새 경로와 파일명을 만들기
    timestamp = time.strftime("%Y%m%d%H%M%S")
    original_filename = os.path.basename(repo_path)
    name, ext = os.path.splitext(original_filename)
    new_filename = f"{name}_{timestamp}{ext}"
    recycle_bin_path = f"_recycle_bin/{new_filename}"
    
    # 3-(2.2). 휴지통 경로에 새 파일을 생성
    put_url = f"https://api.github.com/repos/{settings['username']}/{settings['repo']}/contents/{recycle_bin_path}"
    put_data = {
        "message": f"Recycle: Move {repo_path}",
        "content": original_content_encoded
    }
    log_queue.put(f"  ➡️ '{recycle_bin_path}' 경로로 파일을 이동합니다...")
    try:
        response_put = requests.put(put_url, headers=headers, data=json.dumps(put_data))
        if response_put.status_code not in [200, 201]:
             log_queue.put(f"  ❌ 휴지통에 파일 생성 실패! (코드: {response_put.status_code})")
             return
    except Exception as e:
        log_queue.put(f"  ❌ 네트워크 오류 (휴지통 생성 중): {e}")
        return

    # 3-(2.3). 휴지통으로 복사가 성공했을 때만 원본 파일을 삭제
    del_url = get_url
    del_data = {"message": f"Sync: Delete {repo_path} (moved to recycle bin)", "sha": original_sha}
    try:
        response_del = requests.delete(del_url, headers=headers, data=json.dumps(del_data))
        if response_del.status_code == 200:
            log_queue.put(f"  ✅ '{os.path.basename(repo_path)}' 휴지통으로 이동 완료!")
        else:
            log_queue.put(f"  ❌ 원본 파일 삭제 실패! (코드: {response_del.status_code})")
    except Exception as e:
        log_queue.put(f"  ❌ 네트워크 오류 (원본 삭제 중): {e}")

# 4. 컴퓨터 폴더 실시간 감시 로직

class MyEventHandler(FileSystemEventHandler):
    def __init__(self, settings, log_queue):
        super().__init__()
        self.settings = settings
        self.log_queue = log_queue
        # 모든 변경 이벤트를 담을 '장바구니'와 타이머
        self.pending_changes = set()
        self.batch_timer = None

    def on_created(self, event):
        if not event.is_directory:
            self._add_to_batch(event.src_path)

    def on_modified(self, event):
        if not event.is_directory:
            self._add_to_batch(event.src_path)
    
    def _add_to_batch(self, path):
        # 파일 경로를 일괄 처리 목록에 추가하고 타이머를 (재)시작
        self.pending_changes.add(path)
        
        if self.batch_timer:
            self.batch_timer.cancel()
            
        # 1.5초 후에 일괄 처리 함수를 실행합니다.
        self.batch_timer = threading.Timer(1.5, self.process_changes_batch)
        self.batch_timer.start()

    def process_changes_batch(self):
        # 잠시 동안 모인 모든 변경 이벤트를 한꺼번에 처리
        if not self.pending_changes:
            return
            
        files_to_process = list(self.pending_changes)
        self.pending_changes.clear()
        
        file_count = len(files_to_process)
        
        # 파일 개수에 따라 다르게 처리
        if file_count == 1:
            # 파일이 하나일 경우: 개별 파일로 처리
            file_path = files_to_process[0]
            self.log_queue.put(("notification", os.path.basename(file_path)))
            repo_file_path = os.path.relpath(file_path, self.settings['folder']).replace("\\", "/")
            upload_file_to_github(file_path, repo_file_path, self.settings, self.log_queue)
        else:
            # 파일이 여러 개일 경우: 일괄 작업으로 처리
            self.log_queue.put(("folder_detected", f"{file_count}개 파일의 일괄 작업", files_to_process))

    def on_deleted(self, event):
        # 삭제는 즉시 처리
        if not event.is_directory:
            repo_file_path = os.path.relpath(event.src_path, self.settings['folder']).replace("\\", "/")
            move_file_to_recycle_bin(repo_file_path, self.settings, self.log_queue)


# 5. 초기 동기화 및 감시 시작 로직

def initial_sync_and_start_monitoring(settings, log_queue, stop_event):
    log_queue.put("🔄 초기 동기화를 시작합니다...")

    remote_files = get_github_repo_file_list(settings, log_queue) # 깃허브 저장소의 파일 목록 확인
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
    for root, _, files in os.walk(watch_folder): # os.walk : 내 컴퓨터 폴더의 목록 확인
        for filename in files:
            local_path = os.path.join(root, filename)
            repo_path = os.path.relpath(local_path, watch_folder).replace("\\", "/")
            local_files.add(repo_path)
    files_to_delete = remote_files - local_files
    files_to_upload = local_files - remote_files

    if not files_to_delete and not files_to_upload:
        log_queue.put("✅ 로컬과 깃허브 저장소가 이미 동기화 상태입니다.")
    else:
        total_tasks = len(files_to_delete) + len(files_to_upload)
        current_task = 0
        
        for repo_path in files_to_delete:
            move_file_to_recycle_bin(repo_path, settings, log_queue)
        for repo_path in files_to_upload:
            local_path = os.path.join(settings['folder'], repo_path.replace("/", os.sep))
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

# 6. 기본 UI 로직

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Github 업로드 딸깍!.made by 딸깍눌러조")
        self.root.geometry("600x480")

        self.settings = load_settings()

        # 6-(1). 사용할 기본 폰트와 버튼 폰트를 미리 정의
        # (폰트 이름, 크기, 스타일) 순서
        default_font = ("Malgun Gothic", 10)
        button_font = ("Malgun Gothic", 12, "bold")

        # 6-(2). ttkbootstrap의 스타일 설정을 가져와 폰트를 적용합니다.
        style = ttk.Style()
        style.configure('.', font=default_font) # '.'은 모든 위젯의 기본 스타일
        style.configure('TButton', font=button_font) # 'TButton'은 모든 버튼 스타일
        style.configure('TLabelframe.Label', font=default_font) # 그룹박스 제목 스타일
        self.log_queue = queue.Queue()
        self.stop_event = threading.Event()
        
        header_frame = ttk.Frame(root, padding=(10, 10, 10, 0))
        header_frame.pack(fill="x")

        # 6-(3) 현재 설정 정보 표시 라벨 
        info_text = f"사용자: {self.settings.get('username')} | 저장소: {self.settings.get('repo')}" if self.settings.get('username') else "⚙️ '설정'에서 사용자 정보를 먼저 입력해주세요."
        self.info_label = ttk.Label(header_frame, text=info_text, bootstyle="secondary")
        self.info_label.grid(row=1, column=0, columnspan=3, sticky='w', pady=(5,0))

        # 6-(4) 프로그램 제목과 버튼들
        title_font = ("Malgun Gothic", 16, "bold")
        title_label = ttk.Label(header_frame, text="✨Github 업로드 딸깍!✨", font=title_font)
        title_label.grid(row=0, column=0, sticky="w") # 0번 줄의 왼쪽에 배치

        header_frame.grid_columnconfigure(0, weight=1) # weight : 가중치(얼마나 늘어날지)

        btn_settings = ttk.Button(header_frame, text="⚙️ 설정", command=self.open_settings_window)
        btn_settings.grid(row=0, column=1, sticky="e", ipady=8, padx=5)
        btn_exit = ttk.Button(header_frame, text="🚪 종료", command=self.on_closing, bootstyle="secondary")
        btn_exit.grid(row=0, column=2, sticky="e", ipady=8)
        # sticky : 위젯이 차지하는 공간의 위치를 지정 (n, s, e, w : 북, 남, 동, 서)
        # ipady : 위젯의 내부 여백(수직) 크기 조정
        # padx : 위젯의 외부 여백(수평) 크기 조정

        control_frame = ttk.Frame(root, padding=(10, 10))
        control_frame.pack(fill="x")
        control_frame.grid_columnconfigure((0, 1, 2), weight=1)
        self.btn_start = ttk.Button(control_frame, text="▶️ 동기화&업로드 시작", command=self.start_action, bootstyle="success")
        self.btn_start.grid(row=0, column=0, sticky="ew", padx=(0, 5), ipady=10)
        self.btn_stop = ttk.Button(control_frame, text="⏹️ 업로드 종료", state="disabled", command=self.stop_action, bootstyle="danger")
        self.btn_stop.grid(row=0, column=1, sticky="ew", padx=(5, 5), ipady=10)
        self.btn_problem = ttk.Button(control_frame, text="✏️ 백준 문제 찾기", command=self.open_problem_finder_window, bootstyle="info")
        self.btn_problem.grid(row=0, column=2, sticky="ew", padx=(5, 0), ipady=10)

        # 6-(5) 실시간 로그 출력 영역
        log_frame = ttk.Labelframe(root, text="실시간 진행상황", padding=(10, 5))
        log_frame.pack(expand=True, fill="both", padx=10, pady=(0, 10))
        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, state="disabled", font=("Malgun Gothic", 9))
        self.log_text.pack(expand=True, fill="both")
        
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.check_log_queue()

    # 6-(6) 메인 화면의 설정 정보 라벨을 업데이트하는 함수
    def update_info_label(self):
        info_text = f"사용자: {self.settings.get('username')} | 저장소: {self.settings.get('repo')}" if self.settings.get('username') else "⚙️ '설정'에서 사용자 정보를 먼저 입력해주세요."
        self.info_label.config(text=info_text)

# 7. 설정 창 UI  
    def open_settings_window(self):
        settings_win = ttk.Toplevel(self.root)
        settings_win.title("설정")
        settings_win.geometry("500x300")
        settings_win.transient(self.root)
        settings_win.grab_set()
        frame = ttk.Frame(settings_win, padding=(15, 15))
        frame.pack(expand=True, fill="both")
        frame.grid_columnconfigure(1, weight=1)
        fields = ["GitHub 토큰🔒:", "사용자 이름:", "Repositories 이름:", "감시할 폴더:"]
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

        # 7-(1) 저장 버튼 / Keyring을 사용해 토큰을 OS 보안 저장소에 저장✨
        def save_and_close():
            new_settings = {key: entries[key].get() for key in keys}
            new_settings["theme"] = theme_combo.get()
            try:
                # 1. Keyring을 사용해 토큰을 OS 보안 저장소에 저장
                # "서비스 이름", "계정(사용자 이름)", "비밀번호(토큰)" 형태로 저장됩니다.
                keyring.set_password("github_auto_uploader", new_settings["username"], new_settings["token"])
                
                # 2. config.json 파일에 저장할 설정에서는 토큰을 제거
                settings_for_file = new_settings.copy()
                settings_for_file["token"] = "" # 파일에는 빈 값이나 표시용 텍스트 저장

                # 3. 토큰이 제거된 설정만 파일에 저장 / 저장 후 메인 화면 정보 라벨 업데이트
                if save_settings(settings_for_file):
                    self.settings = new_settings
                    self.update_info_label()
                    dialogs.Messagebox.show_info("설정이 저장되었습니다.\n(토큰은 안전하게 별도 보관됩니다)", title="저장 완료", parent=settings_win)
                    settings_win.destroy()

            except Exception as e:
                dialogs.Messagebox.show_error(f"토큰 저장 중 오류 발생:\n{e}", title="오류", parent=settings_win)

        btn_save = ttk.Button(settings_win, text="저장하고 닫기", command=save_and_close, bootstyle="primary")
        btn_save.pack(pady=(0, 15), ipadx=10)
    
    
# 8. 시작 버튼 클릭 시 실행되는 함수
    def start_action(self):
        if not all(self.settings.get(key) for key in ["username", "repo", "folder"]):
            dialogs.Messagebox.show_error("'⚙️ 설정'에서 사용자 이름, 저장소, 폴더를 먼저 입력해주세요.", "오류")
            return
        # 1. Keyring에서 사용자 이름을 기준으로 토큰을 불러오기
        try:
            token = keyring.get_password("github_auto_uploader", self.settings["username"])
            if not token:
                dialogs.Messagebox.show_error("토큰을 찾을 수 없습니다.\n'⚙️ 설정'에서 토큰을 다시 입력하고 저장해주세요.", "토큰 오류")
                return
        except Exception as e:
            dialogs.Messagebox.show_error(f"토큰을 불러오는 중 오류 발생:\n{e}", "오류")
            return
            
        # 2. 현재 작업에 사용할 설정 객체 만들기 (불러온 토큰 포함)
        active_settings = self.settings.copy()
        active_settings["token"] = token

        # 3. UI 상태를 업데이트
        self.log_text.config(state="normal"); self.log_text.delete(1.0, tk.END); self.log_text.config(state="disabled")
        self.btn_start.config(state="disabled"); self.btn_stop.config(state="normal")
        self.stop_event.clear()

        # 4. 백그라운드 작업에 토큰이 포함된 'active_settings'를 전달
        threading.Thread(target=initial_sync_and_start_monitoring, args=(active_settings, self.log_queue, self.stop_event), daemon=True).start()

    def stop_action(self):
        self.stop_event.set()
        self.reset_ui_to_idle()
    
    def reset_ui_to_idle(self):
        self.btn_start.config(state="normal"); self.btn_stop.config(state="disabled")

    def _upload_files_in_thread(self, files_to_upload):
        for file_path in files_to_upload:
            # 만약 감시가 중단되면 루프를 멈춥니다.
            if self.stop_event.is_set():
                self.log_queue.put("폴더 업로드 중단됨.")
                break
            repo_path = os.path.relpath(file_path, self.settings['folder']).replace("\\", "/")
            upload_file_to_github(file_path, repo_path, self.settings, self.log_queue)

# 9. 실시간 로그 처리 함수
    def check_log_queue(self):
        while not self.log_queue.empty():
            message = self.log_queue.get_nowait()

            if isinstance(message, tuple) and message[0] == "folder_detected":
                folder_path, files_to_upload = message[1], message[2]
                folder_name = os.path.basename(folder_path)
                file_count = len(files_to_upload)
                
                # 사용자에게 확인 팝업을 띄웁니다.
                dialogs.Messagebox.show_info(
                    f"'{folder_name}' 폴더({file_count}개 파일)가 감지되었습니다.\n'확인'을 누르면 전체 업로드를 시작합니다.",
                    title="폴더 감지"
                )
                
                # 확인 후, 별도 스레드에서 업로드를 시작합니다.
                threading.Thread(target=self._upload_files_in_thread, args=(files_to_upload,), daemon=True).start()
                continue # 다음 메시지 처리

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

# 10. 백준 문제 찾기 버튼 클릭 시 실행되는 함수
    def open_problem_finder_window(self):
        problem_finder.launch(self.root)

# 11. 프로그램 종료 확인 박스
    def on_closing(self):
        if dialogs.Messagebox.show_question("프로그램을 종료하시겠습니까?", "종료 확인") == "Yes":
            self.stop_event.set()
            self.root.after(200, self.root.destroy)


# 12. 애플리케이션 실행
if __name__ == "__main__":
    settings = load_settings()
    root = ttk.Window(themename=settings.get("theme", "litera"))
    app = App(root)
    root.mainloop()