# 파일 변환기 (File Converter)

비개발자도 **드래그앤드롭 한 번**으로 파일을 변환할 수 있는 **로컬 웹 도구**입니다.
모든 처리는 이 PC 안에서 이뤄지며, **파일이 외부로 전송되지 않습니다.**

Python(Flask) + Pillow + PyMuPDF + ffmpeg 로 동작합니다.

---

## ✨ 기능 (총 15개 도구)

| 카테고리 | 도구 |
|----------|------|
| **이미지** | JPG · PNG · WEBP 변환 (PNG→JPG 시 투명 영역 흰색 처리) |
| **PDF** | → JPG · 압축 · 병합 · 분할 · 텍스트 추출 · 이미지 추출 |
| **영상** | MP4 · GIF · WEBM 변환 |
| **오디오** | MP3 · WAV · M4A 변환 (영상에서 소리만 추출 가능) |

- 파일마다 **진행률 바 + 상태 배지**(처리중 / 완료 / 실패)를 표시
- 결과가 여러 개면 자동으로 **ZIP**으로 묶어 제공
- PDF 병합은 파일 순서를 지정해 하나로 합침

---

## 🚀 실행 방법

### 방법 1. 배포용 실행파일 (비개발자용 — 권장)

1. `파일변환기.exe` 를 더블클릭
2. 검은 창이 뜨고 → 잠시 후 브라우저가 자동으로 열림
3. 파일을 드래그해서 변환
4. 다 쓰면 검은 창을 닫으면 종료

> Python·ffmpeg 설치가 전혀 필요 없습니다(모두 내장). 첫 실행은 5~10초 정도 걸릴 수 있습니다.
> exe는 저장소가 아니라 **[Releases](../../releases)** 에서 내려받으세요.

### 방법 2. 소스로 실행 (개발용)

```bash
# 1) 파이썬 패키지 설치
python -m pip install -r requirements.txt

# 2) (영상/오디오용) ffmpeg 설치 — Windows
winget install --id Gyan.FFmpeg -e

# 3) 실행
python app.py
```

또는 Windows에서 `run.bat` 더블클릭 (서버 실행 + 브라우저 자동 오픈).

실행 후 브라우저에서 **http://127.0.0.1:5000** 접속.

---

## 🧱 프로젝트 구조

```
Vibe_Coding_Transform_files/
├── app.py              # Flask 웹 서버 (라우팅 + 업로드/다운로드)
├── convert_image.py    # 이미지 변환 (Pillow)
├── pdf_tools.py        # PDF 도구 (PyMuPDF)
├── video_tools.py      # 영상 변환 (ffmpeg) + ffmpeg 경로 탐색
├── audio_tools.py      # 오디오 변환 (ffmpeg)
├── templates/
│   └── index.html      # 툴 허브 화면
├── static/
│   ├── style.css       # 라이트 테마 UI
│   └── main.js         # 드롭존·진행률·병합 UI
├── storage/            # 업로드/결과 (실행 시 자동 생성, git 제외)
├── requirements.txt    # 파이썬 의존성
├── run.bat             # Windows 실행 런처
└── README.md
```

역할이 명확히 나뉘어, 새 포맷/도구 추가 시 해당 `*_tools.py`와 카드만 추가하면 됩니다.

---

## 🛠 기술 스택 / 의존성

**파이썬 패키지** (`requirements.txt`)
- Flask — 로컬 웹 서버
- Pillow — 이미지 변환
- PyMuPDF — PDF 렌더링·편집
- waitress — 안정적인 WSGI 서버 (배포 실행용)

**외부 프로그램** (pip으로 설치되지 않음)
- **ffmpeg** — 영상·오디오 변환에 필요
  - `find_ffmpeg()` 가 ①exe 번들 내부 ②앱 옆 `ffmpeg/` ③시스템 PATH ④winget 위치 순으로 탐색
  - 배포 exe에는 ffmpeg가 내장되어 별도 설치 불필요

---

## 📦 실행파일(.exe) 빌드 방법

```bash
python -m pip install pyinstaller waitress

python -m PyInstaller --onefile --name FileConverter --clean --noconfirm --console ^
  --add-data "templates;templates" ^
  --add-data "static;static" ^
  --add-data "<ffmpeg.exe 경로>;ffmpeg" ^
  --collect-all pymupdf ^
  --collect-all waitress ^
  app.py
```

- 결과물: `dist/FileConverter.exe` (ffmpeg 포함 시 약 138MB)
- 읽기 리소스는 exe 내부에, 사용자 데이터(`storage/`)는 exe 옆에 생성됩니다.

---

## 🔒 개인정보 / 보안

- 서버는 `127.0.0.1`(로컬)에만 바인딩되어 **외부에서 접근할 수 없습니다.**
- 업로드·변환 파일은 이 PC의 `storage/` 폴더에만 저장되며 인터넷으로 전송되지 않습니다.

---

## 📌 알아두기

- **스캔된 PDF**(글자가 이미지로 된 문서)는 텍스트 추출이 되지 않습니다. → OCR 기능은 향후 추가 예정.
- exe는 백신이 드물게 오탐할 수 있습니다(PyInstaller 특성). 사내 배포 시 예외 등록이 필요할 수 있습니다.
