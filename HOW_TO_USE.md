# ✨ Github 업로드 딸깍! 사용방법 ✨

---

## 1️⃣ 프로그램 실행

<img width="1040" height="640" alt="image" src="https://github.com/user-attachments/assets/a28eeeae-b136-4c88-9a62-dced4513f160" />

1.  위 3개의 파일(`my_app.py`, `problem_finder.py`, `requirements.txt`)을 **같은 폴더**에 다운로드합니다.
2.  `github_auto_upload.py` (또는 `my_app.py`) 파일을 실행합니다.

<br>

---

## 2️⃣ 개인 Github 계정 확인

### (1) 토큰 발급 🌟

1.  깃허브 로그인 → 오른쪽 상단 프로필 → **Settings** → 왼쪽 메뉴 맨 아래 **Developer settings** → **Personal access tokens** → **Tokens (classic)** → **Generate new token**
    <br>
    <img width="1040" height="640" alt="image" src="https://github.com/user-attachments/assets/82a57f71-b064-4849-9692-df27a8db0626" />

2.  **`repo`**, **`workflow`**, **`user`** 스코프(scope)를 체크한 뒤 **Generate token** 버튼을 클릭합니다.
    <br>
    <img width="640" height="640" alt="image" src="https://github.com/user-attachments/assets/f7c6cd49-4f8f-497a-9640-102343b4e254" />

3.  발급된 토큰을 복사하여 안전한 곳에 보관합니다. (이 창을 벗어나면 다시 볼 수 없습니다!)

### (2) Repositories 만들기
* 깃허브 로그인 → 오른쪽 상단 프로필 → **Your repositories** → **New** 버튼 클릭
* 자동으로 업로드할 저장소의 이름을 설정하고 **Public**으로 지정한 뒤 **Create repository** 버튼을 클릭합니다.

<br>

---

## 3️⃣ 프로그램 시작

### 1. 개인 정보 설정
`⚙️ 설정` 버튼을 눌러 아래 정보를 입력합니다.
* **GitHub 토큰**: 방금 발급받은 토큰
* **Github 이름**: 본인의 깃허브 아이디
* **업로드 할 Github repositories 이름**: 위에서 생성한 저장소 이름
* **감시할 폴더**: 동기화를 원하는 로컬 폴더

<br>
<img width="406" height="259" alt="image" src="https://github.com/user-attachments/assets/98e8efdd-d622-4397-8e1f-e32e82ece6f0" />
<br>

### 2. 동기화 시작
* **`▶️ 동기화&업로드 시작`**: 버튼을 누르면 초기 동기화가 진행된 후, 실시간 감시가 시작됩니다.
* **실시간 감지**: 감시가 시작된 후 폴더에 파일을 추가, 수정, 삭제하면 자동으로 깃허브에 반영됩니다.
* **휴지통 기능**: 파일 삭제 시, 깃허브 저장소의 `_recycle_bin` 폴더로 이동되어 안전하게 보관됩니다.
* **`⏹️ 업로드 종료`**: 실시간 감시를 중단합니다.

<br>

---

## 4️⃣ 백준 문제

1.  **`✏️ 백준 문제 찾기`**: 버튼을 누르면 별도의 문제 찾기 창이 나타납니다.
2.  **클래스 선택**: 원하는 난이도의 클래스(1~10)를 선택하고 '문제 불러오기'를 누릅니다.
3.  **문제 열기**: 목록에서 원하는 문제를 더블클릭하면 해당 문제 페이지가 웹 브라우저의 새 탭으로 열립니다.
