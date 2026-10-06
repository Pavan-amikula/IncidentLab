# Isolated Kubernetes application staging

For the CPU laptop workflow use [the transfer guide](../TRANSFER_README.md) and
`Run-Cluster.ps1` (Check, Deploy, Quick, Validate). It includes fresh cluster healthy
calibration and timestamped pod-log capture; actual cluster execution remains pending.

These assets are rendered and parsed locally; the container image and cluster
deployment have **not** been built or executed. The Windows account cannot enable
the required container environment. They are reviewable next-stage assets, not
evidence of successful Kubernetes collection or fault validation.

`Dockerfile.testbed` packages only the standard-library HTTP application. The manifest
creates one namespace, three Deployments and three internal ClusterIP Services.
Each service uses readiness/liveness probes, a writable bounded telemetry volume,
an unprivileged UID, a read-only root filesystem and no service-account token.
The application uses DNS service names for downstream calls and emits its raw request
event schema on stdout. These choices follow the official [Service documentation](https://kubernetes.io/docs/concepts/services-networking/service/)
and [HTTP probe documentation](https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/).

## When an isolated local container environment is available

```powershell
docker build -f deployment/Dockerfile.testbed -t incidentlab-testbed:dev .
kind create cluster --name incidentlab
kind load docker-image incidentlab-testbed:dev --name incidentlab
.\.venv\Scripts\python.exe scripts\render_kubernetes_testbed.py --image incidentlab-testbed:dev
kubectl --context kind-incidentlab apply -f deployment/kubernetes-testbed.yaml
kubectl --context kind-incidentlab -n incidentlab-testbed rollout status deployment/frontend
kubectl --context kind-incidentlab -n incidentlab-testbed rollout status deployment/checkout
kubectl --context kind-incidentlab -n incidentlab-testbed rollout status deployment/inventory
kubectl --context kind-incidentlab -n incidentlab-testbed port-forward service/frontend 8891:8891
```

Pin the built base/application image digests and record cluster, runtime and CLI
versions before a research release. The dev tag and source-only YAML are staging
references. Default volume/resource limits need measurement on the real cluster.

After healthy collection and independent deployment calibration, the bounded fault
runner can operate only in the explicit `kind-incidentlab` context and owned namespace:

```powershell
.\deployment\Run-ClusterFault.ps1 -Target checkout -Fault delay -DurationSeconds 30
.\deployment\Run-ClusterFault.ps1 -Target inventory -Fault unavailable -DurationSeconds 30
```

It resets the control or replicas in `finally`. Archived command times are **not**
automatically exact failure-onset labels: observe and review actual workload impact,
service endpoint changes and recovery. Do not feed control metadata into inference.

## Acceptance still required

Run healthy workloads at several loads, export/deduplicate pod telemetry across
restarts, validate raw adapters against measured request traces, fit fresh healthy
references and hold out entire later trials. Archive scheduling separately, including
unsuccessful injections and recovery failures. Add cluster resource/orchestration
events, workload shifts and repeated faults before making an orchestration claim.
The native HTTP model is not deployment-calibrated for this cluster.

Pod logs are available through `kubectl logs`; durable cluster-log collection,
restart handling and workload/control timing must be implemented and validated on
the running cluster. The manifest alone does not complete that delivery gate.
