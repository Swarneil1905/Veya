"""Bounded local load scenario against the real ASGI admission middleware."""

import asyncio

from veya.observability.admission import Admission
from veya.observability.tracing import Telemetry


async def run(*, requests=100, capacity=8):
    if not 1 <= requests <= 1000 or not 1 <= capacity < requests:
        raise ValueError('Bound the declared load above capacity')
    release = asyncio.Event()
    outcomes = []
    telemetry = Telemetry()

    async def slow_provider(scope, receive, send):
        await release.wait()
        await send({'type': 'http.response.start', 'status': 200, 'headers': []})

    async def receive():
        return {'type': 'http.request', 'body': b'', 'more_body': False}

    async def send(message):
        if message['type'] == 'http.response.start':
            outcomes.append(message['status'])

    gate = Admission(slow_provider, telemetry, capacity)
    attempts = [asyncio.create_task(gate({'type': 'http'}, receive, send)) for _ in range(requests)]
    await asyncio.sleep(0)
    peak = gate.active
    release.set()
    await asyncio.gather(*attempts)
    await gate({'type': 'http'}, receive, send)
    return {
        'requests': requests,
        'capacity': capacity,
        'peak_admitted': peak,
        'succeeded': outcomes[:-1].count(200),
        'rejected': outcomes[:-1].count(503),
        'recovered': outcomes[-1] == 200,
        'queued': 0,
    }
