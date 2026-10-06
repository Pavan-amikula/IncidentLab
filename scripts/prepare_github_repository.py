"""Prepare a separate publication checkout; never alter measured research evidence."""
import hashlib
import json
import shutil
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT.parent/'IncidentLab-GitHub'
EXCLUDE={'.venv','.venv-laptop','.venv-laptop-cpu','__pycache__','.git'}
def main():
    if OUT.exists():raise RuntimeError('Publication directory already exists; inspect before changing it')
    OUT.mkdir()
    for source in ROOT.rglob('*'):
        rel=source.relative_to(ROOT)
        if not source.is_file() or any(p in EXCLUDE for p in rel.parts):continue
        if source.suffix in ('.pyc','.sqlite3','.db','.log') or source.name.startswith('.env'):continue
        if rel.parts[:2] in [('artifacts','live_runtime'),('reports','preview')]:continue
        if rel.parts[:2]==('artifacts','laptop_validation') and source.suffix not in ('.json','.png'):continue
        target=OUT/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
    provenance=OUT/'docs/provenance';provenance.mkdir(exist_ok=True)
    for name in ('README.md','handoff_manifest.json','laptop_patch_manifest.json'):
        shutil.copy2(ROOT/name,provenance/('college-project-README.md' if name=='README.md' else name))
    # Keep immutable transfer manifests as historical provenance. The publication
    # has its own file inventory because databases/cache/logs are deliberately omitted.
    for name in ('handoff_manifest.json','laptop_patch_manifest.json'):(OUT/name).unlink()
    readme='''# IncidentLab

### End-to-end ML for cloud incident detection and evidence-supported investigation

**Python · PyTorch · scikit-learn · FastAPI · Docker · Kubernetes (kind) · SQLite**

IncidentLab connects multimodal telemetry research with a real three-service HTTP testbed. It processes logs, metrics and traces, compares anomaly-detection models, serves frozen checkpoints on CPU, and investigates controlled faults using request evidence.

**Status:** Research and the controlled laptop demonstration are complete. Industrial reliability remains unverified. New LLM generation and automatic remediation are disabled.

## Measured results

| Evaluation | Result | Meaning |
|---|---:|---|
| RCAEval processing | 733 eligible cases; 49.7M logs; 110.7M spans | Original processing, not a new laptop download |
| Case partitions | 439 / 147 / 147 | Training / validation / development-test |
| Research GRU | F1 **0.972** | Development-test window metric; external transfer was weak |
| Original native HTTP trials | Operational **18/18**; ML **10/18** | Controlled local experiment on the college PC |
| Laptop Kubernetes trials | Operational **9/9**; ML **4/9** | Separate deployment; trial flags, not guaranteed causal diagnoses |
| Chronological replay | **300 windows; zero mismatches** | Reproduced features, scores and decisions |
| Container restart check | **8/8 tail traces recovered** | One controlled restart; zero duplicate poll insertions |
| Lean CPU checks | **75 tests passed locally** | Optional transformer diagnosis module excluded; not a claimed GitHub CI run |

Operational results include latency/error envelopes and coverage checks. They are not ML-only results. The frozen GRU alerted on only 3/24 external AnoMod fault runs; missing healthy/onset labels prevent an external precision/F1 claim. Capture review found 21 incomplete successful trace chains near pod deletion. Negative results remain included.

## Architecture

```mermaid
flowchart LR
    D[Research logs, metrics and traces] --> P[Bounded preprocessing and case splits]
    P --> M[Isolation Forest, boosting and temporal GRU]
    M --> R[Saved predictions and evaluation figures]
    F[Frontend] --> C[Checkout] --> I[Inventory]
    F --> E[Measured request events]
    C --> E
    I --> E
    E --> S[Durable ingestion and 3-second windows]
    S --> A[Native Isolation Forest + operational checks]
    A --> V[FastAPI dashboard and trace investigation]
```

Research features and the live HTTP detector use separate schemas/checkpoints. The applications run in Kubernetes pods during cluster experiments; inference, capture and the dashboard run on the Windows host. The local HTTP demo does not require Docker.

## Run on Windows, CPU only

Prerequisite: official 64-bit Python 3.14 with the `py` launcher. This setup installs CPU dependencies, verifies publication hashes and loads saved checkpoints. It does not retrain models or download raw datasets.

```powershell
git clone https://github.com/Pavan-amikula/IncidentLab.git
cd IncidentLab
powershell -ExecutionPolicy Bypass -File .\\Setup-GitHub.ps1
powershell -ExecutionPolicy Bypass -File .\\Start-Laptop.ps1
```

Open **http://127.0.0.1:8768/**. Choose **Live demo**, run healthy traffic first, then run the Inventory delay test. The bounded demo lasts one minute and collects 20 observation windows. Saved results remain available afterward.

```powershell
# Run the lean CPU suite after setup.
.\\.venv-laptop\\Scripts\\python.exe -m scripts.test_laptop
```

This GitHub edition uses `Setup-GitHub.ps1` and `repository_manifest.json`. Historical transfer scripts/manifests describe the original full ZIP and are retained for provenance; do not use them as the GitHub edition installer.

## Docker and Kubernetes

**Docker's Linux engine must run for fresh cluster workloads.** Its window can be minimized. Saved research/results/figures and the native localhost demo do not need it.

The dedicated cluster context is `kind-incidentlab`. Namespace: `incidentlab-testbed`. Docker container `incidentlab-control-plane` holds the kind Kubernetes node, which contains the three application pods. It is separate from Docker Desktop's optional built-in Kubernetes cluster.

```powershell
kubectl --context kind-incidentlab -n incidentlab-testbed get pods
```

For a fresh cluster, follow [the measured laptop deployment procedure](docs/laptop_execution_20261006.md), including the compatibility and owned-testbed termination settings used in this run. The runner exposes Check, Deploy, Quick and Validate. Quick takes about five minutes and Validate about 21 minutes plus overhead. Do not rerun expensive research training just to demonstrate the dashboard.

## Report figures

![GRU confusion matrix](artifacts/report_figures/research-gru-confusion.png)

![Measured cluster delay](artifacts/report_figures/cluster-delay-timeline.png)

Confusion matrices, per-system ROC/PR curves, original training curves and measured timelines are available in [PNG/SVG/PDF with exact figure data](artifacts/report_figures/). Research curves use saved scores; cluster matrices use control-completion timing proxies and exclude crossing windows. Trial impact was reviewed against traces, not independently labeled for every window.

## Start reading here

| Reader | Document |
|---|---|
| Recruiter / resume | [Project description and quantified bullets](docs/resume_project_description.md) |
| Interview preparation | [Complete project guide and questions](docs/project_interview_guide.md) |
| Dashboard user | [Short user guide](docs/dashboard_user_guide.md) |
| Experiment reviewer | [Reproducible laptop execution report](docs/laptop_execution_20261006.md) |
| Current status | [Final delivery and limitations](docs/final_delivery_20261006.md) |
| Paper/report | [Readable IEEE-style PDF](reports/IncidentLab-IEEE-readable.pdf) · [Editable IEEEtran source](reports/IncidentLab-IEEE.tex) |
| Dataset/source attribution | [Third-party notices](THIRD_PARTY_NOTICES.md) |

The report's PDF is a reviewed two-column fallback because the built-in LaTeX compiler failed on this host. IEEEtran source is editable; publication and venue-compliant compilation are not claimed.

## Repository map

- `incidentlab/`: processing, models, telemetry collection, APIs and runtime.
- `scripts/`: acquisition/preprocessing, evaluation, replay checks and figure/report builders.
- `tests/`: meaningful protocol, HTTP, capture, serving and workspace checks.
- `deployment/`: Docker/kind assets and controlled cluster procedures.
- `web/`: guided dashboard and detailed research/native archives.
- `data/processed/`: portable processed benchmark inputs; no large raw collections.
- `artifacts/research/`: frozen research checkpoints, predictions and reports.
- `artifacts/live/`: measured native HTTP experiments, including negative findings.
- `artifacts/kubernetes/`: separate measured cluster runs and infrastructure checks.
- `docs/` and `reports/`: methodology, investigation guide and report.

Virtual environments, CUDA libraries, transformer/LLM weights, runtime databases and transient process logs are omitted. New local databases are created as needed. The publication inventory preserves hashes of included evidence. Serialized checkpoints should only be loaded from a trusted copy of this repository.

## Limitations and next work

Long-duration reliability, independent external healthy/onset labels, log rotation/repeated restart capture, authenticated multi-user deployment and company-scale testing remain open. This is a cloud-relevant local ML project, not an AWS/Azure/GCP production deployment. An alert or service ranking alone does not prove a root cause.

## Author and attribution

**Amikula Pavan Kumar Goud** — MSc Computer Science Student, Blekinge Institute of Technology, Karlskrona, Sweden.

RCAEval and other external datasets belong to their respective creators. Original academic references and source records are retained. Historical college-PC paths and older “pending” notes remain provenance; dated laptop reports describe the subsequent execution.
'''
    (OUT/'README.md').write_text(readme,encoding='utf-8')
    (OUT/'.gitignore').write_text('''.venv*/
__pycache__/
*.py[cod]
.env
.env.*
*.sqlite3
*.sqlite3-*
*.db
*.log
artifacts/live_runtime/
reports/preview/
''',encoding='utf-8')
    (OUT/'THIRD_PARTY_NOTICES.md').write_text('''# Third-party data and provenance

The author's project source, measured testbed evidence and documentation are distinct from external datasets and libraries. No blanket license is applied to third-party material.

## RCAEval

Luan Pham, Hongyu Zhang, Huong Ha, Flora Salim and Xiuzhen Zhang, “RCAEval: A Benchmark for Root Cause Analysis of Microservice Systems with Telemetry Data,” arXiv:2412.17015 (2024, revised 2025), DOI 10.48550/arXiv.2412.17015.

- Dataset card and declared MIT license: https://huggingface.co/datasets/phamquiluan/RCAEval
- Maintainer repository: https://github.com/phamquiluan/RCAEval
- Original record: https://zenodo.org/records/14590730

Included processed Parquet features are transformations of the acquired telemetry: aggregation, causal warm-up normalization, modality features and explicit partition assignments. They are not a newly authored source dataset. Acquisition/preparation reports retain release references and hashes.

## AnoMod

Source: EvoTestOps/AnoMod and author deposit https://zenodo.org/records/18342898 . The recorded dataset license is CC BY 4.0; source-code licensing is distinct. License: https://creativecommons.org/licenses/by/4.0/ . Included processed inputs are transformations for external/development evaluation; preserve attribution and negative results. The original large raw archive is not included.

## OpenStack / Loghub

OpenStack log investigations use the Loghub source identified in the acquisition and research notes. See https://github.com/logpai/loghub and the original acquisition provenance. Raw log collections are not redistributed in this edition. Saved analysis/checkpoints do not transfer ownership of upstream data.

## Libraries

PyTorch, scikit-learn, FastAPI, NumPy, SciPy, PyArrow, Drain3, Docker, Kubernetes and kind retain their respective licenses. Dependencies are installed from their official/package-registry sources rather than vendored here.

## Historical provenance

`docs/provenance/` retains the original README, transfer manifest and amendment manifest. Some original paths refer to the college PC. Publication packaging omits local databases and transient logs; `repository_manifest.json` is the inventory for this edition.
''',encoding='utf-8')
    verifier='''"""Verify publication hashes and CPU replay; no training or raw downloads."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
manifest=json.loads((ROOT/'repository_manifest.json').read_text(encoding='utf-8'))
for name,digest in manifest['files'].items():
    p=(ROOT/name).resolve()
    if not p.is_relative_to(ROOT) or not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=digest:
        raise ValueError('Publication file missing or changed: '+name)
from scripts.verify_laptop import verify
result=verify()
result['repository_files_verified']=len(manifest['files'])
print(json.dumps(result,indent=2))
'''
    (OUT/'scripts/verify_repository.py').write_text(verifier,encoding='utf-8')
    setup='''param([switch]$CheckOnly)
$ErrorActionPreference='Stop'
$projectRoot=$PSScriptRoot
$runtime=Join-Path $projectRoot '.venv-laptop\\Scripts\\python.exe'
if(-not(Test-Path -LiteralPath $runtime)) {
    if($CheckOnly) { throw 'Run Setup-GitHub.ps1 first.' }
    & py -3.14 -m venv (Join-Path $projectRoot '.venv-laptop')
    if($LASTEXITCODE -ne 0) { throw 'Official Python 3.14 with the py launcher is required.' }
}
Push-Location -LiteralPath $projectRoot
try {
    if(-not $CheckOnly) {
        & $runtime -m pip install -r requirements-laptop.txt
        if($LASTEXITCODE -ne 0) { throw 'CPU dependency installation failed.' }
    }
    & $runtime -m scripts.verify_repository
    if($LASTEXITCODE -ne 0) { throw 'Publication verification failed.' }
} finally { Pop-Location }
Write-Host 'CPU repository checked. Start-Laptop.ps1 starts the dashboard without training.'
'''
    (OUT/'Setup-GitHub.ps1').write_text(setup,encoding='utf-8')
    files={p.relative_to(OUT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(OUT.rglob('*')) if p.is_file()}
    (OUT/'repository_manifest.json').write_text(json.dumps(dict(format='incidentlab-github-publication-v1',files=files,training_performed=False),indent=2),encoding='utf-8')
    summary=dict(directory=str(OUT),files=len(files)+1,mib=round(sum(p.stat().st_size for p in OUT.rglob('*') if p.is_file())/1048576,2),largest_mib=round(max(p.stat().st_size for p in OUT.rglob('*') if p.is_file())/1048576,2),published=False)
    (ROOT/'artifacts/laptop_validation/github-preparation.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
