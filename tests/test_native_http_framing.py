"""HTTP bodies must be framed before a proxy delays connection closure."""
import json
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from urllib.request import urlopen


class HttpFramingTests(unittest.TestCase):
    def test_real_health_and_request_bodies_have_exact_content_length(self):
        with tempfile.TemporaryDirectory() as directory:
            with socket.socket() as probe:
                probe.bind(('127.0.0.1',0));port=probe.getsockname()[1]
            child=subprocess.Popen([sys.executable,'-m','incidentlab.native_service','--service','inventory',
                '--port',str(port),'--directory',directory],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            try:
                deadline=time.monotonic()+10
                while True:
                    try:
                        with urlopen(f'http://127.0.0.1:{port}/health',timeout=1) as response:response.read()
                        break
                    except OSError:
                        if time.monotonic()>deadline:raise
                        time.sleep(.05)
                for endpoint in ('health','request'):
                    with urlopen(f'http://127.0.0.1:{port}/{endpoint}',timeout=1) as response:
                        body=response.read()
                        self.assertEqual(int(response.headers['Content-Length']),len(body))
                        self.assertEqual(json.loads(body)['service'],'inventory')
            finally:
                child.terminate();child.wait(timeout=5)


if __name__=='__main__':unittest.main()
