"""Bounded transport for trusted workers; this alone is not a native-code sandbox."""

import os
import subprocess
import threading
from pathlib import Path

from veya.domain.models import DomainError


def run_worker(
    command: list[str], payload: bytes, *, cwd: Path, timeout: float, maximum: int
) -> bytes:
    if not 0 < timeout <= 30 or not 0 < maximum <= 1048576:
        raise ValueError('Invalid worker limits')
    environment = {k: v for k, v in os.environ.items() if k.upper() in {'SYSTEMROOT', 'WINDIR'}}
    output = bytearray()
    exceeded = threading.Event()
    try:
        with subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env=environment,
            cwd=cwd,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
        ) as child:
            assert child.stdin is not None and child.stdout is not None

            def read():
                assert child.stdout is not None
                while block := child.stdout.read(4096):
                    if len(output) + len(block) > maximum:
                        exceeded.set()
                        child.kill()
                        break
                    output.extend(block)

            def write():
                assert child.stdin is not None
                try:
                    child.stdin.write(payload)
                    child.stdin.close()
                except (BrokenPipeError, OSError):
                    pass

            reader = threading.Thread(target=read, daemon=True)
            writer = threading.Thread(target=write, daemon=True)
            reader.start()
            writer.start()
            try:
                child.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
                raise DomainError('limit_exceeded', 'Worker exceeded its execution limit') from None
            finally:
                reader.join(timeout=2)
                writer.join(timeout=2)
            if exceeded.is_set() or child.returncode != 0 or reader.is_alive() or writer.is_alive():
                raise DomainError('limit_exceeded', 'Worker failed or exceeded its output limit')
    except OSError:
        raise DomainError('unavailable', 'Worker could not start') from None
    return bytes(output)
