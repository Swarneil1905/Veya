"""Bounded EML ingestion. Attachments inherit the immutable parent message grant."""

from email import policy
from email.parser import BytesParser
from email.utils import parsedate_to_datetime

from veya.domain.models import DomainError


def extract_email(content, *, validation_only=False):
    from veya.ingestion.intake import MAX_BYTES, validate
    from veya.ingestion.pdf import extract_pdf
    from veya.ingestion.tables import extract_table

    if len(content) > MAX_BYTES:
        raise DomainError('too_large', 'Email exceeds 512 KiB')
    message = BytesParser(policy=policy.default).parsebytes(content)
    if message.defects or not message.get('From') or not message.get('Date'):
        raise DomainError('invalid_input', 'Email requires valid sender and date headers')
    try:
        stamp = parsedate_to_datetime(str(message['Date']))
        if stamp.tzinfo is None:
            raise ValueError()
    except (ValueError, TypeError, OverflowError):
        raise DomainError('invalid_input', 'Email date must include a time zone') from None
    blocks: list[dict] = [
        {'locator': 'email:from', 'text': str(message['From'])[:1000]},
        {'locator': 'email:date', 'text': stamp.isoformat()},
        {'locator': 'email:subject', 'text': str(message.get('Subject', ''))[:1000]},
    ]
    issues: list[dict] = []
    count = 0
    names = set()
    expanded = 0

    def visit(part, depth):
        nonlocal count, expanded
        count += 1
        if count > 32 or depth > 3 or part.defects or part.get_content_type() == 'message/rfc822':
            raise DomainError(
                'invalid_input', 'Nested, malformed or excessive email parts are unsupported'
            )
        if part.is_multipart():
            for child in part.iter_parts():
                visit(child, depth + 1)
            return
        data = part.get_payload(decode=True)
        if part.defects:
            raise DomainError('invalid_input', 'Email payload is malformed')
        if data is None:
            raise DomainError('invalid_input', 'Email part has no supported payload')
        expanded += len(data)
        if expanded > MAX_BYTES:
            raise DomainError('too_large', 'Decoded email parts exceed 512 KiB')
        name = part.get_filename()
        if name:
            if name in names or name.lower().endswith('.eml'):
                raise DomainError(
                    'invalid_input', 'Duplicate or nested email attachments are unsupported'
                )
            names.add(name)
            kind = validate(name, data)
            if validation_only:
                return
            result = extract_pdf(data) if kind == 'pdf' else extract_table(kind, data)
            prefix = 'attachment:' + name + '/'
            blocks.extend({**b, 'locator': prefix + b['locator']} for b in result['blocks'])
            issues.extend({**i, 'locator': prefix + i['locator']} for i in result['issues'])
        elif part.get_content_type() == 'text/plain':
            try:
                text = data.decode(part.get_content_charset() or 'utf-8', errors='strict')
            except (UnicodeError, LookupError):
                raise DomainError('invalid_input', 'Email body encoding is unsupported') from None
            if len(text) > 100000:
                raise DomainError('too_large', 'Email body exceeds the text limit')
            for start in range(0, len(text), 4000):
                blocks.append(
                    {
                        'locator': f'email:body:{count}:{start}',
                        'text': text[start : start + 4000],
                        'start': start,
                        'end': min(start + 4000, len(text)),
                    }
                )
        elif part.get_content_type() == 'text/html':
            issues.append({'code': 'html_body_not_rendered', 'locator': 'email:body'})
        else:
            raise DomainError('invalid_input', 'Unsupported unnamed email part')

    visit(message, 0)
    if len(blocks) > 10000:
        raise DomainError('too_large', 'Email has too many source blocks')
    return {'blocks': blocks, 'issues': issues}
