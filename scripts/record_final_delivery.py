"""Record current source/artifact hashes and verify local document downloads."""
import hashlib
import json
import re
from pathlib import Path
from urllib.request import urlopen
ROOT=Path(__file__).resolve().parents[1]
destination=ROOT/'artifacts/laptop_validation'
old=json.loads((destination/'final-source-hashes.json').read_text())
new=['scripts/verify_cluster_restart.py','scripts/update_cluster_panel.py','scripts/build_ieee_report.py',
 'scripts/render_ieee_pdf.py','scripts/record_final_delivery.py','docs/resume_project_description.md',
 'docs/final_delivery_20261006.md','reports/IncidentLab-IEEE.tex','reports/IncidentLab-IEEE-readable.pdf',
 'reports/IncidentLab-IEEE-source.zip','reports/IEEE-report-provenance.json']
hashes={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in sorted(set(old)|set(new))}
(destination/'final-source-hashes.json').write_text(json.dumps(hashes,indent=2))
download={}
for name,path in [('ieee.pdf','reports/IncidentLab-IEEE-readable.pdf'),('ieee-source.zip','reports/IncidentLab-IEEE-source.zip'),('resume.md','docs/resume_project_description.md')]:
    with urlopen('http://127.0.0.1:8768/api/workspace/documents/'+name,timeout=10) as response:data=response.read()
    assert hashlib.sha256(data).hexdigest()==hashes[path]
    download[name]=dict(bytes=len(data),sha256=hashes[path])
with urlopen('http://127.0.0.1:8768/api/workspace/cluster-health',timeout=12) as response:health=json.load(response)
assert health['status']=='ready' and len(health['pods'])==3
html=(ROOT/'web/workspace.html').read_text(encoding='utf-8')
(destination/'workspace-final-syntax-check.js').write_text(re.search(r'<script>(.*?)</script>',html,re.S)[1],encoding='utf-8')
(destination/'final-delivery-verification.json').write_text(json.dumps(dict(downloads=download,cluster_health=health,
 lean_cpu_tests=75,ieeetran_compilation='unavailable: platform directory error',pdf_visual_review='All five pages inspected',
 restart_check='infrastructure-20261006T194017-f133aa',industrial_validation='remaining; see final delivery report'),indent=2))
print('Document downloads match their source hashes; three pods Ready; delivery receipt saved.')
