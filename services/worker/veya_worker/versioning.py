"""Workflow type names are immutable history contracts."""

CONTRACT_VERSION = 1
WORKFLOW_TYPE = 'VeyaTaskV1'
TASK_QUEUE = 'veya-fixtures-v1'


def validate_version(version):
    if type(version) is not int or version != CONTRACT_VERSION:
        raise ValueError('Unsupported worker/runtime contract version')
