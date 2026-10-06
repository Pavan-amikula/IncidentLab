import json
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from pydantic import ValidationError
from incidentlab.raw_telemetry import EventCollector, RequestEvent


def event(end=11):
    return dict(schema='incidentlab-http-v1', service='inventory', trace_id='a'*32,
        span_id='b'*32, parent_span_id='c'*32, start=end-.01, end=end,
        duration_ms=10, status=200, active_requests=1, message='request completed',
        dependency=None, dependency_status=None)


class RawIngestionChecks(unittest.TestCase):
    def test_partial_write_is_not_lost_or_double_scored(self):
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name); path = directory/'inventory.jsonl'
            first = json.dumps(event()).encode()
            path.write_bytes(first[:20])
            collector = EventCollector(directory)
            self.assertEqual(collector.read_window(9, 10), [])
            with path.open('ab') as handle: handle.write(first[20:]+b'\n')
            self.assertEqual(len(collector.read_window(10, 12)), 1)
            self.assertEqual(collector.read_window(12, 13), [])
            self.assertEqual(collector.audit()['records_read'], 1)

    def test_future_and_late_records_are_accounted_separately(self):
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            (directory/'inventory.jsonl').write_text('\n'.join(json.dumps(event(end)) for end in (5,11,15))+'\n')
            collector = EventCollector(directory)
            self.assertEqual(len(collector.read_window(10, 12)), 1)
            self.assertEqual(collector.audit()['late_records'], 1)
            self.assertEqual(len(collector.read_window(12, 16)), 1)

    def test_evaluation_labels_and_nonfinite_values_rejected(self):
        for extra in ({'root_cause':'inventory'}, {'fault':'delay'}, {'duration_ms':float('nan')}):
            with self.assertRaises(ValidationError): RequestEvent.model_validate(dict(event(), **extra))

    def test_clock_incoherence_is_rejected(self):
        value = event(); value['duration_ms'] = 900
        with self.assertRaises(ValidationError): RequestEvent.model_validate(value)

    def test_append_at_moving_eof_is_read_next_poll_not_capacity_failure(self):
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name); path = directory/'inventory.jsonl'
            path.write_text(json.dumps(event(11))+'\n')
            original_open = Path.open
            appended = False

            class GrowingReader:
                def __init__(self, source): self.source = source
                def __enter__(self): return self
                def __exit__(self, *args): self.source.close()
                def seek(self, *args): return self.source.seek(*args)
                def read(self, size=-1):
                    nonlocal appended
                    value = self.source.read(size)
                    if size > 1 and not appended:
                        appended = True
                        with original_open(path, 'ab') as writer:
                            writer.write((json.dumps(event(15))+'\n').encode())
                    return value

            def opening(selected, mode='r', *args, **kwargs):
                source = original_open(selected, mode, *args, **kwargs)
                return GrowingReader(source) if selected == path and mode == 'rb' else source

            collector = EventCollector(directory)
            with patch.object(Path, 'open', opening):
                self.assertEqual(len(collector.read_window(10,12)), 1)
                self.assertEqual(len(collector.read_window(12,16)), 1)
            self.assertEqual(collector.record_count, 2)


if __name__ == '__main__': unittest.main()
