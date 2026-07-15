"""
로컬 파일 변환기 - Flask 웹 서버

실행:
    python app.py
그다음 브라우저에서 http://127.0.0.1:5000 접속

- 이미지: convert_image.py 의 변환 함수 사용
- PDF   : pdf_tools.py 의 도구(→JPG / 압축 / 병합 / 분할) 사용
모든 처리는 이 PC 안에서 이뤄지며 파일은 외부로 전송되지 않는다.
"""

import os
import shutil
import sys
import uuid
import zipfile

from flask import (
    Flask,
    jsonify,
    render_template,
    request,
    send_from_directory,
)

from convert_image import FORMAT_ALIASES, convert_image
from pdf_tools import (
    compress_pdf,
    extract_images,
    extract_text,
    merge_pdfs,
    pdf_to_images,
    split_pdf,
)
from video_tools import convert_video, find_ffmpeg
from audio_tools import convert_audio

VIDEO_FORMATS = {"mp4", "mov", "webm", "gif"}
AUDIO_FORMATS = {"mp3", "wav", "m4a"}

# 프리징(PyInstaller exe) 대응 경로 분리:
#  - RES_DIR : templates/static 등 읽기 전용 리소스 (exe 내부 _MEIPASS)
#  - DATA_DIR: uploads/outputs 등 쓰기 데이터 (exe '옆' 폴더 → 실행 후에도 남음)
if getattr(sys, "frozen", False):
    RES_DIR = sys._MEIPASS
    DATA_DIR = os.path.dirname(sys.executable)
else:
    RES_DIR = os.path.dirname(os.path.abspath(__file__))
    DATA_DIR = RES_DIR

UPLOAD_DIR = os.path.join(DATA_DIR, "storage", "uploads")
OUTPUT_DIR = os.path.join(DATA_DIR, "storage", "outputs")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

app = Flask(
    __name__,
    template_folder=os.path.join(RES_DIR, "templates"),
    static_folder=os.path.join(RES_DIR, "static"),
)
app.config["MAX_CONTENT_LENGTH"] = 500 * 1024 * 1024  # 업로드 최대 500MB (영상 대비)

TARGET_FORMATS = ["jpg", "png", "webp"]


# --------------------------------------------------------------------------
# 공통 헬퍼
# --------------------------------------------------------------------------
def _safe_basename(filename):
    """경로 구분자를 제거해 파일 이름 부분만 안전하게 얻는다 (한글 유지)."""
    name = os.path.basename((filename or "").replace("\\", "/"))
    return name or "file"


def _save_upload(upload):
    """업로드 파일을 고유 접두어로 저장하고 (토큰, 원본명, 확장자없는이름, 경로)를 돌려준다."""
    original = _safe_basename(upload.filename)
    token = uuid.uuid4().hex[:8]
    src_path = os.path.join(UPLOAD_DIR, f"{token}_{original}")
    upload.save(src_path)
    base = os.path.splitext(original)[0]
    return token, original, base, src_path


def _is_pdf(upload):
    return (upload.filename or "").lower().endswith(".pdf")


def _zip_paths(paths, stored_zip_name):
    """여러 파일을 OUTPUT_DIR 안에 하나의 zip으로 묶는다."""
    zip_path = os.path.join(OUTPUT_DIR, stored_zip_name)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in paths:
            zf.write(p, arcname=os.path.basename(p))
    return zip_path


def _fmt_size(n):
    """바이트 수를 사람이 읽기 쉬운 문자열로."""
    size = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f}{unit}" if unit == "B" else f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}GB"


def _ok(stored, download_name, note=None):
    return jsonify(
        ok=True,
        stored=stored,
        download_name=download_name,
        download_url=f"/download/{stored}?name={download_name}",
        note=note,
    )


# --------------------------------------------------------------------------
# 라우트
# --------------------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html", formats=TARGET_FORMATS)


