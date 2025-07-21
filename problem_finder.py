# problem_finder.py (최적화 버전)

import tkinter as tk
from tkinter import ttk, messagebox
import ttkbootstrap as ttk
import requests
from bs4 import BeautifulSoup
import webbrowser
import threading

def fetch_class_problems(class_num: str) -> list[tuple[str, str]]:
    """
    solved.ac 클래스 문제 목록을 크롤링하는 함수 (lxml 파서 사용)
    """
    url = f"https://solved.ac/class/{class_num}"
    headers = {"User-Agent": "Mozilla/5.0"}
    res = requests.get(url, headers=headers)
    res.raise_for_status()
    
    # ⭐️ 1. 성능이 뛰어난 'lxml' 파서를 사용합니다.
    soup = BeautifulSoup(res.text, "lxml")
    
    problems = []
    problem_table = soup.select_one("table tbody")
    if not problem_table:
        return []
        
    for row in problem_table.find_all("tr"):
        cols = row.find_all("td")
        if len(cols) >= 2:
            problem_id = cols[0].text.strip()
            title = cols[1].text.strip()
            problems.append((problem_id, title))
    return problems

class ProblemFinderWindow(ttk.Toplevel):
    def __init__(self, parent_window):
        super().__init__(parent_window)
        self.title("백준 문제 크롤러")
        self.geometry("450x500")

        # ⭐️ 2. 한 번 불러온 결과를 저장할 캐시(cache)를 만듭니다.
        self.problems_cache = {}
        
        # --- UI 위젯 생성 ---
        top_frame = ttk.Frame(self, padding=(10, 10))
        top_frame.pack(fill="x")
        ttk.Label(top_frame, text="클래스 선택:").pack(side="left", padx=(0, 5))
        self.class_var = tk.StringVar(value='1')
        self.class_menu = ttk.Combobox(top_frame, textvariable=self.class_var, 
                                       values=[str(i) for i in range(1, 11)], 
                                       state="readonly", width=10)
        self.class_menu.pack(side="left", padx=5)
        self.fetch_button = ttk.Button(top_frame, text="문제 불러오기", 
                                       command=self.start_fetching, bootstyle="primary")
        self.fetch_button.pack(side="left", padx=5)
        
        list_frame = ttk.Frame(self, padding=(10, 0, 10, 10))
        list_frame.pack(expand=True, fill="both")
        self.problem_listbox = tk.Listbox(list_frame, font=("Malgun Gothic", 10))
        self.problem_listbox.pack(side="left", expand=True, fill="both")
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", 
                                  command=self.problem_listbox.yview, bootstyle="round")
        scrollbar.pack(side="right", fill="y")
        self.problem_listbox.config(yscrollcommand=scrollbar.set)
        self.problem_listbox.bind("<Double-1>", self.open_selected_problem)
        
        bottom_frame = ttk.Frame(self, padding=(10,0,10,10))
        bottom_frame.pack(fill='x')
        self.open_button = ttk.Button(bottom_frame, text="선택한 문제 브라우저에서 열기", 
                                      command=self.open_selected_problem, bootstyle="success-outline")
        self.open_button.pack(fill='x')
        self.status_label = ttk.Label(self, text="클래스를 선택하고 '문제 불러오기'를 누르세요.", padding=(10,5))
        self.status_label.pack(side="bottom", fill="x")

        self.transient(parent_window)
        self.grab_set()
        parent_window.wait_window(self)

    def start_fetching(self):
        """UI가 멈추지 않도록 별도의 스레드에서 크롤링 함수를 실행"""
        threading.Thread(target=self.fetch_and_display, daemon=True).start()

    def fetch_and_display(self):
        """백그라운드에서 실행될 크롤링 및 UI 업데이트 로직"""
        class_num = self.class_var.get()
        
        # UI 업데이트는 after를 통해 메인 스레드에서 안전하게 실행
        self.after(0, self.ui_before_fetch, class_num)
        
        try:
            # ⭐️ 2. 캐시에 결과가 있는지 먼저 확인합니다.
            if class_num in self.problems_cache:
                problems = self.problems_cache[class_num]
                self.after(0, lambda: self.ui_update_success(class_num, problems))
                return # 캐시된 결과를 사용했으므로 여기서 함수 종료

            # 캐시에 없다면 네트워크에서 데이터를 가져옵니다.
            problems = fetch_class_problems(class_num)
            
            # 가져온 결과를 캐시에 저장합니다.
            self.problems_cache[class_num] = problems
            
            # 가져온 결과로 UI를 업데이트합니다.
            self.after(0, lambda: self.ui_update_success(class_num, problems))

        except Exception as e:
            self.after(0, self.ui_update_error, e)

    def open_selected_problem(self, event=None):
        """리스트박스에서 선택된 문제를 웹 브라우저에서 연다"""
        selected_indices = self.problem_listbox.curselection()
        if not selected_indices:
            messagebox.showwarning("경고", "먼저 목록에서 문제를 선택하세요.", parent=self)
            return
        
        selected_index = selected_indices[0]
        if not self.problems_data: return

        pid, title = self.problems_data[selected_index]
        url = f"https://www.acmicpc.net/problem/{pid}"
        
        self.status_label.config(text=f"🔗 {title} ({pid}) 문제를 브라우저에서 엽니다...")
        webbrowser.open(url)
        
    # ⭐️ 3. UI 업데이트 로직을 별도 메소드로 분리하여 코드 구조 개선
    def ui_before_fetch(self, class_num):
        """데이터를 불러오기 전의 UI 상태 설정"""
        self.fetch_button.config(text="불러오는 중...", state="disabled")
        self.problem_listbox.delete(0, tk.END)
        self.problem_listbox.insert(tk.END, f"Class {class_num} 문제를 로딩합니다...")

    def ui_update_success(self, class_num, problems):
        """데이터 로딩 성공 시 UI 업데이트"""
        self.problems_data = problems
        self.problem_listbox.delete(0, tk.END)
        if not self.problems_data:
            self.status_label.config(text="⚠️ 문제 목록을 가져오지 못했습니다.")
        else:
            for idx, (_, title) in enumerate(self.problems_data, start=1):
                self.problem_listbox.insert(tk.END, f"{idx}. {title}")
            self.status_label.config(text=f"✅ Class {class_num} 문제 {len(self.problems_data)}개 로드 완료.")
        self.fetch_button.config(text="문제 불러오기", state="normal")
        
    def ui_update_error(self, error):
        """데이터 로딩 실패 시 UI 업데이트"""
        self.status_label.config(text=f"❌ 오류가 발생했습니다. 다시 시도해주세요.")
        messagebox.showerror("크롤링 오류", f"문제를 불러오는 중 오류가 발생했습니다:\n{error}", parent=self)
        self.fetch_button.config(text="문제 불러오기", state="normal")

def launch(parent_window):
    """메인 앱에서 이 함수를 호출하여 크롤러 창을 실행합니다."""
    ProblemFinderWindow(parent_window)