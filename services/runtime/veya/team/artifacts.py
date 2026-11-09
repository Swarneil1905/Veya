"""Bounded S3 artifacts addressed by tenant and content digest.

The SDK client is configured by the trusted host. No user-selected endpoints,
bucket names, filesystem paths, or object keys enter this interface.
"""

import base64
import hashlib
import re


class RemoteArtifacts:
    def __init__(self, client, bucket, membership, *, maximum_bytes):
        if not re.fullmatch('[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]', bucket):
            raise ValueError('A configured object-storage bucket is required')
        if type(maximum_bytes) is not int or not 1 <= maximum_bytes <= 64 * 1048576:
            raise ValueError('Explicit artifact size limit required')
        self.client, self.bucket, self.membership = client, bucket, membership
        self.maximum_bytes = maximum_bytes

    def _key(self, digest):
        if not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}', digest):
            raise ValueError('Artifact reference must be a SHA-256 digest')
        return f'tenants/{self.membership.tenant}/artifacts/{digest}'

    def put(self, content):
        self.membership.require('submit')
        if not isinstance(content, bytes) or not 1 <= len(content) <= self.maximum_bytes:
            raise ValueError('Artifact exceeds its configured byte limit')
        digest = hashlib.sha256(content).hexdigest()
        checksum = base64.b64encode(bytes.fromhex(digest)).decode()
        self.client.put_object(
            Bucket=self.bucket,
            Key=self._key(digest),
            Body=content,
            ContentLength=len(content),
            ChecksumSHA256=checksum,
            ContentType='application/octet-stream',
        )
        # Do not acknowledge a write on the strength of an ETag, which may be a
        # multipart or encrypted-object identity rather than a content checksum.
        if self.read(digest) != content:
            raise ValueError('Stored artifact did not match the submitted content')
        return {'sha256': digest, 'size': len(content)}

    def read(self, digest):
        self.membership.require('read')
        reply = self.client.get_object(Bucket=self.bucket, Key=self._key(digest))
        stream = reply['Body']
        try:
            size = reply['ContentLength']
            if type(size) is not int or not 1 <= size <= self.maximum_bytes:
                raise ValueError('Stored artifact exceeds its configured byte limit')
            content = stream.read(self.maximum_bytes + 1)
            if len(content) != size or hashlib.sha256(content).hexdigest() != digest:
                raise ValueError('Stored artifact failed integrity verification')
            return content
        finally:
            stream.close()

    def download_url(self, digest, *, expires_seconds=60):
        self.membership.require('read')
        if type(expires_seconds) is not int or not 1 <= expires_seconds <= 300:
            raise ValueError('Download expiry must be between 1 and 300 seconds')
        # Recheck object scope and integrity before issuing a short-lived capability.
        self.read(digest)
        return self.client.generate_presigned_url(
            'get_object',
            Params={'Bucket': self.bucket, 'Key': self._key(digest)},
            ExpiresIn=expires_seconds,
        )
