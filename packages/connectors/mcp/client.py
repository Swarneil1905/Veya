"""Pinned 2025-11-25 JSON transport profile with pre-registered typed tool mappings.

SSE, server-initiated requests, dynamic tools and newer protocol versions fail closed.
The host owns transport authentication and policy; no arbitrary stdio subprocesses.
"""

import asyncio
import json

from veya.domain.models import DomainError
from veya.security.boundaries import https_request
from veya.tools.contracts import canonical_json
from veya.tools.execution import ToolBinding
from veya.tools.registry import ToolRegistry, ToolScope

VERSION = '2025-11-25'


class HTTPTransport:
    def __init__(self, endpoint, credential):
        self.endpoint, self.credential = endpoint, credential

    async def __call__(self, message):
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json, text/event-stream',
            'MCP-Protocol-Version': VERSION,
            'Authorization': 'Bearer ' + self.credential(),
        }
        result = await asyncio.to_thread(
            https_request, self.endpoint, canonical_json(message, 1048576).encode(), headers
        )
        return json.loads(result) if result else None


class MCPClient:
    def __init__(self, transport, definitions, require_connection):
        self.transport, self.require_connection = transport, require_connection
        self.registry = ToolRegistry()
        self.definitions = {tool.name: tool for tool in definitions}
        for tool in definitions:
            self.registry.register(tool)
        self.ready, self.sequence = False, 0

    async def request(self, method, params):
        self.require_connection()
        self.sequence += 1
        request_id = self.sequence
        result = await asyncio.wait_for(
            self.transport(
                {'jsonrpc': '2.0', 'id': request_id, 'method': method, 'params': params}
            ),
            10,
        )
        canonical_json(result, 1048576)
        if (
            not isinstance(result, dict)
            or result.get('jsonrpc') != '2.0'
            or result.get('id') != request_id
            or 'error' in result
            or not isinstance(result.get('result'), dict)
        ):
            raise DomainError('invalid_input', 'MCP response does not match the request')
        return result['result']

    async def discover(self):
        self.ready = False
        hello = await self.request(
            'initialize',
            {
                'protocolVersion': VERSION,
                'capabilities': {},
                'clientInfo': {'name': 'Veya', 'version': '0.1.0'},
            },
        )
        if hello.get('protocolVersion') != VERSION or 'tools' not in hello.get('capabilities', {}):
            raise DomainError('invalid_input', 'Unsupported MCP server profile')
        await asyncio.wait_for(
            self.transport({'jsonrpc': '2.0', 'method': 'notifications/initialized'}), 10
        )
        discovered = {}
        cursor = None
        for _ in range(10):
            page = await self.request('tools/list', {} if cursor is None else {'cursor': cursor})
            if not isinstance(page.get('tools'), list) or len(page['tools']) > 100:
                raise DomainError('too_large', 'Invalid MCP tool catalog')
            for item in page['tools']:
                if (
                    not isinstance(item, dict)
                    or not isinstance(item.get('name'), str)
                    or item['name'] in discovered
                ):
                    raise DomainError('invalid_input', 'Invalid MCP tool declaration')
                discovered[item['name']] = item
            cursor = page.get('nextCursor')
            if cursor is None:
                break
            if not isinstance(cursor, str) or len(cursor) > 1000:
                raise DomainError('invalid_input', 'Invalid MCP pagination cursor')
        else:
            raise DomainError('too_large', 'MCP tool discovery exceeded its page limit')
        for name, tool in self.definitions.items():
            remote = discovered.get(name, {})
            if (
                remote.get('inputSchema') != tool.input_model.model_json_schema()
                or remote.get('outputSchema') != tool.output_model.model_json_schema()
            ):
                raise DomainError('conflict', 'MCP schemas differ from the approved mapping')
        # Description, annotations, instructions, and additional discovered tools are untrusted.
        self.ready = True
        return tuple(self.definitions)

    def binding(self, name, resources, operation):
        tool = self.definitions[name]

        async def invoke(args):
            if not self.ready:
                raise DomainError('unavailable', 'Discover the approved MCP tools first')
            scope = ToolScope('mcp_host', frozenset({name}), tool.capabilities)
            validated = self.registry.arguments(scope, name, tool.version, args)
            result = await self.request('tools/call', {'name': name, 'arguments': validated})
            if result.get('isError') or 'structuredContent' not in result:
                raise DomainError(
                    'unavailable', 'MCP tool did not return a successful typed result'
                )
            return self.registry.output(scope, name, tool.version, result['structuredContent'])

        return ToolBinding(name, tool.version, operation, resources, invoke)
