"""Single-runtime process admission. Reject excess work before buffering request bodies."""

from threading import Lock

from fastapi.responses import JSONResponse


class Admission:
    def __init__(self, app, telemetry, capacity=32):
        if type(capacity) is not int or not 1 <= capacity <= 256:
            raise ValueError('Invalid admission capacity')
        self.app, self.telemetry, self.capacity = app, telemetry, capacity
        self.active, self.lock = 0, Lock()

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        with self.lock:
            accepted = self.active < self.capacity
            if accepted:
                self.active += 1
        if not accepted:
            self.telemetry.metrics.rejections.inc()
            self.telemetry.metrics.record('runtime', 'rejected', 0)
            await JSONResponse(
                {
                    'error': {
                        'code': 'busy',
                        'message': 'Runtime capacity reached; retry later',
                        'schema_version': 1,
                        'retryable': True,
                    }
                },
                status_code=503,
                headers={'Retry-After': '1'},
            )(scope, receive, send)
            return
        try:
            self.telemetry.metrics.queue_delay.observe(0)
            await self.app(scope, receive, send)
        finally:
            with self.lock:
                self.active -= 1
