"""
PDF 처리 도구 (PyMuPDF 기반)

- pdf_to_images : PDF의 각 페이지를 JPG로 렌더링
- compress_pdf  : PDF 용량 최적화 (재압축/불필요 데이터 정리)
- merge_pdfs    : 여러 PDF를 하나로 병합
- split_pdf     : PDF를 페이지별 개별 PDF로 분할

이미지 저장에는 Pillow를 사용한다(품질 조절이 쉬움).
"""

import os

import fitz  # PyMuPDF
from PIL import Image


def pdf_to_images(src_path, out_dir, dpi=150, quality=90, name_base=None):
    """PDF의 각 페이지를 JPG로 렌더링해 out_dir에 저장하고 경로 목록을 돌려준다.

    name_base: 결과 파일 이름의 기준(생략 시 원본 파일명). 저장된 업로드에는
               고유 접두어가 붙으므로, 깔끔한 이름을 쓰려면 이 값을 넘긴다.
    """
    os.makedirs(out_dir, exist_ok=True)
    base = name_base or os.path.splitext(os.path.basename(src_path))[0]
    saved = []

    with fitz.open(src_path) as doc:
        if doc.page_count == 0:
            raise ValueError("페이지가 없는 PDF입니다.")
        digits = len(str(doc.page_count))  # 페이지 번호 자릿수 (정렬용)
        for i, page in enumerate(doc, start=1):
            # alpha=False → 투명 없는 RGB 픽스맵 (JPG에 바로 사용 가능)
            pix = page.get_pixmap(dpi=dpi, alpha=False)
            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            out_path = os.path.join(out_dir, f"{base}_p{i:0{digits}d}.jpg")
            img.save(out_path, "JPEG", quality=quality)
            saved.append(out_path)

    return saved


def extract_text(src_path, dst_path):
    """PDF의 모든 페이지 텍스트를 추출해 dst_path(.txt)에 저장한다.

    반환: (총 글자 수, 페이지 수). 글자 수가 0이면 텍스트 레이어가 없는
          스캔 PDF일 가능성이 높다(호출 측에서 안내).
    """
    parts = []
    with fitz.open(src_path) as doc:
        page_count = doc.page_count
        for i, page in enumerate(doc, start=1):
            text = page.get_text().strip()
            if text:
                parts.append(f"===== {i} 페이지 =====\n{text}")

    body = "\n\n".join(parts)
    # 한글 깨짐 방지를 위해 UTF-8 with BOM (메모장에서도 정상 표시)
    with open(dst_path, "w", encoding="utf-8-sig") as f:
        f.write(body)

    char_count = sum(len(p) for p in parts)
    return char_count, page_count


def extract_images(src_path, out_dir, name_base=None):
    """PDF에 포함된(임베드된) 이미지를 원본 형식 그대로 추출한다.

    페이지 렌더링이 아니라 PDF 안에 저장된 실제 이미지를 뽑는다.
    같은 이미지가 여러 페이지에 쓰이면 한 번만 저장한다.
    반환: 저장된 파일 경로 목록.
    """
    os.makedirs(out_dir, exist_ok=True)
    base = name_base or os.path.splitext(os.path.basename(src_path))[0]
    saved = []
    seen = set()  # 중복 이미지(xref) 방지

    with fitz.open(src_path) as doc:
        for page in doc:
            for img in page.get_images(full=True):
                xref = img[0]
                if xref in seen:
                    continue
                seen.add(xref)
                info = doc.extract_image(xref)  # {'image': bytes, 'ext': 'png'|'jpeg'...}
                ext = info.get("ext", "png")
                idx = len(saved) + 1
                out_path = os.path.join(out_dir, f"{base}_img{idx:03d}.{ext}")
                with open(out_path, "wb") as f:
                    f.write(info["image"])
                saved.append(out_path)

    return saved


def compress_pdf(src_path, dst_path):
    """PDF를 다시 저장하며 용량을 줄인다. (원본, 결과) 바이트 크기를 함께 돌려준다."""
    with fitz.open(src_path) as doc:
        # garbage=4: 중복/미사용 객체 제거, deflate*: 스트림/이미지/폰트 압축
        doc.save(
            dst_path,
            garbage=4,
            deflate=True,
            deflate_images=True,
            deflate_fonts=True,
            clean=True,
        )
    return os.path.getsize(src_path), os.path.getsize(dst_path)


def merge_pdfs(src_paths, dst_path):
    """여러 PDF를 순서대로 하나로 합친다. 합쳐진 총 페이지 수를 돌려준다."""
    if len(src_paths) < 2:
        raise ValueError("병합하려면 PDF가 2개 이상 필요합니다.")

    merged = fitz.open()
    try:
        for path in src_paths:
            with fitz.open(path) as doc:
                merged.insert_pdf(doc)
        page_count = merged.page_count
        merged.save(dst_path, garbage=3, deflate=True)
    finally:
        merged.close()
    return page_count


def split_pdf(src_path, out_dir, name_base=None):
    """PDF를 페이지별 개별 PDF로 나눈다. 생성된 파일 경로 목록을 돌려준다."""
    os.makedirs(out_dir, exist_ok=True)
    base = name_base or os.path.splitext(os.path.basename(src_path))[0]
    saved = []

    with fitz.open(src_path) as doc:
        if doc.page_count == 0:
            raise ValueError("페이지가 없는 PDF입니다.")
        digits = len(str(doc.page_count))
        for i in range(doc.page_count):
            single = fitz.open()
            single.insert_pdf(doc, from_page=i, to_page=i)
            out_path = os.path.join(out_dir, f"{base}_p{i + 1:0{digits}d}.pdf")
            single.save(out_path)
            single.close()
            saved.append(out_path)

    return saved
