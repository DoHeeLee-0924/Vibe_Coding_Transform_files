"""
이미지 포맷 변환기 (핵심 기능 1개)

사용법 (터미널):
    python convert_image.py <입력파일> <목표포맷> [출력파일]

예시:
    python convert_image.py sample.png jpg
    python convert_image.py sample.png jpg result.jpg
"""

import os
import sys

from PIL import Image


# 확장자 → Pillow 저장 포맷 이름 매핑 (사용자가 편하게 쓰도록 별칭 허용)
FORMAT_ALIASES = {
    "jpg": "JPEG",
    "jpeg": "JPEG",
    "png": "PNG",
    "webp": "WEBP",
}

# 알파(투명) 채널을 버려야 하는(투명 미지원) 포맷
NO_ALPHA_FORMATS = {"JPEG"}


def convert_image(src_path, target_format, dst_path=None, background=(255, 255, 255)):
    """
    이미지 파일을 목표 포맷으로 변환해 저장한다.

    Args:
        src_path:       원본 이미지 경로
        target_format:  목표 포맷 (jpg, png, webp ...)
        dst_path:       저장 경로. 생략 시 원본과 같은 폴더에 확장자만 바꿔 저장
        background:     투명 영역을 채울 배경색 (기본 흰색)

    Returns:
        저장된 파일의 경로
    """
    # 1) 목표 포맷 확인
    key = target_format.lower().lstrip(".")
    if key not in FORMAT_ALIASES:
        raise ValueError(
            f"지원하지 않는 포맷입니다: '{target_format}' "
            f"(가능: {', '.join(sorted(FORMAT_ALIASES))})"
        )
    pillow_format = FORMAT_ALIASES[key]

    # 2) 입력 파일 확인
    if not os.path.isfile(src_path):
        raise FileNotFoundError(f"파일을 찾을 수 없습니다: {src_path}")

    # 3) 출력 경로 결정 (생략 시 원본 이름 + 새 확장자)
    if dst_path is None:
        base, _ = os.path.splitext(src_path)
        dst_path = f"{base}.{key}"

    # 4) 열기 → 변환 → 저장
    with Image.open(src_path) as img:
        if pillow_format in NO_ALPHA_FORMATS:
            # JPG 등 투명 미지원 포맷: 투명 영역을 배경색으로 채운다
            img = _flatten_transparency(img, background)
        else:
            # 그 외: 팔레트(P) 등은 RGBA로 정규화해 안전하게 저장
            if img.mode not in ("RGB", "RGBA"):
                img = img.convert("RGBA")

        img.save(dst_path, format=pillow_format)

    return dst_path


def _flatten_transparency(img, background):
    """투명 영역이 있는 이미지를 배경색 위에 합성해 불투명 RGB로 만든다."""
    # 팔레트 이미지(P) 등도 알파를 다룰 수 있게 RGBA로 통일
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
        canvas = Image.new("RGB", img.size, background)
        # 알파 채널을 마스크로 사용해 배경 위에 붙임
        canvas.paste(img, mask=img.split()[-1])
        return canvas
    # 애초에 투명 정보가 없으면 RGB로만 변환
    return img.convert("RGB")


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 1

    src = argv[0]
    target = argv[1]
    dst = argv[2] if len(argv) >= 3 else None

    try:
        out = convert_image(src, target, dst)
    except (ValueError, FileNotFoundError) as e:
        print(f"[오류] {e}")
        return 1

    print(f"[완료] {src} -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
