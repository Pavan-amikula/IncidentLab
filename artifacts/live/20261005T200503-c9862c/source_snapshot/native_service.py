"""Isolated Windows-compatible HTTP test service with actual request telemetry."""
import argparse
import json
import os
import random
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def serve(service, port, downstream, directory, instance_id=None):
    directory.mkdir(parents=True, exist_ok=True)
    lock = threading.Lock()
    rng = random.Random(43)
    state = {'active': 0}
    output = (directory / f'{service}.jsonl').open('a', encoding='utf-8', buffering=1)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            if self.path == '/health':
                self.send_response(200); self.end_headers()
                self.wfile.write(json.dumps({'service':service, 'pid':os.getpid(), 'instance_id':instance_id}).encode()); return
            if self.path != '/request':
                self.send_response(404); self.end_headers(); return
            started = time.time()
            span = uuid.uuid4().hex
            trace = self.headers.get('X-Trace-ID') or uuid.uuid4().hex
            parent = self.headers.get('X-Parent-ID')
            with lock:
                state['active'] += 1
                active = state['active']
                base_delay = rng.uniform(.004, .016)
            status, message, dependency, dependency_status = 200, 'request completed', None, None
            try:
                config_path = directory / 'control.json'
                config = json.loads(config_path.read_text()) if config_path.exists() else {}
                mode = config.get(service, 'healthy')
                if mode == 'delay':
                    time.sleep(.25)
                time.sleep(base_delay)
                if mode == 'error':
                    status, message = 503, 'local dependency capacity exhausted'
                elif downstream:
                    dependency = downstream[0]
                    request = Request(f'http://127.0.0.1:{downstream[1]}/request',
                                      headers={'X-Trace-ID': trace, 'X-Parent-ID': span})
                    try:
                        with urlopen(request, timeout=1.0) as response:
                            response.read(); dependency_status = response.status
                    except HTTPError as exc:
                        dependency_status = exc.code
                    except (URLError, TimeoutError, OSError):
                        dependency_status = 0
                    if dependency_status != 200:
                        status, message = 502, 'downstream request failed'
                completed = time.time()
                event = dict(schema='incidentlab-http-v1', service=service, trace_id=trace,
                             span_id=span, parent_span_id=parent, start=started, end=completed,
                             duration_ms=(completed-started)*1000, status=status,
                             active_requests=active, message=message, dependency=dependency,
                             dependency_status=dependency_status)
                with lock:
                    output.write(json.dumps(event) + '\n')
                self.send_response(status); self.end_headers()
                try:
                    self.wfile.write(json.dumps({'service': service, 'status': status}).encode())
                except (BrokenPipeError, ConnectionResetError):
                    pass
            finally:
                with lock:
                    state['active'] -= 1

    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    server.daemon_threads = True
    try:
        server.serve_forever()
    finally:
        server.server_close(); output.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--service', required=True)
    parser.add_argument('--port', type=int, required=True)
    parser.add_argument('--downstream')
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--instance-id', default=None)
    args = parser.parse_args()
    downstream = args.downstream.split(':') if args.downstream else None
    serve(args.service, args.port, (downstream[0], int(downstream[1])) if downstream else None,
          args.directory, args.instance_id)