@app.route("/convert", methods=["POST"])
def convert():
    """이미지 포맷 변환 (1개 → 1개)."""
    upload = request.files.get("file")
    if not upload or not upload.filename:
        return jsonify(ok=False, error="파일이 전송되지 않았습니다."), 400

    target = (request.form.get("format") or "").lower().lstrip(".")
    if target not in FORMAT_ALIASES:
        return jsonify(ok=False, error=f"지원하지 않는 포맷입니다: {target}"), 400

    token, _, base, src_path = _save_upload(upload)
    out_name = f"{token}_{base}.{target}"
    dst_path = os.path.join(OUTPUT_DIR, out_name)
    try:
        convert_image(src_path, target, dst_path)
    except Exception as e:  # noqa: BLE001
        return jsonify(ok=False, error=f"변환 실패: {e}"), 500

    return _ok(out_name, f"{base}.{target}")


@app.route("/pdf/to-jpg", methods=["POST"])
def pdf_to_jpg():
    """PDF의 각 페이지를 JPG로 (여러 장이면 zip)."""
    upload = request.files.get("file")
    if not upload or not upload.filename:
        return jsonify(ok=False, error="파일이 전송되지 않았습니다."), 400
    if not _is_pdf(upload):
        return jsonify(ok=False, error="PDF 파일만 넣어 주세요."), 400

    token, _, base, src_path = _save_upload(upload)
    work_dir = os.path.join(UPLOAD_DIR, f"{token}_work")
    try:
        images = pdf_to_images(src_path, work_dir, name_base=base)
    except Exception as e:  # noqa: BLE001
        return jsonify(ok=False, error=f"변환 실패: {e}"), 500

    if len(images) == 1:
        stored = f"{token}_{base}.jpg"
        shutil.move(images[0], os.path.join(OUTPUT_DIR, stored))
        result = _ok(stored, f"{base}.jpg", note="1페이지")
    else:
        stored = f"{token}_{base}_jpg.zip"
        _zip_paths(images, stored)
        result = _ok(stored, f"{base}_jpg.zip", note=f"{len(images)}장 이미지 · ZIP")

    shutil.rmtree(work_dir, ignore_errors=True)
    return result


@app.route("/pdf/compress", methods=["POST"])
def pdf_compress():
    """PDF 용량 최적화 (1개 → 1개)."""
    upload = request.files.get("file")
    if not upload or not upload.filename:
        return jsonify(ok=False, error="파일이 전송되지 않았습니다."), 400
    if not _is_pdf(upload):
        return jsonify(ok=False, error="PDF 파일만 넣어 주세요."), 400

    token, _, base, src_path = _save_upload(upload)
    stored = f"{token}_{base}_compressed.pdf"
    dst_path = os.path.join(OUTPUT_DIR, stored)
    try:
        before, after = compress_pdf(src_path, dst_path)
    except Exception as e:  # noqa: BLE001
        return jsonify(ok=False, error=f"압축 실패: {e}"), 500

    if after < before:
        pct = round((1 - after / before) * 100)
        note = f"{_fmt_size(before)} → {_fmt_size(after)} ({pct}% 감소)"
    else:
        note = f"이미 최적화된 PDF입니다 ({_fmt_size(after)})"
    return _ok(stored, f"{base}_compressed.pdf", note=note)


@app.route("/pdf/split", methods=["POST"])
def pdf_split():
    """PDF를 페이지별 개별 PDF로 분할 (여러 장이면 zip)."""
    upload = request.files.get("file")
    if not upload or not upload.filename:
        return jsonify(ok=False, error="파일이 전송되지 않았습니다."), 400
    if not _is_pdf(upload):
        return jsonify(ok=False, error="PDF 파일만 넣어 주세요."), 400

    token, _, base, src_path = _save_upload(upload)
    work_dir = os.path.join(UPLOAD_DIR, f"{token}_split")
    try:
        pages = split_pdf(src_path, work_dir, name_base=base)
    except Exception as e:  # noqa: BLE001
        return jsonify(ok=False, error=f"분할 실패: {e}"), 500

    if len(pages) == 1:
        stored = f"{token}_{base}_p1.pdf"
        shutil.move(pages[0], os.path.join(OUTPUT_DIR, stored))
        result = _ok(stored, f"{base}_p1.pdf", note="1페이지 (분할 불필요)")
    else:
        stored = f"{token}_{base}_split.zip"
        _zip_paths(pages, stored)
        result = _ok(stored, f"{base}_split.zip", note=f"{len(pages)}페이지 · ZIP")

    shutil.rmtree(work_dir, ignore_errors=True)
    return result


