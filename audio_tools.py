"""
오디오 처리 도구 (ffmpeg 기반)

- convert_audio : 오디오 포맷 변환 (MP3 / WAV / M4A)
                  입력에 영상이 들어오면 오디오만 추출한다(-vn).

ffmpeg 실행 파일 탐색은 video_tools.find_ffmpeg 를 공유한다.
"""

import os

from video_tools import _run, find_ffmpeg

# 목표 포맷별 ffmpeg 오디오 인코딩 옵션 (-vn: 영상 스트림 제거 → 오디오만)
_AUDIO_CODECS = {
    "mp3": ["-vn", "-c:a", "libmp3lame", "-q:a", "2"],   # VBR ~190kbps
    "wav": ["-vn", "-c:a", "pcm_s16le"],                 # 무손실 PCM
    "m4a": ["-vn", "-c:a", "aac", "-b:a", "192k"],       # AAC 192kbps
}


def convert_audio(src_path, dst_path, target):
    """오디오(또는 영상의 오디오)를 목표 포맷으로 변환한다. 결과 크기(바이트) 반환."""
    ff = find_ffmpeg()
    if ff is None:
        raise RuntimeError("ffmpeg가 설치되어 있지 않습니다. 설치 후 다시 시도해 주세요.")

    target = target.lower().lstrip(".")
    if target not in _AUDIO_CODECS:
        raise ValueError(f"지원하지 않는 오디오 포맷입니다: {target}")

    _run([ff, "-y", "-i", src_path, *_AUDIO_CODECS[target], dst_path])
    return os.path.getsize(dst_path)
