"""Create-only TRL conversational SFT export from the reviewed, scrubbed corpus.

Callers supply a local tokenizer with a pinned template. No training or model promotion occurs.
"""

import hashlib
import json
import tempfile
from pathlib import Path

from veya.privacy.scanning import require_clean
from veya.tools.contracts import canonical_json

from training.data.export import export
from training.data.manifest import Manifest, validate_current


def conversation(trace):
    messages, approvals = [], []
    pending = None
    for event in trace['events']:
        kind = event['kind']
        if kind == 'start':
            if messages or not event['content']:
                raise ValueError('One nonempty user request is required')
            messages.append({'role': 'user', 'content': event['content']})
        elif kind == 'proposal':
            if pending or not event.get('operation'):
                raise ValueError('Parallel or unnamed tool proposals are unsupported')
            try:
                arguments = json.loads(event['content'])
            except ValueError:
                raise ValueError('Tool arguments must be structured JSON') from None
            if type(arguments) is not dict:
                raise ValueError('Tool arguments must be an object')
            pending = {
                'id': f'call_{event["sequence"]}',
                'type': 'function',
                'function': {'name': event['operation'], 'arguments': arguments},
            }
            messages.append({'role': 'assistant', 'tool_calls': [pending]})
        elif kind == 'approval':
            if pending is None or not event['approved']:
                raise ValueError('Missing or rejected approval cannot enter a demonstration')
            approvals.append(event['sequence'])
        elif kind == 'tool':
            if pending is None or event['operation'] != pending['function']['name']:
                raise ValueError('Tool result has no matching proposal')
            messages.append(
                {
                    'role': 'tool',
                    'tool_call_id': pending['id'],
                    'name': event['operation'],
                    'content': event['content'],
                }
            )
            pending = None
        elif kind == 'finish':
            if pending or not event['content']:
                raise ValueError('Incomplete actions or empty completions cannot be exported')
            messages.append({'role': 'assistant', 'content': event['content']})
        else:
            raise ValueError('Unsupported trajectory event')
    if (
        pending
        or len(messages) < 2
        or messages[0]['role'] != 'user'
        or messages[-1]['role'] != 'assistant'
    ):
        raise ValueError('Incomplete conversation')
    return messages, approvals


def tokenizer_digest(tokenizer):
    serialized = json.dumps(
        {'backend': tokenizer.backend_tokenizer.to_str(), 'template': tokenizer.chat_template},
        sort_keys=True,
        ensure_ascii=False,
    )
    if len(serialized.encode()) > 24000000:
        raise ValueError('Tokenizer identity exceeds the supported size')
    return hashlib.sha256(serialized.encode()).hexdigest()


def tokenize(messages, tokenizer, *, max_tokens):
    template = tokenizer.chat_template
    if not isinstance(template, str) or not template.strip() or not 32 <= max_tokens <= 131072:
        raise ValueError('Select a bounded context and explicit chat template')
    rendered = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=False)
    ids = tokenizer.apply_chat_template(
        messages, tokenize=True, add_generation_prompt=False, return_dict=False
    )
    if (
        not isinstance(rendered, str)
        or not isinstance(ids, list)
        or not ids
        or len(ids) > max_tokens
    ):
        raise ValueError('Tokenization failed or critical actions would be truncated')
    decoded = tokenizer.decode(ids, skip_special_tokens=False, clean_up_tokenization_spaces=False)
    if decoded != rendered:
        raise ValueError('Selected tokenizer/template does not round-trip')
    for message in messages:
        if 'tool_calls' in message:
            for call in message['tool_calls']:
                if call['function']['name'] not in rendered or 'tool_call' not in rendered:
                    raise ValueError('Selected template does not support tool calls')
                if json.dumps(call['function']['arguments'], ensure_ascii=False) not in rendered:
                    raise ValueError('Selected template omitted or changed critical tool arguments')
        elif message.get('content') and message['content'] not in rendered:
            raise ValueError('Selected template omitted conversation content')
    return ids, hashlib.sha256(template.encode()).hexdigest()


def export_trl(
    store,
    path: Path,
    ids: tuple[str, ...],
    *,
    rules,
    held_out,
    tokenizer,
    tokenizer_revision: str,
    max_tokens: int,
):
    if len(tokenizer_revision) != 64 or any(
        c not in '0123456789abcdef' for c in tokenizer_revision
    ):
        raise ValueError('Pin the local tokenizer files with a SHA-256 revision')
    if tokenizer_digest(tokenizer) != tokenizer_revision:
        raise ValueError('Tokenizer or chat template differs from the pinned identity')
    with tempfile.TemporaryDirectory(prefix='veya-corpus-', dir=path.parent) as temporary:
        corpus_path = Path(temporary) / 'corpus.json'
        export(store, corpus_path, ids, rules=rules, held_out=held_out)
        corpus = json.loads(corpus_path.read_text())
        manifest = Manifest.model_validate_json(json.dumps(corpus['manifest']))
        rows = []
        for record in corpus['records']:
            messages, approvals = conversation(record)
            tokens, template_hash = tokenize(messages, tokenizer, max_tokens=max_tokens)
            rows.append(
                {
                    'messages': messages,
                    'metadata': {
                        'trajectory_id': record['id'],
                        'tokenizer_sha256': tokenizer_revision,
                        'template_sha256': template_hash,
                        'token_count': len(tokens),
                        'approval_sequences': approvals,
                        'source_ids': record['source_ids'],
                        'manifest': corpus['manifest'],
                        'synthetic': record['source'] == 'synthetic',
                    },
                }
            )
        payload = ''.join(canonical_json(row, 1048576) + '\n' for row in rows)
        if len(payload.encode()) > 16777216:
            raise ValueError('Training export exceeds the byte budget')
        require_clean(payload.encode())
        with store.db.transaction():
            validate_current(store, manifest)
            with path.open('x', encoding='utf8', newline='\n') as output:
                output.write(payload)
    return {
        'rows': len(rows),
        'format': 'trl_conversational_sft',
        'sha256': hashlib.sha256(payload.encode()).hexdigest(),
        'trained': False,
    }