@app.route("/pdf/extract-text", methods=["POST"])
def pdf_extract_text():
    """PDF에서 텍스트를 추출해 .txt로 (1개 → 1개)."""
    upload = request.files.get("file")
    if not upload or not upload.filename:
        return jsonify(ok=False, error="파일이 전송되지 않았습니다."), 400
    if not _is_pdf(upload):
        return jsonify(ok=False, error="PDF 파일만 넣어 주세요."), 400

    token, _, base, src_path = _save_upload(upload)
    stored = f"{token}_{base}.txt"
    dst_path = os.path.join(OUTPUT_DIR, stored)
    try:
        chars, pages = extract_text(src_path, dst_path)
    except Exception as e:  # noqa: BLE001
        return jsonify(ok=False, error=f"텍스트 추출 실패: {e}"), 500

    if chars == 0:
        os.remove(dst_path)
        return jsonify(
            ok=False,
            error="추출할 텍스트가 없습니다. 이미지로 스캔된 PDF일 수 있어요.",
        ), 422

    return _ok(stored, f"{base}.txt", note=f"{pages}페이지 · 약 {chars:,}자")


@app.route("/pdf/extract-images", methods=["POST"])
def pdf_extract_images():
    """PDF에 포함된 이미지를 추출해 zip으로 (여러 장이면 zip, 1장이면 그대로)."""
    upload = request.files.get("file")
    if not upload or not upload.filename:
        return jsonify(ok=False, error="파일이 전송되지 않았습니다."), 400
    if not _is_pdf(upload):
        return jsonify(ok=False, error="PDF 파일만 넣어 주세요."), 400

    token, _, base, src_path = _save_upload(upload)
    work_dir = os.path.join(UPLOAD_DIR, f"{token}_imgs")
    try:
        images = extract_images(src_path, work_dir, name_base=base)
    except Exception as e:  # noqa: BLE001
        return jsonify(ok=False, error=f"이미지 추출 실패: {e}"), 500

    if not images:
        shutil.rmtree(work_dir, ignore_errors=True)
        return jsonify(
            ok=False,
            error="PDF 안에 포함된 이미지가 없습니다. (텍스트만 있는 문서일 수 있어요)",
        ), 422

    if len(images) == 1:
        ext = os.path.splitext(images[0])[1]
        stored = f"{token}_{base}_img1{ext}"
        shutil.move(images[0], os.path.join(OUTPUT_DIR, stored))
        result = _ok(stored, f"{base}_img1{ext}", note="이미지 1장")
    else:
        stored = f"{token}_{base}_images.zip"
        _zip_paths(images, stored)
        result = _ok(stored, f"{base}_images.zip", note=f"이미지 {len(images)}장 · ZIP")

    shutil.rmtree(work_dir, ignore_errors=True)
    return result


@app.route("/pdf/merge", methods=["POST"])
def pdf_merge():
    """여러 PDF를 순서대로 하나로 병합 (여러 개 → 1개)."""
    uploads = [u for u in request.files.getlist("file") if u and u.filename]
    if len(uploads) < 2:
        return jsonify(ok=False, error="병합하려면 PDF를 2개 이상 올려 주세요."), 400
    for u in uploads:
        if not _is_pdf(u):
            return jsonify(ok=False, error=f"PDF가 아닌 파일이 있습니다: {u.filename}"), 400

    token = uuid.uuid4().hex[:8]
    src_paths = []
    for i, u in enumerate(uploads):
        p = os.path.join(UPLOAD_DIR, f"{token}_{i:03d}_{_safe_basename(u.filename)}")
        u.save(p)
        src_paths.append(p)

    stored = f"{token}_merged.pdf"
    dst_path = os.path.join(OUTPUT_DIR, stored)
    try:
        pages = merge_pdfs(src_paths, dst_path)
    except Exception as e:  # noqa: BLE001
        return jsonify(ok=False, error=f"병합 실패: {e}"), 500

    return _ok(stored, "merged.pdf", note=f"{len(uploads)}개 · 총 {pages}페이지")


