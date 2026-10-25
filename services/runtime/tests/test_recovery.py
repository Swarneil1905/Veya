import asyncio

import pytest
from test_approvals import approved_gateway
from test_tool_registry import scope

from veya.recovery import status
from veya.storage.sqlite import Database


def test_uncertain_write_survives_restart_without_redispatch(tmp_path):
    executor, actor, proposal, _, _, calls, _, _, _, receipt = approved_gateway(tmp_path)
    binding = next(iter(executor.bindings.values()))
    from dataclasses import replace

    async def uncertain(arguments):
        calls.append(arguments)
        raise ConnectionError('response lost after remote effect')

    executor.bindings[(binding.name, binding.version)] = replace(binding, handler=uncertain)
    # Receipt binds the original operation key; use that exact identity.
    import json

    key = json.loads(receipt.body_json)['operation_key']
    with pytest.raises(ConnectionError):
        asyncio.run(executor.execute(actor, scope(), key, proposal.id, approval_id=receipt.id))
    assert status(Database(tmp_path), actor.tenant_id)['uncertain_operations'] == [
        {'operation_key': key, 'run_id': proposal.run_id}
    ]
    assert status(Database(tmp_path), 'fixture_other')['uncertain_operations'] == []
    asyncio.run(executor.execute(actor, scope(), key, proposal.id, approval_id=receipt.id))
    assert len(calls) == 1
