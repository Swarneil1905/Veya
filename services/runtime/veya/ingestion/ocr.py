"""Optional local OCR. No model downloads, external services, or document network egress."""

import math
from pathlib import Path

from veya.domain.models import DomainError
from veya.security.artifact_integrity import verified_bytes

MODELS = {
    'ch_PP-OCRv4_det_infer.onnx': 'd2a7720d45a54257208b1e13e36a8479894cb74155a5efe29462512d42f49da9',
    'ch_PP-OCRv4_rec_infer.onnx': '48fc40f24f6d2a207a2b1091d3437eb3cc3eb6b676dc3ef9c37384005483683b',
    'ch_ppocr_mobile_v2.0_cls_infer.onnx': 'e47acedf663230f8863ff1ab0e64dd2d82b838fceb5957146dab185a89d6215c',
}


def normalize_regions(rows, page: int, width: int, height: int):
    if len(rows) > 500 or width <= 0 or height <= 0:
        raise DomainError('too_large', 'OCR exceeds its region limit')
    blocks, issues = [], []
    for index, (points, text, score) in enumerate(rows):
        if (
            not isinstance(text, str)
            or len(text) > 4000
            or not math.isfinite(float(score))
            or not 0 <= score <= 1
            or len(points) != 4
        ):
            raise DomainError('invalid_input', 'OCR returned an invalid region')
        if any(len(p) != 2 or not all(math.isfinite(float(v)) for v in p) for p in points):
            raise DomainError('invalid_input', 'OCR returned invalid coordinates')
        xs, ys = [float(p[0]) for p in points], [float(p[1]) for p in points]
        if min(xs) < 0 or min(ys) < 0 or max(xs) > width or max(ys) > height:
            raise DomainError('invalid_input', 'OCR region exceeds page bounds')
        locator = f'page:{page}:ocr:{index + 1}'
        blocks.append(
            {
                'locator': locator,
                'text': text,
                'confidence': float(score),
                'region': [min(xs) / width, min(ys) / height, max(xs) / width, max(ys) / height],
                'value_type': 'untrusted_text',
            }
        )
        if score < 0.90:
            issues.append({'code': 'low_ocr_confidence', 'locator': locator})
    return {'blocks': blocks, 'issues': issues}


def extract_scanned(content: bytes, pages: list[int], engine=None):
    try:
        import pypdfium2 as pdfium  # type: ignore[import-untyped]
        import rapidocr_onnxruntime as rapid  # type: ignore[import-untyped]
    except ImportError:
        raise DomainError(
            'invalid_input', 'Scanned pages need the optional local OCR package'
        ) from None
    if len(pages) > 5:
        raise DomainError('too_large', 'OCR supports at most five scanned pages per document')
    if engine is None:
        root = Path(rapid.__file__).parent / 'models'
        for name, digest in MODELS.items():
            verified_bytes(root / name, digest)
        engine = rapid.RapidOCR(intra_op_num_threads=1, inter_op_num_threads=1)
    blocks, issues = [], []
    with pdfium.PdfDocument(content) as document:
        for number in pages:
            page = document[number - 1]
            try:
                width, height = page.get_size()
                if not 0 < width <= 2000 or not 0 < height <= 2000:
                    raise DomainError('too_large', 'Scanned page dimensions exceed the OCR limit')
                scale = min(2, (2000000 / (width * height)) ** 0.5)
                bitmap = page.render(scale=scale)
                try:
                    image = bitmap.to_pil()
                    try:
                        rows, _ = engine(image)
                        result = normalize_regions(rows or [], number, image.width, image.height)
                        blocks.extend(result['blocks'])
                        issues.extend(result['issues'])
                        if not result['blocks']:
                            issues.append({'code': 'no_ocr_text', 'locator': f'page:{number}'})
                    finally:
                        image.close()
                finally:
                    bitmap.close()
            finally:
                page.close()
    return {'blocks': blocks, 'issues': issues}
