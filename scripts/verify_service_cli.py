"""Exercise deployment CLI flags using owned native processes, not a cluster."""
import json
import os
import socket
import subprocess
import sys
import time
import uuid
from urllib.request import urlopen

from incidentlab.native_experiment import ROOT, OUT, save
from incidentlab.raw_telemetry import RequestEvent


def main():
    directory = OUT/'cli_checks'/uuid.uuid4().hex[:8]
    directory.mkdir(parents=True)
    children, handles, ports = [], [], {}
    try:
        for service in ('inventory', 'checkout'):
            with socket.socket() as reservation:
                reservation.bind(('127.0.0.1', 0))
                port = reservation.getsockname()[1]
            ports[service] = port
            nonce = uuid.uuid4().hex
            args = [sys.executable, '-m', 'incidentlab.native_service', '--service', service,
                    '--port', str(port), '--directory', str(directory), '--instance-id', nonce,
                    '--bind', '0.0.0.0', '--stdout-events']
            if service == 'checkout':
                args += ['--downstream', f'inventory:{ports["inventory"]}', '--downstream-host', 'localhost']
            stream = (directory/f'{service}.stdout').open('wb')
            handles.append(stream)
            child = subprocess.Popen(args, cwd=ROOT, stdout=stream, stderr=stream,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
            children.append(child)
            deadline = time.monotonic()+10
            while True:
                if child.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError('Owned CLI service did not start')
                try:
                    with urlopen(f'http://127.0.0.1:{port}/health', timeout=.3) as response:
                        if json.loads(response.read())['instance_id'] == nonce:
                            break
                except OSError:
                    time.sleep(.05)
        with urlopen(f'http://127.0.0.1:{ports["checkout"]}/request', timeout=2) as response:
            assert response.status == 200
            response.read()
        records = {}
        for service in ports:
            raw = (directory/f'{service}.jsonl').read_text(encoding='utf-8').strip()
            RequestEvent.model_validate_json(raw)
            assert json.loads((directory/f'{service}.stdout').read_text().strip()) == json.loads(raw)
            records[service] = json.loads(raw)
        assert records['inventory']['trace_id'] == records['checkout']['trace_id']
        assert records['inventory']['parent_span_id'] == records['checkout']['span_id']
        report = dict(status='passed', bind='0.0.0.0', downstream_host='localhost',
            stdout_matches_jsonl=True, trace_parent_verified=True,
            scope='Native CLI integration only; image/cluster execution unverified')
        save(directory/'report.json', report)
        save(OUT/'service_cli_check_report.json', report)
        print(json.dumps(report, indent=2))
    finally:
        for child in children:
            if child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    child.kill(); child.wait(timeout=5)
        for stream in handles:
            stream.close()


if __name__ == '__main__':
    main()
