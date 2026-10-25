"""Text-only PDF extraction. Offsets address the immutable extracted page text."""

import io

from pypdf import Configuration, PdfReader, apply_configuration

from veya.domain.models import DomainError

# Context-local parser ceilings apply before decoding any page or form stream.
LIMITS = Configuration(
    maximum_declared_stream_length=1048576,
    array_based_stream_maximum_output_length=1048576,
    lzw_maximum_output_length=1048576,
    run_length_maximum_output_length=1048576,
    zlib_maximum_output_length=1048576,
    brotli_maximum_output_length=1048576,
    jbig2_maximum_output_length=1048576,
    image_maximum_buffer_size=1048576,
    stream_decoding_work_maximum_length=4194304,
    stream_parsing_work_maximum_count=100000,
    page_tree_maximum_entries=200,
    xform_maximum_invocations_per_extraction=100,
    jbig2dec_binary=None,
)


def extract_pdf(content: bytes) -> dict:
    with apply_configuration(LIMITS):
        return _extract(content)


def _extract(content: bytes) -> dict:
    try:
        reader = PdfReader(io.BytesIO(content), strict=True)
        if reader.is_encrypted:
            raise DomainError('invalid_input', 'Encrypted PDFs must be unlocked before import')
        if len(reader.pages) > 100:
            raise DomainError('too_large', 'PDF exceeds 100 pages')
        blocks = []
        expanded = 0
        for page_number, page in enumerate(reader.pages, 1):
            stream = page.get_contents()
            expanded += len(stream.get_data()) if stream is not None else 0
            if expanded > 4194304:
                raise DomainError('too_large', 'PDF exceeds the expanded content limit')
            text = page.extract_text() or ''
            if len(text) > 100000:
                raise DomainError('too_large', 'PDF page text exceeds the extraction limit')
            offset = 0
            for line_number, line in enumerate(text.splitlines(keepends=True), 1):
                if line.strip():
                    blocks.append(
                        {
                            'locator': f'page:{page_number}:block:{line_number}',
                            'text': line.rstrip('\r\n'),
                            'start': offset,
                            'end': offset + len(line.rstrip('\r\n')),
                        }
                    )
                offset += len(line)
        if not blocks:
            raise DomainError(
                'invalid_input',
                'No selectable text found. Scanned PDFs need OCR, which is not available yet',
            )
        return {'blocks': blocks, 'issues': []}
    except DomainError:
        raise
    except Exception as error:
        raise DomainError(
            'invalid_input', 'PDF text could not be extracted; the file may be malformed'
        ) from error
