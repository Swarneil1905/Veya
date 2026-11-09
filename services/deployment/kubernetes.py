"""Explicit kubectl adapter; no cluster creation, image builds, or mutable image tags."""

import json
import re
import subprocess

from scripts.render_team_deployment import render


class KubernetesTarget:
    def __init__(self, *, context, namespaces, secrets, deployment, image_repository, timeout=180):
        if not context or set(namespaces) != {'test', 'staging'}:
            raise ValueError('Explicit context and test/staging namespaces are required')
        if set(secrets) != {'test', 'staging'} or deployment != 'veya-team':
            raise ValueError('Team deployment and explicit environment secret names required')
        for name in [deployment, *namespaces.values(), *secrets.values()]:
            if not re.fullmatch('[a-z][a-z0-9-]{0,62}', name):
                raise ValueError('Invalid Kubernetes resource name')
        if not re.fullmatch('[a-z0-9./:_-]+', image_repository) or '@' in image_repository:
            raise ValueError('A configured image repository is required')
        if type(timeout) is not int or not 1 <= timeout <= 600:
            raise ValueError('Bounded rollout timeout required')
        self.context, self.namespaces = context, namespaces
        self.secrets = secrets
        self.deployment, self.image_repository, self.timeout = deployment, image_repository, timeout

    def _run(self, environment, *args, content=None):
        if environment not in self.namespaces:
            raise ValueError('Unknown deployment environment')
        reply = subprocess.run(
            [
                'kubectl',
                '--context',
                self.context,
                '--namespace',
                self.namespaces[environment],
                *args,
            ],
            capture_output=True,
            input=content,
            text=True,
            timeout=self.timeout + 10,
            check=False,
        )
        if reply.returncode or len(reply.stdout) > 1048576:
            raise RuntimeError('Kubernetes operation failed; inspect the configured cluster')
        return reply.stdout

    def deploy(self, environment, digest):
        if not re.fullmatch('sha256:[0-9a-f]{64}', digest):
            raise ValueError('Immutable artifact digest required')
        image = self.image_repository + '@' + digest
        if self.observe(environment) == {'absent': True}:
            manifest = render(image, self.namespaces[environment], self.secrets[environment])
            self._run(environment, 'apply', '-f', '-', content=json.dumps(manifest))
        else:
            self._run(
                environment,
                'set',
                'image',
                'deployment/' + self.deployment,
                'team=' + image,
            )
        self._run(
            environment,
            'rollout',
            'status',
            'deployment/' + self.deployment,
            '--timeout=' + str(self.timeout) + 's',
        )

    def observe(self, environment):
        raw = self._run(
            environment,
            'get',
            'deployment',
            self.deployment,
            '-o',
            'json',
            '--ignore-not-found=true',
        )
        # A successful empty response means NotFound. API failures still raise.
        if not raw.strip():
            return {'absent': True}
        value = json.loads(raw)
        spec, status = value['spec'], value.get('status', {})
        containers = spec['template']['spec']['containers']
        images = [c['image'] for c in containers if c['name'] == 'team']
        prefix = self.image_repository + '@'
        if len(images) != 1 or not images[0].startswith(prefix):
            raise ValueError('Deployment does not use the configured image repository')
        digest = images[0][len(prefix) :]
        if not re.fullmatch('sha256:[0-9a-f]{64}', digest):
            raise ValueError('Deployment image identity is mutable')
        desired = spec.get('replicas', 1)
        healthy = (
            desired > 0
            and status.get('observedGeneration', 0) >= value['metadata']['generation']
            and status.get('updatedReplicas', 0) == desired
            and status.get('readyReplicas', 0) == desired
            and status.get('availableReplicas', 0) == desired
            and status.get('replicas', 0) == desired
        )
        return {'digest': digest, 'healthy': healthy}
