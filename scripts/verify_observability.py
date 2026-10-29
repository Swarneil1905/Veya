"""Local synthetic Prometheus/Grafana smoke, using explicit portable tool paths."""

import argparse
import json
import os
import socket
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from uuid import uuid4


def port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--prometheus', type=Path, required=True)
    p.add_argument('--grafana', type=Path, required=True)
    args = p.parse_args()
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / 'services/runtime'))
    import httpx
    from veya.observability.metrics import Metrics

    output = root / 'artifacts/operations20/dashboard'
    output.mkdir(parents=True, exist_ok=True)
    for name in ('data', 'logs', 'plugins'):
        (output / name).mkdir(exist_ok=True)
    metrics = Metrics()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            metrics.calls.labels('provider', 'succeeded').inc(90)
            metrics.calls.labels('provider', 'failed').inc(10)
            metrics.calls.labels('runtime', 'succeeded').inc(100)
            metrics.latency.labels('provider').observe(0.2)
            metrics.latency.labels('runtime').observe(0.01)
            metrics.unknown_cost.inc(10)
            metrics.queue_delay.observe(0)
            body = metrics.render()
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain; version=0.0.4')
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    seed = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=seed.serve_forever, daemon=True).start()
    prom_port, grafana_port = port(), port()
    prom_data = output / ('prom-data-' + uuid4().hex)
    rules = root / 'infra/observability/rules/veya.yml'
    (output / 'prometheus.yml').write_text(f"""global:
  scrape_interval: 1s
  evaluation_interval: 1s
rule_files: ['{rules.as_posix()}']
scrape_configs:
  - job_name: synthetic-veya-validation
    static_configs:
      - targets: ['127.0.0.1:{seed.server_port}']
""")
    provision = output / 'provisioning'
    for kind in ('datasources', 'dashboards'):
        (provision / kind).mkdir(parents=True, exist_ok=True)
    (provision / 'datasources/veya.yml').write_text(f"""apiVersion: 1
datasources:
  - name: Veya synthetic validation
    uid: veya-prometheus
    type: prometheus
    access: proxy
    url: http://127.0.0.1:{prom_port}
    isDefault: true
""")
    dashboard_dir = (root / 'infra/observability/dashboards').as_posix()
    (provision / 'dashboards/veya.yml').write_text(f"""apiVersion: 1
providers:
  - name: Veya validation
    type: file
    options:
      path: {dashboard_dir}
""")
    (output / 'grafana.ini').write_text(f"""[server]
http_addr = 127.0.0.1
http_port = {grafana_port}
[paths]
data = {(output / 'data').as_posix()}
logs = {(output / 'logs').as_posix()}
plugins = {(output / 'plugins').as_posix()}
provisioning = {provision.as_posix()}
[auth.anonymous]
enabled = true
org_role = Viewer
[analytics]
reporting_enabled = false
check_for_updates = false
check_for_plugin_updates = false
[plugins]
preinstall_disabled = true
""")
    children = []
    flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    try:
        for name, command in [
            (
                'prometheus',
                [
                    str(args.prometheus.resolve()),
                    '--config.file=' + str(output / 'prometheus.yml'),
                    '--storage.tsdb.path=' + str(prom_data),
                    '--web.listen-address=127.0.0.1:' + str(prom_port),
                ],
            ),
            (
                'grafana',
                [
                    str((args.grafana / 'bin/grafana-server.exe').resolve()),
                    '--homepath=' + str(args.grafana.resolve()),
                    '--config=' + str(output / 'grafana.ini'),
                ],
            ),
        ]:
            with (output / (name + '.log')).open('wb') as logs:
                children.append(
                    subprocess.Popen(command, stdout=logs, stderr=logs, creationflags=flags)
                )
        with httpx.Client(trust_env=False, timeout=2) as client:
            deadline = time.monotonic() + 55
            while time.monotonic() < deadline:
                if any(child.poll() is not None for child in children):
                    raise RuntimeError('Dashboard process exited; inspect bounded local logs')
                try:
                    grafana = client.get(f'http://127.0.0.1:{grafana_port}/api/health')
                    response = client.get(
                        f'http://127.0.0.1:{prom_port}/api/v1/query',
                        params={'query': 'veya:failure_ratio:rate5m'},
                    )
                    values = response.json()['data']['result']
                    rates = {row['metric']['source']: float(row['value'][1]) for row in values}
                    if grafana.status_code == 200 and rates.get('provider') is not None:
                        assert abs(rates['provider'] - 0.1) < 0.00001 and rates['runtime'] == 0
                        break
                except (httpx.HTTPError, KeyError, ValueError):
                    pass
                time.sleep(1)
            else:
                raise RuntimeError('Synthetic dashboard did not become queryable')
            (output / 'query-result.json').write_text(
                json.dumps(
                    {'synthetic': True, 'rates': rates, 'provider_failure_ratio': 0.1}, indent=2
                )
            )
            rendered = subprocess.run(
                [
                    'node',
                    'scripts/test-observability-browser.mjs',
                    f'http://127.0.0.1:{grafana_port}',
                ],
                cwd=root,
                capture_output=True,
                text=True,
                creationflags=flags,
            )
            (output / 'browser.log').write_text(rendered.stdout + rendered.stderr, encoding='utf8')
            rendered.check_returncode()
    finally:
        seed.shutdown()
        seed.server_close()
        for child in children:
            child.terminate()
        for child in children:
            try:
                child.wait(10)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()


if __name__ == '__main__':
    main()
