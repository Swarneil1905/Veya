"""Allowlisted structured records, before every configured sink; never stringify exceptions."""

import json
import logging
import re
from collections import deque
from datetime import datetime, timezone
from threading import Lock


class SafeLogs:
    def __init__(self, capacity=500):
        if type(capacity) is not int or not 1 <= capacity <= 2000:
            raise ValueError('Bound log storage')
        self.records: deque[dict] = deque(maxlen=capacity)
        self.lock = Lock()

    def emit(self, *, event, source, outcome, trace_id, span_id, duration_ms, **discarded):
        if (
            event != 'operation.completed'
            or source not in {'runtime', 'provider', 'connector', 'finance'}
            or outcome not in {'succeeded', 'failed', 'cancelled', 'unknown', 'rejected'}
        ):
            raise ValueError('Unrecognized structured log event')
        if not re.fullmatch('[0-9a-f]{32}', trace_id) or not re.fullmatch('[0-9a-f]{16}', span_id):
            raise ValueError('Invalid correlation identity')
        if type(duration_ms) is not int or not 0 <= duration_ms <= 86_400_000:
            raise ValueError('Invalid duration')
        record = dict(
            timestamp=datetime.now(timezone.utc).isoformat(),
            event=event,
            source=source,
            outcome=outcome,
            trace_id=trace_id,
            span_id=span_id,
            duration_ms=duration_ms,
        )
        with self.lock:
            self.records.append(record)

    def snapshot(self):
        with self.lock:
            return json.loads(json.dumps(list(self.records)))


class ServerRedaction(logging.Filter):
    """Uvicorn's process sink must not serialize raw exception messages."""

    def filter(self, record):
        record.msg = 'Runtime server event'
        record.args = ()
        record.exc_info = None
        record.exc_text = None
        record.stack_info = None
        return True


SERVER_LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'filters': {'safe': {'()': ServerRedaction}},
    'formatters': {'safe': {'format': '%(levelname)s %(message)s'}},
    'handlers': {
        'safe': {
            'class': 'logging.StreamHandler',
            'stream': 'ext://sys.stderr',
            'filters': ['safe'],
            'formatter': 'safe',
        }
    },
    'loggers': {
        'uvicorn': {'handlers': ['safe'], 'level': 'WARNING', 'propagate': False},
        'uvicorn.error': {'handlers': ['safe'], 'level': 'WARNING', 'propagate': False},
        'uvicorn.access': {'handlers': [], 'propagate': False},
    },
}
