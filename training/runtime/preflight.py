"""Measure before planning. Unknown CUDA runtime or memory fit blocks training launch."""

import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Hardware:
    name: str
    total_mib: int
    free_mib: int
    driver: str
    torch_version: str | None
    cuda_runtime: str | None
    cuda_available: bool


def measure():
    if os.environ.get('CUDA_VISIBLE_DEVICES') not in (None, '0'):
        return Hardware('unmapped CUDA selection', 0, 0, 'unknown', None, None, False)
    try:
        reply = subprocess.run(
            [
                'nvidia-smi',
                '--query-gpu=name,memory.total,memory.free,driver_version',
                '--format=csv,noheader,nounits',
            ],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
        records = [x.strip().split(',') for x in reply.stdout.splitlines() if x.strip()]
        if len(records) != 1:
            raise ValueError()
        name, total, free, driver = records[0]
        probe = subprocess.run(
            [
                sys.executable,
                '-c',
                "import json,torch; print(json.dumps({'torch':torch.__version__,'cuda':torch.version.cuda,'available':torch.cuda.is_available()}))",
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        runtime = json.loads(probe.stdout) if probe.returncode == 0 else {}
        return Hardware(
            name.strip(),
            int(total),
            int(free),
            driver.strip(),
            runtime.get('torch'),
            runtime.get('cuda'),
            runtime.get('available') is True,
        )
    except (OSError, ValueError, subprocess.SubprocessError):
        return Hardware('unavailable', 0, 0, 'unknown', None, None, False)


def assess(hardware: Hardware, *, parameters: int, activation_mib: int, reserve_mib: int = 1024):
    if (
        any(type(v) is not int or v < 0 for v in [parameters, activation_mib, reserve_mib])
        or not 1 <= parameters <= 10**12
    ):
        raise ValueError('Bounded explicit allocation estimates required')
    # Conservative full-parameter FP32/Adam plan: weights, gradients and two optimizer states.
    required = (parameters * 16 + 1048575) // 1048576 + activation_mib + reserve_mib
    reasons = []
    if not hardware.cuda_available or not hardware.cuda_runtime or not hardware.torch_version:
        reasons.append('unsupported_or_unmeasured_runtime')
    if not 0 <= hardware.free_mib <= hardware.total_mib or required > hardware.free_mib:
        reasons.append('insufficient_memory')
    return {
        'hardware': asdict(hardware),
        'estimated_peak_mib': required,
        'launch_allowed': not reasons,
        'reasons': reasons,
        'suggestion': 'Use a smaller parameter count, batch/context activation budget, or a separately measured adapter-training plan.'
        if reasons
        else 'Measure actual peak allocation during a bounded pilot before scaling.',
        'estimate_kind': 'full_parameter_fp32_adam',
        'parameters': parameters,
        'activation_mib': activation_mib,
        'reserve_mib': reserve_mib,
    }
