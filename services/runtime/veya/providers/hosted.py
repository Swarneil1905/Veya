"""The hosted adapter shares parsing but requires exact OpenAI destination and consent."""

from veya.domain.models import DomainError
from veya.providers.local import Adapter


class HostedAdapter(Adapter):
    def __init__(self, config, vault, **kwargs):
        if config.profile != 'remote':
            raise DomainError('invalid_input', 'Hosted adapter requires a remote profile')
        super().__init__(config, vault, **kwargs)
