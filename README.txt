## 🛠️ 사용된 주요 기술 및 라이브러리
이 프로그램은 다음과 같은 파이썬 라이브러리들을 기반으로 구현되었습니다.

(1) GUI: Tkinter, ttkbootstrap

파이썬 표준 GUI 라이브러리인 Tkinter를 기반으로, ttkbootstrap을 사용하여 세련되고 현대적인 디자인의 UI를 구축했습니다.

(2) 파일 시스템 감시: watchdog

지정된 폴더의 파일 생성, 수정, 삭제 이벤트를 실시간으로 감지하여 자동화 로직을 촉발하는 핵심 라이브러리입니다.

(3) 웹 통신 (API & 크롤링): requests, BeautifulSoup

requests를 통해 GitHub REST API와 통신하여 파일 업로드, 삭제, 목록 조회 등을 처리합니다.

(4) problem_finder 모듈 :BeautifulSoup을 이용

solved.ac의 HTML을 분석(파싱)하여 문제 데이터를 추출합니다.

(5) 동시성 처리: threading

파일 감시, 초기 동기화, 웹 크롤링 등 시간이 걸리는 작업이 실행되는 동안에도 UI가 멈추지 않고 부드럽게 반응하도록 백그라운드 스레드를 활용했습니다.

(6) 데이터 처리: json, base64

사용자의 설정을 config.json 파일로 저장하고 불러오는 데 json을 사용했습니다.

깃허브 API 요구사항에 맞춰 파일 내용을 base64로 인코딩하여 전송합니다.

(7) 시스템 및 자동화: os, sys, webbrowser

파일 경로를 다루고, 실행 파일 환경을 감지하며, 외부 웹 브라우저를 여는 등 시스템과 상호작용하는 데 사용됩니다.
