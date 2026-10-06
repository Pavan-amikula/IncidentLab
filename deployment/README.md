# Deployment staging

`Dockerfile` and `compose.yaml` package CPU research serving. They mount existing
processed data read-only and local artifacts for checkpoints/prediction persistence.
Only localhost port 8769 is published, leaving the current Windows server on 8768.
The image runs one worker as an unprivileged user. Source/runtime dependencies are
pinned, but the base image tag needs a digest when the image is built for a release.

**Not built or executed yet:** this machine has no Docker engine or Linux/WSL.
These files are staging assets, not evidence of a successful container deployment.
They do not create a microservice application, collectors or Kubernetes fault trials.

After the environment is available, from the project root:

```powershell
.\Check-LiveEnvironment.ps1
docker compose -f deployment/compose.yaml config
docker compose -f deployment/compose.yaml up --build -d
docker compose -f deployment/compose.yaml ps
```

Verify the dashboard at localhost:8769, feature serving and prediction persistence
before treating packaging as complete. Linux mount ownership must permit the container
UID to write the artifact directory. Windows Docker bind behavior must also be tested.

For this computer, the required external setup is enabling WSL 2 and providing a
working container engine. WSL setup requires an administrator terminal and can request
a restart. The coding session is not elevated and will not restart the user's machine.
Use [Docker's official Windows setup](https://docs.docker.com/desktop/setup/install/windows-install/)
and [Microsoft's WSL setup](https://learn.microsoft.com/windows/wsl/install).
Docker's first startup includes an agreement for the user to review.

## Live experiment acceptance plan

1. Deploy an isolated, pinned Online Boutique revision on a dedicated local cluster.
   Record cluster/app/collector versions and service identity mappings.
2. Collect at least several hours of healthy telemetry across load levels before
   calibrating deployment thresholds. Keep sensor/metric units explicit.
3. Implement and verify the raw-to-feature adapter against offline aggregates.
   Archive raw telemetry, normalized windows and timing without fault labels in inputs.
4. Inject bounded CPU, memory, delay and dependency-unavailability faults only in the
   isolated app. Record schedules separately; reset and verify recovery between runs.
5. Hold out complete trials and later healthy periods. Compare GRU and boosting at
   a matched false-alert budget, including localization, missing telemetry, delay,
   p95 total latency and deduplicated operator alerts.
6. Require external-dataset results, failure analysis and evidence-grounded diagnosis
   before selecting the final model or presenting an industrial deployment claim.

## Native application and cluster testbed

The native three-service HTTP pipeline has executed without administrator access; see [its workflow](../docs/native_live_workflow.md). A separate three-service Kubernetes manifest and scoped resettable fault runner are prepared in [KUBERNETES.md](KUBERNETES.md). Cluster execution and restart-safe cluster collection remain unverified.
