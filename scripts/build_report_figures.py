"""Render report figures from immutable saved predictions; no fitting or threshold tuning.

Install optional requirements-report.txt, then run python -m scripts.build_report_figures.
"""
import hashlib
import json
import zipfile
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from sklearn.metrics import confusion_matrix, roc_curve, roc_auc_score, precision_recall_curve, average_precision_score

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'artifacts/report_figures'
OUT.mkdir(parents=True,exist_ok=True)
sources = {}
figures = []
metrics = {}


def read(path):
    sources[str(path.relative_to(ROOT)).replace('\\','/')] = hashlib.sha256(path.read_bytes()).hexdigest()
    return json.loads(path.read_text(encoding='utf-8-sig'))


def export(fig, name, title, caption):
    fig.tight_layout()
    for extension in ('png','svg','pdf'):
        fig.savefig(OUT/f'{name}.{extension}',dpi=200,bbox_inches='tight')
    plt.close(fig)
    figures.append(dict(name=name,title=title,caption=caption))


def confusion(y,p,name,title,caption):
    matrix = confusion_matrix(y,p,labels=[False,True])
    fig,ax = plt.subplots(figsize=(6,4.5))
    image = ax.imshow(matrix,cmap='Blues')
    for (row,column),count in np.ndenumerate(matrix):
        ax.text(column,row,str(count),ha='center',va='center',fontsize=18,
            color='white' if count>matrix.max()/2 else '#142032')
    ax.set(xticks=[0,1],yticks=[0,1],xticklabels=['Clear','Alert'],yticklabels=['Healthy','Fault'],
           xlabel='Saved detector decision',ylabel='Evaluation label',title=title)
    fig.colorbar(image,ax=ax,label='Observation windows')
    metrics[name]=dict(matrix=matrix.tolist(),windows=len(y),unit='observation windows')
    export(fig,name,title,caption)