@app.route("/video/convert", methods=["POST"])
def video_convert():
    """영상 포맷 변환 (MP4/MOV/WEBM/GIF). 1개 → 1개."""
    upload = request.files.get("file")
    if not upload or not upload.filename:
        return jsonify(ok=False, error="파일이 전송되지 않았습니다."), 400

    target = (request.form.get("format") or "").lower().lstrip(".")
    if target not in VIDEO_FORMATS:
        return jsonify(ok=False, error=f"지원하지 않는 영상 포맷입니다: {target}"), 400

    if find_ffmpeg() is None:
        return jsonify(
            ok=False,
            error="영상 변환에는 ffmpeg가 필요합니다. 설치 후 run.bat을 다시 실행해 주세요.",
        ), 503

    token, _, base, src_path = _save_upload(upload)
    stored = f"{token}_{base}.{target}"
    dst_path = os.path.join(OUTPUT_DIR, stored)
    try:
        size = convert_video(src_path, dst_path, target)
    except Exception as e:  # noqa: BLE001
        return jsonify(ok=False, error=f"변환 실패: {e}"), 500

    return _ok(stored, f"{base}.{target}", note=_fmt_size(size))


@app.route("/audio/convert", methods=["POST"])
def audio_convert():
    """오디오 포맷 변환 (MP3/WAV/M4A). 영상 입력 시 오디오만 추출. 1개 → 1개."""
    upload = request.files.get("file")
    if not upload or not upload.filename:
        return jsonify(ok=False, error="파일이 전송되지 않았습니다."), 400

    target = (request.form.get("format") or "").lower().lstrip(".")
    if target not in AUDIO_FORMATS:
        return jsonify(ok=False, error=f"지원하지 않는 오디오 포맷입니다: {target}"), 400

    if find_ffmpeg() is None:
        return jsonify(
            ok=False,
            error="오디오 변환에는 ffmpeg가 필요합니다. 설치 후 run.bat을 다시 실행해 주세요.",
        ), 503

    token, _, base, src_path = _save_upload(upload)
    stored = f"{token}_{base}.{target}"
    dst_path = os.path.join(OUTPUT_DIR, stored)
    try:
        size = convert_audio(src_path, dst_path, target)
    except Exception as e:  # noqa: BLE001
        return jsonify(ok=False, error=f"변환 실패: {e}"), 500

    return _ok(stored, f"{base}.{target}", note=_fmt_size(size))


@app.route("/download/<path:stored>")
def download(stored):
    download_name = request.args.get("name", stored)
    return send_from_directory(
        OUTPUT_DIR, stored, as_attachment=True, download_name=download_name
    )


def _open_browser_later(url, delay=1.5):
    """서버가 뜰 시간을 준 뒤 기본 브라우저로 페이지를 연다 (별도 스레드)."""
    import threading
    import time
    import webbrowser

    def _open():
        time.sleep(delay)
        webbrowser.open(url)

    threading.Thread(target=_open, daemon=True).start()


if __name__ == "__main__":
    HOST, PORT = "127.0.0.1", 5000
    url = f"http://{HOST}:{PORT}"

    # exe로 실행된 경우: 안내 문구 + 브라우저 자동 오픈
    if getattr(sys, "frozen", False):
        print("=" * 46)
        print("  파일 변환기 실행 중")
        print(f"  브라우저가 자동으로 열립니다  ({url})")
        print("  이 창을 닫으면 종료됩니다. 사용하는 동안 열어 두세요.")
        print("=" * 46)
        _open_browser_later(url)

    # waitress(순수 파이썬 WSGI)로 조용하고 안정적으로 서빙.
    # 개발 환경에 waitress가 없으면 Flask 내장 서버로 대체.
    try:
        from waitress import serve

        serve(app, host=HOST, port=PORT, threads=8)
    except ImportError:
        app.run(host=HOST, port=PORT, debug=False, threaded=True)
