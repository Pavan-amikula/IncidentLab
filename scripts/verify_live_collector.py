"""Verify actual HTTP trace identity, incremental ingestion and owned-process cleanup."""
import json
import time
import uuid
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from incidentlab.native_experiment import Testbed, OUT, request_once, save
from incidentlab.raw_telemetry import EventCollector


def main():
    directory = OUT/'collector_checks'/uuid.uuid4().hex[:8]
    bed = Testbed(directory)
    try:
        bed.start()
        start = time.time()
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(lambda _:request_once(), range(20)))
        end = time.time()+.001
        collector = EventCollector(directory)
        events = collector.read_window(start, end)
        grouped = defaultdict(list)
        for event in events:
            grouped[event['trace_id']].append(event)
        if len(events) != 60 or len(grouped) != 20:
            raise RuntimeError('Requests did not produce complete three-service traces')
        for values in grouped.values():
            services = {event['service']:event for event in values}
            if services['frontend']['parent_span_id'] is not None:
                raise RuntimeError('Root request has an unexpected parent')
            if services['checkout']['parent_span_id'] != services['frontend']['span_id']:
                raise RuntimeError('Checkout trace parent does not resolve')
            if services['inventory']['parent_span_id'] != services['checkout']['span_id']:
                raise RuntimeError('Inventory trace parent does not resolve')
        if collector.read_window(end, end+1):
            raise RuntimeError('Collector delivered duplicate events')
        report = dict(status='passed', actual_requests=20, complete_traces=len(grouped),
            event_records=len(events), audit=collector.audit(),
            scope='Collector/trace/process integration check, not an ML dataset or accuracy experiment')
        save(directory/'report.json', report)
        save(OUT/'collector_check_report.json', report)
        print(json.dumps(report, indent=2))
    finally:
        bed.close()
        if bed.children:
            raise RuntimeError('Owned test service processes leaked')


if __name__ == '__main__': main()
