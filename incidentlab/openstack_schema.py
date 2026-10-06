"""Lightweight raw-log schema shared by batch and serving adapters."""
import re
from pathlib import Path

BASE=Path(__file__).resolve().parents[1]/'data/research/OpenStack'
UUID=re.compile(r'\b[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\b',re.I)
INSTANCE=re.compile(r'\[instance: ([0-9a-f-]{36})\]')
LINE=re.compile(r'^\S+ \d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+ \d+ (DEBUG|INFO|WARNING|WARN|ERROR|CRITICAL) (\S+) (.*)')
