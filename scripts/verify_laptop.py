"""Load transferred artifacts and compare CPU inference without training."""
import argparse
import hashlib
import json
import os
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def verify(require_manifest=False,patch_manifest=None):
    manifest_path=ROOT/'handoff_manifest.json'
    verified=0
    amendments={}
    if patch_manifest:
        amendments=json.loads(Path(patch_manifest).read_text(encoding='utf-8-sig'))['files']
    if require_manifest and not manifest_path.exists():raise ValueError('Extract the complete laptop bundle first')
    if manifest_path.exists():
        for name,entry in json.loads(manifest_path.read_text())['files'].items():
            path=(ROOT/name).resolve()
            if not path.is_relative_to(ROOT.resolve()):raise ValueError('Unsafe manifest path')
            expected=entry['sha256']
            if name in amendments:
                runtime_source = name.endswith(('.py','.ps1')) and name.startswith(('incidentlab/','scripts/','Setup-Laptop.ps1'))
                web_source = name.startswith('web/') and name.endswith(('.html','.js','.css'))
                if not (runtime_source or web_source):
                    raise ValueError('Patch manifest may only amend runtime source: '+name)
                if amendments[name]['original_sha256']!=expected:raise ValueError('Patch provenance disagrees with transfer manifest: '+name)
                expected=amendments[name]['sha256']
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
                raise ValueError('Missing or changed handoff file: '+name)
            verified+=1
        if set(amendments)-set(json.loads(manifest_path.read_text())['files']):raise ValueError('Unknown patch manifest entry')
    os.environ['CUDA_VISIBLE_DEVICES']='-1'
    os.environ['INCIDENTLAB_DISABLE_LLM']='1'
    import torch
    if torch.version.cuda is not None:raise ValueError('Install requirements-laptop.txt in a fresh CPU environment; CUDA build found')
    torch.set_num_threads(2)
    from fastapi.testclient import TestClient
    from incidentlab import research_server as server
    from incidentlab.native_observer import native_bundle
    from incidentlab.live_monitor import score
    from incidentlab.parameter_serving import bundle as parameter_bundle
    client=TestClient(server.app)
    assert client.get('/api/status').status_code==200
    assert client.get('/live').status_code==200
    status=client.get('/api/live/status').json()
    run_id=status['report']['run_id']
    native,digest=native_bundle(run_id)
    trial=next(t['phase'] for t in status['report']['trials'] if t['kind']=='error' and t['target']=='checkout')
    directory=ROOT/'artifacts/live'/run_id/trial
    rows=json.loads((directory/'windows.json').read_text())
    reference=json.loads((directory/'predictions.json').read_text())
    result=score(rows[36:39],native)
    assert result['operational_alert']==reference[12]['operational_alert']
    assert result['ml_alert']==reference[12]['ml_alert']
    assert client.post('/api/live/diagnose',json=dict(phase=trial,window=12)).status_code==503
    _,parameter_digest=parameter_bundle('v4')
    saved=json.loads((ROOT/'artifacts/research/temporal_test_predictions.json').read_text())
    cases=client.get('/api/status').json()['test_cases']
    comparisons=[]
    for profile in ('ob','ss','tt'):
        case=next(name for name in cases if name[3:5]==profile)
        baseline=client.get('/api/replay/'+case).json()
        assert baseline['windows']
        began=time.perf_counter()
        response=client.get('/api/replay/'+case+'?model=temporal')
        assert response.status_code==200,response.text[:300]
        windows=response.json()['windows']
        expected={r['start']:r for r in saved if r['case']==case}
        assert len(windows)==len(expected)
        differences=[abs(w['score']-expected[w['start']]['score']) for w in windows]
        assert max(differences)<.001
        comparisons.append(dict(case=case,windows=len(windows),max_cpu_gpu_score_difference=max(differences),
            milliseconds=(time.perf_counter()-began)*1000))
    return dict(status='passed',manifest_files_verified=verified,source_amendments_verified=sorted(amendments),torch_version=torch.__version__,
        torch_cuda_version=torch.version.cuda,device='cpu',threads=2,model_run=run_id,
        native_checkpoint_sha256=digest,parameter_checkpoint_sha256=parameter_digest,
        temporal_comparisons=comparisons,training_performed=False,llm_generation_disabled=True,
        boundary='CPU artifact loading/replay verification only; actual Kubernetes evidence is documented separately in docs/laptop_execution_20261006.md')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--require-manifest',action='store_true')
    parser.add_argument('--patch-manifest')
    args=parser.parse_args();report=verify(args.require_manifest,args.patch_manifest)
    directory=ROOT/'artifacts/handoff';directory.mkdir(parents=True,exist_ok=True)
    (directory/'cpu_verification.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))
