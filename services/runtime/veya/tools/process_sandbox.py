"""Capability-limited WASI runner. Native code and ambient network access are unsupported."""

import asyncio
import base64
import json
import sys
import tempfile
from pathlib import Path

from veya.domain.models import DomainError
from veya.security.plugins import PluginApproval
from veya.security.process import run_worker
from veya.tools.execution import ToolBinding


def binding(definition, module_path: Path, approval: PluginApproval, resources, inputs):
    """Host registration plugs isolated execution into the existing approval/budget gateway."""

    async def invoke(arguments):
        output = await asyncio.to_thread(
            execute,
            module_path,
            approval,
            version=definition.version,
            capabilities=definition.capabilities,
            inputs=inputs(arguments),
            payload=json.dumps(arguments, allow_nan=False).encode(),
            maximum=definition.max_output_bytes,
        )
        try:
            value = json.loads(output)
        except ValueError:
            raise DomainError('invalid_input', 'Plugin output must be a JSON object') from None
        if type(value) is not dict:
            raise DomainError('invalid_input', 'Plugin output must be a JSON object')
        return value

    return ToolBinding(
        definition.name,
        definition.version,
        'read' if definition.effect.value == 'read_only' else 'write',
        resources,
        invoke,
    )


def execute(
    path: Path,
    approval: PluginApproval,
    *,
    version: str,
    capabilities: frozenset[str],
    inputs: dict[str, bytes],
    payload: bytes = b'',
    timeout: float = 5,
    maximum: int = 65536,
) -> bytes:
    module = approval.load(path, version=version, capabilities=capabilities)
    if (
        len(inputs) > 16
        or sum(len(data) for data in inputs.values()) > 524288
        or len(payload) > 65536
    ):
        raise DomainError('too_large', 'Tool inputs exceed the sandbox limit')
    if inputs and 'read_inputs' not in capabilities:
        raise DomainError('forbidden', 'Input read capability is required')
    for name in inputs:
        if (
            not name
            or len(name) > 100
            or any(
                c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.'
                for c in name
            )
            or name in {'.', '..'}
        ):
            raise DomainError('forbidden', 'Input must have a simple filename')
    source = Path(__file__).resolve().parents[2]
    code = 'import sys; sys.path.insert(0,sys.argv[1]); from veya.tools.process_sandbox import main; main()'
    with tempfile.TemporaryDirectory(prefix='veya-tool-') as folder:
        root = Path(folder)
        data_dir = root / 'inputs'
        data_dir.mkdir()
        for name, content in inputs.items():
            (data_dir / name).write_bytes(content)
        request = json.dumps(
            {
                'module': base64.b64encode(module).decode(),
                'stdin': base64.b64encode(payload).decode(),
                'root': str(data_dir),
            }
        ).encode()
        return run_worker(
            [sys.executable, '-I', '-c', code, str(source)],
            request,
            cwd=root,
            timeout=timeout,
            maximum=maximum,
        )


def main() -> None:
    import wasmtime

    request = json.loads(sys.stdin.buffer.read(24000000))
    config = wasmtime.Config()
    config.consume_fuel = True
    engine = wasmtime.Engine(config)
    store = wasmtime.Store(engine)
    store.set_fuel(10000000)
    store.set_limits(memory_size=16777216, table_elements=1024, instances=1, tables=1, memories=1)
    wasi = wasmtime.WasiConfig()
    wasi.argv = ['tool']
    # No environment or inherited descriptors. WASI has only this read-only input directory.
    wasi.preopen_dir(request['root'], '/inputs', fs_mutable=False)
    stdin = Path(request['root']).parent / 'stdin'
    stdin.write_bytes(base64.b64decode(request['stdin'], validate=True))
    wasi.stdin_file = str(stdin)
    wasi.inherit_stdout()
    store.set_wasi(wasi)
    linker = wasmtime.Linker(engine)
    linker.define_wasi()
    module = wasmtime.Module(engine, base64.b64decode(request['module'], validate=True))
    instance = linker.instantiate(store, module)
    start = instance.exports(store)['_start']
    assert isinstance(start, wasmtime.Func)
    try:
        start(store)
    except wasmtime.ExitTrap as exit_status:
        if exit_status.code != 0:
            raise
