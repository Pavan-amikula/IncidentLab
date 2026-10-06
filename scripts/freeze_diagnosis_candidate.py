"""Freeze the diagnosis implementation before this native run's fault collection."""
import argparse
import hashlib
import json
import time

from incidentlab.native_experiment import ROOT, OUT, save
from incidentlab.evidence_diagnosis import SYSTEM_V2


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--run-id',required=True)
    args=parser.parse_args()
    progress=json.loads((OUT/'progress.json').read_text())
    if progress.get('run_id')!=args.run_id or progress.get('stage') not in (
            'healthy_train','healthy_validation','test_healthy','test_surge'):
        raise ValueError('Candidate freeze must precede fault-trial collection')
    directory=OUT/args.run_id/'diagnosis_candidate_v2'
    directory.mkdir()
    hashes={}
    for name in ('evidence_diagnosis.py','llm_live_evaluation.py','semantic_models.py'):
        raw=(ROOT/'incidentlab'/name).read_bytes()
        (directory/name).write_bytes(raw)
        hashes[name]=hashlib.sha256(raw).hexdigest()
    manifest=dict(run_id=args.run_id,policy_version='v2',created_epoch=time.time(),
        created_stage=progress['stage'],code_sha256=hashes,
        prompt_sha256=hashlib.sha256(SYSTEM_V2.encode()).hexdigest(),
        note='Candidate frozen before fault collection; known fault families and one application, not an unseen-system test')
    save(directory/'manifest.json',manifest)
    print(json.dumps(manifest,indent=2))


if __name__=='__main__': main()
