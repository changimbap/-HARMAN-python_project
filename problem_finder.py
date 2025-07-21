# problem_finder.py (오류 수정 버전)

import tkinter as tk
from tkinter import ttk, messagebox
import ttkbootstrap as ttk
import requests
from bs4 import BeautifulSoup
import webbrowser
import threading

def fetch_class_problems(class_num):
    """solved.ac 클래스 문제 목록을 크롤링하는 함수"""
    url = f"https://solved.ac/class/{class_num}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"}
    res = requests.get(url, headers=headers)
    res.raise_for_status()
    soup = BeautifulSoup(res.text, "html.parser")
    problems = []
    problem_table = soup.select_one("table tbody")
    if not problem_table: return []
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
        
        top_frame = ttk.Frame(self, padding=(10, 10))
        top_frame.pack(fill="x")
        ttk.Label(top_frame, text="클래스 선택:").pack(side="left", padx=(0, 5))
        self.class_var = tk.StringVar(value='1')
        self.class_menu = ttk.Combobox(top_frame, textvariable=self.class_var, values=[str(i) for i in range(1, 11)], state="readonly", width=10)
        self.class_menu.pack(side="left", padx=5)
        self.fetch_button = ttk.Button(top_frame, text="문제 불러오기", command=self.start_fetching, bootstyle="primary")
        self.fetch_button.pack(side="left", padx=5)
        
        list_frame = ttk.Frame(self, padding=(10, 0, 10, 10))
        list_frame.pack(expand=True, fill="both")
        self.problem_listbox = tk.Listbox(list_frame, font=("Malgun Gothic", 10))
        self.problem_listbox.pack(side="left", expand=True, fill="both")
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.problem_listbox.yview, bootstyle="round")
        scrollbar.pack(side="right", fill="y")
        self.problem_listbox.config(yscrollcommand=scrollbar.set)
        self.problem_listbox.bind("<Double-1>", self.open_selected_problem)
        
        bottom_frame = ttk.Frame(self, padding=(10,0,10,10))
        bottom_frame.pack(fill='x')
        self.open_button = ttk.Button(bottom_frame, text="선택한 문제 브라우저에서 열기", command=self.open_selected_problem, bootstyle="success-outline")
        self.open_button.pack(fill='x')
        self.status_label = ttk.Label(self, text="클래스를 선택하고 '문제 불러오기'를 누르세요.", padding=(10,5))
        self.status_label.pack(side="bottom", fill="x")

        self.transient(parent_window)
        self.grab_set()
        parent_window.wait_window(self)

    def start_fetching(self):
        threading.Thread(target=self.fetch_and_display, daemon=True).start()

    def fetch_and_display(self):
        # ⭐️ 모든 self.root.after를 self.after로 수정했습니다.
        self.after(0, self.fetch_button.config, {'text': "불러오는 중...", 'state': "disabled"})
        self.after(0, self.problem_listbox.delete, 0, tk.END)
        self.after(0, self.problem_listbox.insert, tk.END, f"Class {self.class_var.get()} 문제를 로딩합니다...")
        try:
            self.problems_data = fetch_class_problems(self.class_var.get())
            def update_ui_success():
                self.problem_listbox.delete(0, tk.END)
                if not self.problems_data:
                    self.status_label.config(text="⚠️ 문제 목록을 가져오지 못했습니다.")
                else:
                    for idx, (_, title) in enumerate(self.problems_data, start=1):
                        self.problem_listbox.insert(tk.END, f"{idx}. {title}")
                    self.status_label.config(text=f"✅ Class {self.class_var.get()} 문제 {len(self.problems_data)}개 로드 완료.")
            self.after(0, update_ui_success)
        except Exception as e:
            def update_ui_error():
                self.status_label.config(text=f"❌ 오류가 발생했습니다. 다시 시도해주세요.")
                messagebox.showerror("크롤링 오류", f"문제를 불러오는 중 오류가 발생했습니다:\n{e}")
            self.after(0, update_ui_error)
        finally:
            self.after(0, self.fetch_button.config, {'text': "문제 불러오기", 'state': "normal"})

    def open_selected_problem(self, event=None):
        selected_indices = self.problem_listbox.curselection()
        if not selected_indices: return
        # problems_data가 비어있을 경우를 대비한 방어 코드
        if not hasattr(self, 'problems_data') or not self.problems_data: return
        
        pid, title = self.problems_data[selected_indices[0]]
        url = f"https://www.acmicpc.net/problem/{pid}"
        self.status_label.config(text=f"🔗 {title} ({pid}) 문제를 브라우저에서 엽니다...")
        webbrowser.open(url)

def launch(parent_window):
    ProblemFinderWindow(parent_window)