def main():
    plt.rcParams.update({'font.size':11,'axes.spines.top':False,'axes.spines.right':False})
    research=ROOT/'artifacts/research'
    temporal=read(research/'temporal_test_predictions.json')
    baseline=read(research/'full_test_predictions.json')['windows']
    threshold=read(research/'temporal_test_report.json')['thresholds']
    rows=[('GRU',temporal,[r['score']>threshold[r['system']] and not r.get('abstained',False) for r in temporal]),
          ('Isolation Forest',baseline,[r['alert'] for r in baseline])]
    caption='RCAEval development-test partition, 147 cases. Frozen validation thresholds; windows within a case are correlated. This does not establish external transfer or production reliability.'
    for label,data,decisions in rows:
        confusion([r['anomalous'] for r in data], decisions,
            'research-gru-confusion' if label=='GRU' else 'research-if-confusion',f'{label}: RCAEval window decisions',caption)
    for profile in ('ob','ss','tt'):
        fig,axes=plt.subplots(1,2,figsize=(10,4))
        for label,data,_ in rows:
            selected=[r for r in data if r['system']==profile]
            y=[r['anomalous'] for r in selected];scores=[r['score'] for r in selected]
            fpr,tpr,_=roc_curve(y,scores);precision,recall,_=precision_recall_curve(y,scores)
            auc=roc_auc_score(y,scores);ap=average_precision_score(y,scores)
            axes[0].plot(fpr,tpr,label=f'{label} (AUC {auc:.3f})')
            axes[1].plot(recall,precision,label=f'{label} (AP {ap:.3f})')
            metrics[f'{profile}-{label}']=dict(windows=len(y),roc_auc=auc,average_precision=ap)
        prevalence=float(np.mean(y))
        axes[0].plot([0,1],[0,1],'--',color='gray',label='Chance ranking')
        axes[1].axhline(prevalence,linestyle='--',color='gray',label=f'Fault prevalence {prevalence:.2f}')
        axes[0].set(xlabel='False positive rate',ylabel='True positive rate',title=f'{profile.upper()} ROC',xlim=(0,1),ylim=(0,1.02))
        axes[1].set(xlabel='Recall',ylabel='Precision',title=f'{profile.upper()} precision–recall',xlim=(0,1),ylim=(0,1.02))
        for ax in axes:ax.legend(fontsize=9)
        export(fig,f'research-{profile}-curves',f'{profile.upper()}: ROC and precision–recall',caption+' Curves use continuous scores within one system; AP is average precision, not a thresholded F1.')
    training=read(research/'temporal_training_report.json')
    fig,axes=plt.subplots(1,2,figsize=(10,4))
    epochs=training['epochs'];x=[r['epoch'] for r in epochs]
    axes[0].plot(x,[r['training_loss'] for r in epochs],marker='o')
    axes[0].set(xlabel='Epoch',ylabel='Training loss',title='Recorded GRU training loss')
    for metric in ('f1','pr_auc'):
        axes[1].plot(x,[r['validation']['overall'][metric] for r in epochs],marker='o',label=metric)
    axes[1].set(xlabel='Epoch',ylabel='Validation metric',title='Recorded validation history');axes[1].legend()
    export(fig,'research-training-curves','GRU training and validation history','Original GPU training history; no retraining on this laptop. Checkpoint selected using validation only. Training loss and validation metrics have different units.')
    receipt=read(ROOT/'artifacts/laptop_validation/final_summary.json')
    cluster=read(ROOT/'artifacts/kubernetes'/receipt['run_id']/'report.json')
    directory=ROOT/'artifacts/kubernetes'/cluster['run_id']
    y=[];op=[];ml=[]
    latency=[];seconds=[]
    for trial in cluster['trials']:
        schedule=read(directory/trial['phase']/'schedule.json')
        predictions=read(directory/trial['phase']/'predictions.json')
        for p in predictions:
            onset,recovery=schedule['onset'],schedule['recovery']
            if onset is None:
                label=False
            elif p['start']>=onset and p['end']<=recovery:
                label=True
            elif p['end']<=onset or p['start']>=recovery:
                label=False
            else:
                continue
            y.append(label);op.append(p['operational_alert']);ml.append(p['ml_alert'])
        if trial['phase']=='test_delay_inventory':
            origin=predictions[0]['start']
            seconds=[p['end']-origin for p in predictions]
            latency={s:[next(c for c in p['candidates'] if c['service']==s)['features'][0] for p in predictions] for s in ('frontend','checkout','inventory')}
            interval=[schedule['onset']-origin,schedule['recovery']-origin]
    boundary=f'Actual kind run {cluster["run_id"]}. Three-second window labels use control-command completion proxies; crossing windows excluded. Capture gaps can affect missing-service warnings. Trace review confirmed trial impact, not exact labels for every window.'
    confusion(y,op,'cluster-operational-confusion','Kubernetes operational warnings',boundary+' These warnings include rules and coverage checks, not ML alone.')
    confusion(y,ml,'cluster-ml-confusion','Kubernetes Isolation Forest warnings',boundary)
    fig,ax=plt.subplots(figsize=(8,4))
    for s,values in latency.items():ax.plot(seconds,values,marker='.',label=s)
    ax.axvspan(*interval,color='orange',alpha=.18,label='Control proxy interval')
    ax.set(xlabel='Seconds from phase start',ylabel='p95 request latency (ms)',title='Measured inventory delay and upstream propagation');ax.legend()
    export(fig,'cluster-delay-timeline','Measured service latency during a cluster fault',boundary+' Latency comes from captured request spans.')
    fig,ax=plt.subplots(figsize=(7,4))
    labels=['Native (18 trials)','Kubernetes (9 trials)'];a=[18,9];b=[10,4];x=np.arange(2)
    ax.bar(x-.18,a,.36,label='Operational approach');ax.bar(x+.18,b,.36,label='Isolation Forest only')
    ax.set(xticks=x,xticklabels=labels,ylabel='Detected controlled trials',title='Trial detection: keep operational and ML results separate');ax.legend()
    export(fig,'trial-detection-comparison','Controlled trial detection','Native: original college-PC HTTP experiment. Kubernetes: laptop held-out fault trials. Different deployments, calibrated native models and sample sizes; no claim of production recall or a paired model improvement.')
    payload=dict(figures=figures,metrics=metrics,source_sha256=sources,training_performed=False,
                 boundary='Saved development and controlled-lab evaluation; no external or production reliability claim.')
    (OUT/'index.json').write_text(json.dumps(payload,indent=2),encoding='utf-8')
    (OUT/'figure-data.json').write_text(json.dumps(dict(metrics=metrics,source_sha256=sources),indent=2),encoding='utf-8')
    with zipfile.ZipFile(OUT/'report-figures.zip','w',zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(OUT.iterdir()):
            if path.suffix in ('.png','.svg','.pdf','.json'):archive.write(path,path.name)
    print(json.dumps(dict(figures=len(figures),directory=str(OUT),training=False)))


if __name__=='__main__':main()
