"""Render a private Kubernetes team-service deployment; never apply or provision resources."""

import argparse
import json
import re


def render(image, namespace, secret):
    if not re.fullmatch(r'[a-z0-9./:_-]+@sha256:[0-9a-f]{64}', image):
        raise ValueError('An immutable reviewed container image is required')
    for value in [namespace, secret]:
        if not re.fullmatch('[a-z][a-z0-9-]{0,62}', value):
            raise ValueError('Explicit namespace and secret names required')
    label = {'app': 'veya-team'}
    security = dict(
        runAsNonRoot=True,
        runAsUser=10001,
        runAsGroup=10001,
        seccompProfile={'type': 'RuntimeDefault'},
    )
    probe = {'exec': {'command': ['python', '-m', 'veya.team.health']}, 'timeoutSeconds': 7}
    deployment = {
        'apiVersion': 'apps/v1',
        'kind': 'Deployment',
        'metadata': {'name': 'veya-team', 'namespace': namespace},
        'spec': {
            'replicas': 1,
            'selector': {'matchLabels': label},
            'template': {
                'metadata': {'labels': label},
                'spec': {
                    'automountServiceAccountToken': False,
                    'securityContext': security,
                    'containers': [
                        {
                            'name': 'team',
                            'image': image,
                            'ports': [{'containerPort': 8080}],
                            'env': [
                                {
                                    'name': name,
                                    'valueFrom': {'secretKeyRef': {'name': secret, 'key': key}},
                                }
                                for name, key in [
                                    ('VEYA_TEAM_DATABASE_URL', 'database-url'),
                                    ('VEYA_TEAM_GATEWAY_TOKEN', 'gateway-token'),
                                ]
                            ],
                            'securityContext': {
                                'allowPrivilegeEscalation': False,
                                'readOnlyRootFilesystem': True,
                                'capabilities': {'drop': ['ALL']},
                            },
                            'resources': {
                                'requests': {'cpu': '100m', 'memory': '128Mi'},
                                'limits': {'cpu': '1', 'memory': '512Mi'},
                            },
                            'readinessProbe': probe | {'periodSeconds': 10},
                            'startupProbe': probe | {'failureThreshold': 12, 'periodSeconds': 5},
                            'volumeMounts': [{'name': 'tmp', 'mountPath': '/tmp'}],
                        }
                    ],
                    'volumes': [{'name': 'tmp', 'emptyDir': {'sizeLimit': '32Mi'}}],
                },
            },
        },
    }
    service = {
        'apiVersion': 'v1',
        'kind': 'Service',
        'metadata': {'name': 'veya-team', 'namespace': namespace},
        'spec': {
            'selector': label,
            'ports': [{'port': 8080, 'targetPort': 8080}],
            'type': 'ClusterIP',
        },
    }
    network = {
        'apiVersion': 'networking.k8s.io/v1',
        'kind': 'NetworkPolicy',
        'metadata': {'name': 'veya-team', 'namespace': namespace},
        'spec': {
            'podSelector': {'matchLabels': label},
            'policyTypes': ['Ingress', 'Egress'],
            'ingress': [
                {
                    'from': [{'podSelector': {'matchLabels': {'app': 'veya-gateway'}}}],
                    'ports': [{'protocol': 'TCP', 'port': 8080}],
                }
            ],
            'egress': [
                {
                    'to': [{'podSelector': {'matchLabels': {'app': 'veya-postgres'}}}],
                    'ports': [{'protocol': 'TCP', 'port': 5432}],
                },
                {
                    'to': [
                        {
                            'namespaceSelector': {
                                'matchLabels': {'kubernetes.io/metadata.name': 'kube-system'}
                            },
                            'podSelector': {'matchLabels': {'k8s-app': 'kube-dns'}},
                        }
                    ],
                    'ports': [{'protocol': 'UDP', 'port': 53}, {'protocol': 'TCP', 'port': 53}],
                },
            ],
        },
    }
    return {'apiVersion': 'v1', 'kind': 'List', 'items': [deployment, service, network]}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', required=True)
    parser.add_argument('--namespace', required=True)
    parser.add_argument('--secret', required=True)
    args = parser.parse_args()
    print(json.dumps(render(args.image, args.namespace, args.secret), indent=2))
