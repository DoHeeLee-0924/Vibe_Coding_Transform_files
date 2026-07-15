"""
영상 처리 도구 (ffmpeg 기반)

- find_ffmpeg   : ffmpeg 실행 파일 경로 탐색 (PATH + winget 설치 위치)
- convert_video : 영상 포맷 변환 (MP4 / MOV / WEBM) 및 GIF 변환

ffmpeg는 pip으로 설치되지 않는 외부 프로그램이므로, 없으면
호출 측에서 사용자에게 설치를 안내한다.
"""

import glob
import os
import shutil
import subprocess
import sys

# 목표 포맷별 ffmpeg 인코딩 옵션
_VIDEO_CODECS = {
    "mp4": ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
            "-c:a", "aac", "-movflags", "+faststart"],
    "mov": ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-c:a", "aac"],
    "webm": ["-c:v", "libvpx-vp9", "-crf", "32", "-b:v", "0", "-c:a", "libopus"],
}

# GIF 화질/크기 기본값
_GIF_VF = "fps=12,scale=640:-1:flags=lanczos"


def find_ffmpeg():
    """ffmpeg 실행 파일 경로를 찾는다. 없으면 None.

    탐색 순서: ①exe 번들 내부 ②앱 폴더 옆 ffmpeg\\ ③시스템 PATH ④winget 설치 위치.
    배포된 exe에서는 동봉된 ffmpeg가 항상 먼저 쓰여 사용자 PC 상태와 무관하게 동작한다.
    """
    candidates = []

    # ① PyInstaller로 빌드된 exe라면 번들 내부(_MEIPASS)에 동봉된 ffmpeg
    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS", "")
        candidates.append(os.path.join(base, "ffmpeg", "ffmpeg.exe"))

    # ② 개발/포터블: 앱 폴더 옆 ffmpeg\ 또는 ffmpeg\bin\
    here = os.path.dirname(os.path.abspath(__file__))
    candidates.append(os.path.join(here, "ffmpeg", "ffmpeg.exe"))
    candidates.append(os.path.join(here, "ffmpeg", "bin", "ffmpeg.exe"))

    for c in candidates:
        if os.path.isfile(c):
            return c

    # ③ 시스템 PATH
    found = shutil.which("ffmpeg")
    if found:
        return found

    # ④ winget(Gyan.FFmpeg 등) 설치 위치 (PATH 갱신 전이라도)
    local = os.environ.get("LOCALAPPDATA", "")
    if local:
        pattern = os.path.join(
            local, "Microsoft", "WinGet", "Packages", "*FFmpeg*", "**", "ffmpeg.exe"
        )
        for c in glob.glob(pattern, recursive=True):
            if os.path.isfile(c):
                return c
    return None


def _run(args):
    """ffmpeg 명령을 실행하고 실패 시 stderr 끝부분을 담아 예외를 던진다."""
    proc = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        tail = (proc.stderr or "").strip().splitlines()[-3:]
        raise RuntimeError("ffmpeg 오류: " + " / ".join(tail))


def convert_video(src_path, dst_path, target):
    """영상을 목표 포맷으로 변환한다. 결과 파일 크기(바이트)를 돌려준다."""
    ff = find_ffmpeg()
    if ff is None:
        raise RuntimeError(
            "ffmpeg가 설치되어 있지 않습니다. 설치 후 다시 시도해 주세요."
        )

    target = target.lower().lstrip(".")
    if target == "gif":
        _to_gif(ff, src_path, dst_path)
    elif target in _VIDEO_CODECS:
        _run([ff, "-y", "-i", src_path, *_VIDEO_CODECS[target], dst_path])
    else:
        raise ValueError(f"지원하지 않는 영상 포맷입니다: {target}")

    return os.path.getsize(dst_path)


def _to_gif(ff, src_path, dst_path):
    """팔레트 2패스 방식으로 화질 좋은 GIF를 만든다."""
    palette = dst_path + ".palette.png"
    try:
        # 1패스: 최적 팔레트 생성
        _run([ff, "-y", "-i", src_path, "-vf", f"{_GIF_VF},palettegen", palette])
        # 2패스: 팔레트 적용해 GIF 출력
        _run([
            ff, "-y", "-i", src_path, "-i", palette,
            "-filter_complex", f"{_GIF_VF}[x];[x][1:v]paletteuse",
            dst_path,
        ])
    finally:
        if os.path.exists(palette):
            os.remove(palette)
