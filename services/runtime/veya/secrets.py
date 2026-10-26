"""Windows Credential Manager for exact Veya/workspace/provider targets only.
No enumeration and no renderer read endpoint. Other platforms fail closed.
"""

import ctypes
import hashlib
import os
import re
from ctypes import wintypes

from veya.domain.models import DomainError


class Credential(ctypes.Structure):
    _fields_ = [
        ('Flags', wintypes.DWORD),
        ('Type', wintypes.DWORD),
        ('TargetName', wintypes.LPWSTR),
        ('Comment', wintypes.LPWSTR),
        ('LastWritten', wintypes.FILETIME),
        ('CredentialBlobSize', wintypes.DWORD),
        ('CredentialBlob', ctypes.POINTER(ctypes.c_ubyte)),
        ('Persist', wintypes.DWORD),
        ('AttributeCount', wintypes.DWORD),
        ('Attributes', ctypes.c_void_p),
        ('TargetAlias', wintypes.LPWSTR),
        ('UserName', wintypes.LPWSTR),
    ]


class Vault:
    def __init__(self, root, tenant):
        self.scope = hashlib.sha256((str(root.resolve()) + ':' + tenant).encode()).hexdigest()[:32]

    def _target(self, reference):
        if not isinstance(reference, str) or not re.fullmatch(
            r'vault:[a-zA-Z0-9_-]{1,64}', reference
        ):
            raise DomainError('invalid_input', 'Use a Veya credential reference')
        return 'Veya/provider/' + self.scope + '/' + reference[6:]

    def _api(self):
        if os.name != 'nt':
            raise DomainError(
                'vault_unavailable', 'Credential storage requires Windows Credential Manager'
            )
        api = getattr(ctypes, 'WinDLL')('Advapi32.dll', use_last_error=True)
        api.CredWriteW.argtypes = [ctypes.POINTER(Credential), wintypes.DWORD]
        api.CredWriteW.restype = wintypes.BOOL
        api.CredReadW.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            ctypes.POINTER(ctypes.POINTER(Credential)),
        ]
        api.CredReadW.restype = wintypes.BOOL
        api.CredFree.argtypes = [ctypes.c_void_p]
        api.CredDeleteW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
        api.CredDeleteW.restype = wintypes.BOOL
        return api

    def save(self, reference, secret):
        target = self._target(reference)
        if (
            type(secret) is not str
            or not 1 <= len(secret.encode()) <= 2048
            or any(ord(c) <= 32 or ord(c) > 126 for c in secret)
        ):
            raise DomainError('invalid_input', 'Credential must be a bounded printable token')
        api = self._api()
        content = (ctypes.c_ubyte * len(secret)).from_buffer_copy(secret.encode())
        value = Credential(
            Type=1,
            TargetName=target,
            CredentialBlobSize=len(content),
            CredentialBlob=content,
            Persist=2,
            UserName='Veya',
        )
        try:
            if not api.CredWriteW(ctypes.byref(value), 0):
                raise DomainError('vault_unavailable', 'Credential could not be saved')
        finally:
            ctypes.memset(content, 0, len(content))

    def read(self, reference):
        target, api = self._target(reference), self._api()
        pointer = ctypes.POINTER(Credential)()
        if not api.CredReadW(target, 1, 0, ctypes.byref(pointer)):
            raise DomainError(
                'credential_missing', 'Save the provider credential before connecting'
            )
        try:
            size = pointer.contents.CredentialBlobSize
            if not 1 <= size <= 2048:
                raise DomainError('credential_missing', 'Provider credential is invalid')
            return ctypes.string_at(pointer.contents.CredentialBlob, size).decode('ascii')
        finally:
            api.CredFree(pointer)

    def remove(self, reference):
        target, api = self._target(reference), self._api()
        if not api.CredDeleteW(target, 1, 0) and getattr(ctypes, 'get_last_error')() != 1168:
            raise DomainError('vault_unavailable', 'Credential could not be removed')
