"""Render isolated application staging assets; never contacts or mutates a cluster."""
import argparse
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
NAMESPACE = 'incidentlab-testbed'


def objects(image):
    if not re.fullmatch(r'[A-Za-z0-9._/:@-]+', image):
        raise ValueError('Image reference contains unsupported characters')
    docs = [dict(apiVersion='v1', kind='Namespace', metadata=dict(name=NAMESPACE,
                 labels={'app.kubernetes.io/part-of':'incidentlab-testbed'}))]
    for name, port, downstream in (('frontend',8891,('checkout',8892)),
                                  ('checkout',8892,('inventory',8893)),('inventory',8893,None)):
        labels = {'app.kubernetes.io/name':name, 'app.kubernetes.io/part-of':'incidentlab-testbed'}
        args = ['-m','incidentlab.native_service','--service',name,'--port',str(port),
                '--directory','/telemetry','--bind','0.0.0.0','--stdout-events']
        if downstream:
            args.extend(['--downstream',f'{downstream[0]}:{downstream[1]}','--downstream-host',downstream[0]])
        probe = dict(httpGet=dict(path='/health',port=port),periodSeconds=5,timeoutSeconds=2,failureThreshold=3)
        container = dict(name=name, image=image, imagePullPolicy='IfNotPresent', command=['python'], args=args,
            ports=[dict(containerPort=port,name='http')], readinessProbe=probe,
            livenessProbe=dict(**probe,initialDelaySeconds=5),
            securityContext=dict(allowPrivilegeEscalation=False,readOnlyRootFilesystem=True,
                                 capabilities=dict(drop=['ALL'])),
            resources=dict(requests=dict(cpu='100m',memory='64Mi'),limits=dict(cpu='500m',memory='128Mi')),
            volumeMounts=[dict(name='telemetry',mountPath='/telemetry')])
        pod = dict(automountServiceAccountToken=False,
            securityContext=dict(runAsNonRoot=True,runAsUser=10001,runAsGroup=10001,fsGroup=10001,
                                 seccompProfile=dict(type='RuntimeDefault')),
            containers=[container],volumes=[dict(name='telemetry',emptyDir=dict(sizeLimit='128Mi'))])
        docs.append(dict(apiVersion='apps/v1',kind='Deployment',metadata=dict(name=name,namespace=NAMESPACE,labels=labels),
            spec=dict(replicas=1,selector=dict(matchLabels=labels),
                      template=dict(metadata=dict(labels=labels),spec=pod))))
        docs.append(dict(apiVersion='v1',kind='Service',metadata=dict(name=name,namespace=NAMESPACE,labels=labels),
                         spec=dict(type='ClusterIP',selector=labels,ports=[dict(port=port,targetPort='http',name='http')])))
    return docs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--image',default='incidentlab-testbed:dev')
    args = parser.parse_args()
    path = ROOT/'deployment/kubernetes-testbed.yaml'
    docs = objects(args.image)
    text = yaml.safe_dump_all(docs,sort_keys=False)
    if len(list(yaml.safe_load_all(text))) != 7:
        raise RuntimeError('Unexpected object count')
    path.write_text('# Rendered staging assets; not deployed/cluster-validated.\n'+text,encoding='utf-8')
    print(f'{path}: seven parsed objects, isolated namespace {NAMESPACE}; no cluster contacted')


if __name__ == '__main__': main()
