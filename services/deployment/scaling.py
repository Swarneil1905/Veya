"""Plan replica counts under a shared provider budget; invalid telemetry holds capacity."""

import math


def desired_replicas(*, backlog, current, minimum, maximum, concurrent_per_worker, provider_limit):
    values = [current, minimum, maximum, concurrent_per_worker, provider_limit]
    if any(type(value) is not int for value in values):
        raise ValueError('Integer resource limits required')
    if not 0 <= minimum <= maximum or concurrent_per_worker < 1 or provider_limit < 1:
        raise ValueError('Invalid worker capacity policy')
    ceiling = min(maximum, provider_limit // concurrent_per_worker)
    if ceiling < minimum:
        raise ValueError('Minimum workers exceed the provider concurrency limit')
    if type(backlog) is not int or backlog < 0:
        return {'replicas': min(max(current, minimum), ceiling), 'reason': 'telemetry_unavailable'}
    desired = max(minimum, math.ceil(backlog / concurrent_per_worker))
    return {'replicas': min(desired, ceiling), 'reason': 'bounded_backlog'}
