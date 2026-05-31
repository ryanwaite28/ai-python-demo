# Homelab DevSecOps Retrospective
## k3s Cluster — PVC Migrations, Storage Architecture, CI/CD Hardening, and Kubernetes Mastery

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Session 1 — NFS Migration and Pipeline Foundation](#session-1--nfs-migration-and-pipeline-foundation)
3. [Session 2 — Longhorn Migration and CI/CD Compliance](#session-2--longhorn-migration-and-cicd-compliance)
4. [Key Problems Solved](#key-problems-solved)
5. [Architecture Reference](#architecture-reference)
6. [Lessons Learned](#lessons-learned)
7. [Becoming a Kubernetes SME](#becoming-a-kubernetes-sme)

---

## Project Overview

A two-node k3s homelab cluster running a full DevSecOps stack on a Dell
Optiplex-9020 (control plane) and a dedicated worker node. Over two major
sessions the cluster storage was evolved from a failing local-path HDD through
centralized NFS, and then to a tiered Longhorn + NFS architecture that matches
each storage class to its workload type. The CI/CD pipeline infrastructure was
hardened in parallel, a comprehensive deployment framework was established for
multi-language applications, and all app pipelines were brought into compliance
with a unified security-scanning standard.

**Cluster nodes:**

| Node | Role | IP |
|------|------|----|
| ryanwaite-optiplex-9020 | Control plane + DevSecOps workloads | 10.0.0.251 |
| rmw-home-server | App workloads | 10.0.0.250 |

**Domain:** `*.rmwhs.space` via Cloudflare tunnel → nginx-external ingress

**Storage evolution:**
```
Session 1: local-path HDD  →  NFS (Synology)
Session 2: NFS (databases) →  Longhorn (SSD) + NFS (blobs, kept)
```

---

## Session 1 — NFS Migration and Pipeline Foundation

### 1. Full PVC Migration (local-path HDD → NFS)

Migrated all 20+ PVCs from a failing local-path provisioner on a noisy 2TB HDD
to a Synology NAS at `/volume1/kubernetes/volumes`. This was the most complex
operation of the session involving:

- Writing a migration script with dry-run support
- Handling immutable StatefulSet `volumeClaimTemplates` via `--cascade=orphan`
- Rebinding PVs to renamed PVCs using `claimRef` JSON patches
- Dealing with H2 database corruption in Dependency-Track
- Force-removing stuck Terminating PVCs via finalizer patches
- Fixing `/etc/fstab` emergency mode after physical HDD removal
- Restoring inotify limits after reboot

**Final state:** 25 NFS PVCs, zero local-path PVCs, noisy HDD removed.

### 2. Jenkins Pipeline Hardening

- Refactored `k8s-infrastructure` Jenkinsfile with `agent none` + shift-left
  preflight stage running on the Jenkins controller before any pod is
  provisioned
- Added `--cascade=orphan` StatefulSet deletion before every helm upgrade to
  handle immutable `volumeClaimTemplates`
- Added `--timeout 10m` to prometheus helm upgrade
- Fixed kube-prometheus-stack admission webhook stuck in Terminating state
- Created `build-agent.Jenkinsfile` — separate pipeline for building the
  jenkins-agent image with shift-left checks on controller + DinD pod for build

### 3. Jenkins Agent Image Architecture (original)

Split a monolithic all-language jenkins-agent image into purpose-built images:

| Image | Purpose |
|-------|---------|
| `jenkins-agent-base` | kubectl, helm, docker CLI, sonar-scanner, trivy |
| `jenkins-agent-python` | base + Python 3, pip, virtualenv (Django) |
| `jenkins-agent-ruby` | base + Ruby, bundler (Rails) |
| `jenkins-agent-jvm` | base + Corretto JDK 21, Maven (Hilla/Vaadin) |
| `jenkins-agent-node` | base + Node 20, pnpm, yarn (Next.js) |
| `jenkins-agent-dotnet` | base + .NET SDK 8.0 (ASP.NET) |
| `jenkins-agent-php` | base + PHP, Composer (Laravel) |
| `jenkins-agent-go` | base + Go 1.22, Buffalo CLI |

Each language image inherits `FROM jenkins-agent-base` so all DevSecOps tools
are available in every pipeline without duplication.

**Note:** The language-specific images were later deprecated — see Session 2,
section 3.

### 4. Multi-Agent Pipeline Pattern

Established a pipeline pattern using `agent none` at the top level with
sequential stage groups, each declaring its own agent:

```
Jenkins controller  →  Preflight (file/YAML checks, free)
jenkins-agent-python → Tests, SonarQube scan, quality gate
jenkins-agent-base   → Docker build, Trivy scan, Harbor push, kubectl deploy
```

This avoids the "one fat image for everything" anti-pattern and keeps each
image small and purpose-built.

### 5. Secrets Management Standard

Established Vault as the standard for all app secrets:

- Vault path convention: `kv/<app-id>` (must be created before pipeline runs)
- `withVault` in Jenkinsfile injects secrets as env vars at runtime
- Jenkins credentials reserved for platform-only use (harbor, gitlab, sonarqube,
  vault-auth-token)
- Kubernetes secret manifests in repos are templates only — no values committed

### 6. Naming Convention

Established a collision-safe naming standard: `<app-purpose>-<qualifier>`.
The same identifier flows through namespace, Harbor image, Vault path,
Kubernetes secret, SonarQube project key, and subdomain.

### 7. Documentation Generated (Session 1)

| Document | Purpose |
|----------|---------|
| `KUBERNETES_CONTEXT.md` | Full deployment context for new apps — Jenkinsfile template, manifest templates, secrets pattern, observability, internal DNS |
| `RETRO.md` | This document |
| `Jenkinsfile` | k8s-infrastructure pipeline with shift-left preflight |
| `build-agent.Jenkinsfile` | Jenkins agent image build pipeline |
| `Dockerfile.base` + language variants | Split agent image Dockerfiles |
| `JENKINS_POD_TEMPLATES.md` | Step-by-step guide for configuring pod templates in Jenkins |
| `migrate-pvcs.sh` | PVC migration script |
| `finalize-pvc-migration.sh` | PVC rebind and cleanup script |

---

## Session 2 — Longhorn Migration and CI/CD Compliance

### 1. NFS → Longhorn Storage Migration

Migrated all database and stateful I/O workloads off NFS onto Longhorn-backed
SSD storage. The root cause requiring this migration: PostgreSQL on NFS produces
intermittent SIGPIPE crashes (exit code 141) when the NFS TCP connection drops,
causing 1–2 minute service outages across Harbor, GitLab, and other NFS-dependent
services.

**Migration approach — tiered by workload type:**

| Workload type | Storage | Reasoning |
|---------------|---------|-----------|
| Databases (PostgreSQL, MySQL, Redis) | Longhorn SSD | fsync-sensitive; NFS causes SIGPIPE crashes |
| Jenkins home | Longhorn SSD | Job history and config need durability |
| Vault data | Longhorn SSD | Raft consensus requires low-latency disk I/O |
| Harbor registry blobs, GitLab repos | NFS (kept) | Large sequential reads/writes; NFS is fine for blobs |
| WordPress uploads, wp-content | NFS (kept) | Static file serving; NFS latency is acceptable |
| Grafana, OpenSearch, Prometheus | Longhorn SSD | Metrics/log ingestion requires consistent IOPS |

**Two StorageClasses created:**
- `longhorn` — Optiplex 953.9GB SATA SSD (`/mnt/longhorn`), tagged `optiplex` — DevSecOps workloads
- `longhorn-apps` — Worker node LVM root disk (`/mnt/longhorn-apps`, tagged `worker`) — app namespace workloads

**Longhorn backup target:** NAS `nfs://10.0.0.241/volume1/kubernetes/nodes-internal-data`
with hourly snapshots, 24-snapshot retention — NFS repurposed as backup tier
instead of primary data path.

### 2. Worker Node Disk Topology Deviation

The migration plan assumed `rmw-home-server` had a separate dedicated disk for
Longhorn app volumes. This was wrong. The actual topology:

- `sda` — 256GB LVM root disk (OS + all data). No free partitions.
- `sdb` — 50GB ext4, Harbor registry volume (`/mnt/harbor-data`). Do not touch.

The plan created `/mnt/longhorn-apps` as a directory on the same LVM filesystem
as `/mnt/longhorn`. Longhorn detected both paths sharing the same filesystem UUID
and immediately marked `longhorn-apps` as `DiskNotReady`, faulting all app volumes.

**Resolution:** Removed the duplicate disk entry. Enabled scheduling on the
existing `default-disk-bc4b04f40b7d9` entry (root LVM disk, tagged `worker`).
Longhorn re-scheduled all faulted replicas; volumes recovered within minutes.
The `longhorn-apps` StorageClass was unchanged — it still targets `nodeSelector:
worker / diskSelector: worker`, which now correctly resolves to the root disk.

**Lesson:** Always `lsblk` and verify filesystem UUIDs before adding Longhorn disk
entries. Longhorn uses the filesystem UUID to identify disks — two paths on the
same filesystem register as duplicates.

### 3. Jenkins Agent Architecture Simplified

The language-specific agent images (`jenkins-agent-python`, `jenkins-agent-ruby`,
etc.) were deprecated. Apps now ship their own language toolchain inside their
application `Dockerfile`. The Jenkins agent only needs to drive the pipeline
(kubectl, docker CLI, sonar-scanner, trivy), which is exactly what
`jenkins-agent-base` provides.

**Before:** Two images per pipeline: `jenkins-agent-python` (or other language)
for test/scan stages + `jenkins-agent-base` for build/push/deploy.

**After:** Single image, `jenkins-agent-base`, for the entire pipeline. Each app's
`Dockerfile` carries its own runtime and build tools.

This eliminates the maintenance overhead of keeping 8 language images in sync with
`jenkins-agent-base` and removes the failure mode where a language image is stale.

### 4. DinD Readiness Check Fix

The `build-agent.Jenkinsfile` was checking `docker --version` to wait for the
Docker-in-Docker daemon to be ready. This was wrong:

- `docker --version` runs the local CLI binary and exits immediately — it does
  **not** contact the daemon socket.
- `docker login` connects to an external registry (Harbor), not the local DinD
  socket — so it succeeding means nothing about DinD readiness.
- `docker build` was the first command to actually touch the DinD socket, which
  hadn't started yet, causing `Cannot connect to Docker daemon` failures.

**Fix:** Changed the readiness check to `docker ps`, which requires an active
daemon connection, with a 60-second timeout:

```groovy
sh '''
    echo "Waiting for Docker daemon..."
    timeout 60 sh -c 'until docker ps > /dev/null 2>&1; do sleep 2; done'
    echo "Docker daemon ready."
'''
```

The same correction was made in `KUBERNETES_CONTEXT.md` which had documented the
wrong check as canonical guidance.

**Root cause of two consecutive failed runs:** All commits were local-only and had
never been pushed to GitLab. Jenkins was pulling stale code from the remote.
Always confirm `git push` before triggering a Jenkins run.

### 5. SKIP_SONAR / SKIP_QUALITY_GATE / SKIP_TRIVY Standard

All app pipelines must declare three boolean build parameters:

```groovy
parameters {
  booleanParam(name: 'SKIP_SONAR',        defaultValue: false, description: 'Skip SonarQube scan')
  booleanParam(name: 'SKIP_QUALITY_GATE', defaultValue: false, description: 'Skip SonarQube quality gate wait')
  booleanParam(name: 'SKIP_TRIVY',        defaultValue: false, description: 'Skip Trivy image scan')
}
```

Each scan stage must be gated with a `when` expression:

```groovy
stage('SonarQube Scan') {
  when { expression { !params.SKIP_SONAR } }
  ...
}
stage('Quality Gate') {
  when { expression { !params.SKIP_SONAR && !params.SKIP_QUALITY_GATE } }
  ...
}
stage('Trivy Scan') {
  when { expression { !params.SKIP_TRIVY } }
  ...
}
```

Pipelines that hardcode scan skipping via `echo "Skipping..."; exit 0` or
commented-out scanner blocks are non-compliant. The params give operators a
documented, repeatable way to skip scans without editing the Jenkinsfile.

### 6. WordPress Jenkinsfile Compliance Fixes

Both WordPress repos (`rmw-wp-personal-blog`, `rmw-wp-agency-consulting`) were
non-compliant:

**rmw-wp-personal-blog:** Missing `parameters` block entirely. Missing SonarQube
and Quality Gate stages. Trivy scan used the wrong approach (no `--server` flag,
which required a full local DB download). Harbor secret creation used
`withCredentials` against a Jenkins credential instead of Vault.

**rmw-wp-agency-consulting:** Had all four scan stages but every one was hardcoded
to skip with `echo "Skipping for now; exiting..."`. No `parameters` block. Trivy
stages attempted `docker pull` (requires DinD, not available in these pipelines).
Harbor secret used `withCredentials` (non-compliant).

Both files were fully rewritten to: add the params block, enable actual scanner
code behind `when` expressions, use `trivy image --server ${TRIVY_SERVER}` (no
docker pull needed — Trivy server mode scans the upstream image directly), and
switch Harbor secret creation to Vault (`kv/common-app-deploy-secrets`).

### 7. Vault as the Standard for Harbor Credentials

The `harbor-credentials` Jenkins credential is for platform use only (the
`build-agent.Jenkinsfile` which builds and pushes agent images). App Jenkinsfiles
must not reference it via `withCredentials`. App pipelines retrieve Harbor
credentials from Vault path `kv/common-app-deploy-secrets` via `withVault`.

This distinction matters for audit: using Jenkins credentials in app pipelines
bypasses Vault's access control and audit log. Vault is the single source of
truth for all app secrets, including Harbor registry credentials.

### 8. Documentation and Repo Sync

`KUBERNETES_CONTEXT.md` carries the canonical cluster reference. Every time it
changes in `k8s-infrastructure`, it must be copied to all app repos. This session
identified and fixed two gaps in `KUBERNETES_CONTEXT.md` before syncing:

1. PostgreSQL manifest template was missing `subPath: pgdata` despite documenting
   the requirement. Any new app following the template would hit CrashLoopBackOff
   on first deploy to Longhorn.

2. DinD readiness guidance documented `docker --version` (wrong) instead of
   `docker ps`.

Both gaps were fixed before syncing to all 13 app repos.

---

## Key Problems Solved

### Immutable StatefulSet volumeClaimTemplates

**Problem:** Helm cannot patch StatefulSets when `volumeClaimTemplates` change.
**Solution:** Delete the StatefulSet with `--cascade=orphan` (preserves PVCs)
before every `helm upgrade`. The StatefulSet is recreated by helm; existing PVCs
are reattached by name.

```bash
kubectl delete statefulset <name> -n <namespace> \
  --cascade=orphan --ignore-not-found=true
helm upgrade --install ...
```

### PVC Renaming (rebinding a PV to a new PVC name)

**Problem:** PVCs cannot be renamed. StatefulSets bind to PVCs by exact name
from `volumeClaimTemplates`.
**Solution:** Four-step rebind:
1. Set PV `reclaimPolicy: Retain`
2. Remove `claimRef` from PV using JSON patch
3. Delete the old PVC
4. Create new PVC with correct name, specifying `volumeName` to bind to the
   existing PV

```bash
kubectl patch pv <pv-name> --type=json \
  -p='[{"op":"remove","path":"/spec/claimRef"}]'
```

### Stuck Terminating PVCs

**Problem:** PVCs stuck in Terminating state block operations.
**Solution:** Remove the `kubernetes.io/pvc-protection` finalizer:

```bash
kubectl patch pvc <name> -n <namespace> \
  -p '{"metadata":{"finalizers":[]}}' --type=merge
```

### Jenkins Agent Image Missing After Harbor Data Loss

**Problem:** Harbor registry storage wiped during migration; all pushed images
lost. All pipelines fail with `ErrImagePull`.
**Solution:** Rebuild from Mac over VPN and push directly:

```bash
docker buildx build --platform linux/amd64 \
  -t harbor.rmwhs.space/devops/jenkins-agent:latest --push .
```

Long-term: the `build-agent.Jenkinsfile` pipeline exists to rebuild
automatically. Harbor registry data should be treated as ephemeral — images
must always be rebuildable from source.

### Emergency Mode on Boot After HDD Removal

**Problem:** `/etc/fstab` had an entry for the removed HDD; system boots to
emergency mode.
**Solution:** Edit `/etc/fstab` from the emergency shell and comment out the
dead mount entry, then `exit` to continue boot.

### inotify Limits After Reboot

**Problem:** Fluent Bit sidecars crash with `Too many open files` after reboot
because inotify limits reset.
**Solution:** Persist the limits in sysctl:

```bash
echo "fs.inotify.max_user_instances=512" | sudo tee -a /etc/sysctl.d/99-inotify.conf
echo "fs.inotify.max_user_watches=524288" | sudo tee -a /etc/sysctl.d/99-inotify.conf
sudo sysctl --system
```

### Helm Pre-upgrade Hook Timeout (kube-prometheus-stack)

**Problem:** `kube-prometheus-stack-admission` ServiceAccount stuck in
Terminating causes pre-upgrade hooks to fail.
**Solution:** Force delete the stuck ServiceAccount:

```bash
kubectl delete serviceaccount kube-prometheus-stack-admission \
  -n monitoring --force --grace-period=0
```

### PostgreSQL Refusing to Initialize on a Fresh Longhorn Volume

**Problem:** Fresh Longhorn volumes present an ext4 filesystem with a
`lost+found` directory at root. PostgreSQL's `initdb` aborts with
`"directory is not empty"` even when the only content is a system directory.

**Solution:** Add `subPath: pgdata` to the container volumeMount:

```yaml
volumeMounts:
- name: postgres-storage
  mountPath: /var/lib/postgresql/data
  subPath: pgdata
```

Kubernetes mounts only the `pgdata/` subdirectory of the volume at the data
path. `lost+found` stays at the volume root, which the container never sees.

The same pattern applies to MySQL (`subPath: mysql`) and any other database
engine that checks whether its data directory is empty before initializing.

**What NOT to do:** Do not set both `subPath: pgdata` and the `PGDATA`
environment variable. `PGDATA` overrides where PostgreSQL looks for data. If
`PGDATA=/var/lib/postgresql/data/pgdata` and `subPath: pgdata` are both set,
PostgreSQL looks at `volume/pgdata/pgdata/` — double-nested — and finds nothing.
Use `subPath` alone.

### YAML Indentation Bugs from Batch `sed` Operations

**Problem:** When `subPath: pgdata` was added via `sed`, the resulting line was
at 14-space indentation (appearing as a child of the `mountPath` line) instead
of 10-space (sibling of `mountPath`). Invalid Kubernetes YAML — `kubectl apply`
either rejects or silently ignores the field.

**Lesson:** Never use `sed` or batch text substitution to insert YAML. Indentation
is structural in YAML and a single off-by-N-spaces error changes the meaning of
the document without producing an obvious error. Read each file and use structural
edits instead.

Affected repos: ai-aspnet-app, ai-buffalo-app, ai-drogon-app, ai-hilla-app,
ai-laravel-app, ai-loco-app, ai-nextjs-app. All 7 corrected.

### Rolling Update Deadlock on PVC Reattachment

**Problem:** After recreating a Postgres PVC for `ai-python-demo`, the deployment
had no `nodeSelector` or `tolerations` for the worker node. The pod scheduled to
the control plane, but the Longhorn volume (on the worker's disk) couldn't attach
cross-node. The old ReplicaSet kept recreating the misscheduled pod, preventing
the volume from being released for a corrected pod.

**Solution:** Scale to 0, wait for all pods to terminate (forces volume detach),
add `toleration` + `nodeSelector` to the deployment spec, then scale to 1.

**Rule:** Any PVC created on `longhorn-apps` (worker disk) must have its pod
spec include `nodeSelector: rmw-home-server` and `tolerations:
dedicated=apps:NoSchedule`. The volume can only attach to one node at a time,
and it must be the node holding the disk.

### Longhorn StorageClass Parameters Are Immutable

**Problem:** Attempted to add `nodeSelector` and `diskSelector` to the existing
`longhorn` StorageClass to prevent DevSecOps volumes from accidentally scheduling
to the worker node. `kubectl patch` returned `Forbidden: updates to parameters
are forbidden`. Deleting and re-applying was also blocked — ArgoCD immediately
recreated it from the Helm ConfigMap.

**Current state:** `longhorn-apps` is correctly pinned to the worker. The
`longhorn` StorageClass has no explicit node/disk selector. In practice safe
(worker disk is tagged `worker`, not `optiplex`), but the proper fix requires
updating Longhorn Helm values to set the default StorageClass parameters at
install time. Deferred to next Longhorn upgrade.

**Lesson:** StorageClass `parameters` are immutable after creation. If you need
to change them, you must delete the StorageClass and recreate it — which only
works if no PVCs are currently using it, and ArgoCD is not managing it. Plan
StorageClass configuration carefully before first use.

### DinD Daemon Readiness — The Wrong Check

**Problem:** Pipeline waited for `docker --version` before running `docker build`.
`docker --version` exits immediately (reads a local binary, no socket contact).
`docker build` was the first real daemon call, which failed because DinD hadn't
finished starting.

**Solution:** Wait on `docker ps`, which requires an active socket connection:

```bash
timeout 60 sh -c 'until docker ps > /dev/null 2>&1; do sleep 2; done'
```

**Lesson:** `docker --version` and `docker info` have different behavior:
- `docker --version` — reads the installed CLI binary, no daemon needed
- `docker info` / `docker ps` — connects to the daemon socket, fails if not ready

Always use `docker ps` or `docker info` as the DinD readiness gate.

### Commits Pushed Only Locally — Jenkins Pulling Stale Code

**Problem:** Jenkins ran two consecutive builds from stale code because all commits
existed only in the local working directory and had never been pushed to GitLab.
The pipeline output appeared correct (no errors in checkout) but was running old
logic.

**Rule:** Always `git push` before triggering a Jenkins pipeline. If a pipeline
run produces unexpected results, run `git log origin/main..HEAD` to check for
unpushed commits before investigating anything else.

---

## Architecture Reference

### Storage

| Class | Backend | Workload type | Default |
|-------|---------|---------------|---------|
| `longhorn` | Optiplex 953.9GB SSD (`/mnt/longhorn`) | DevSecOps databases, Vault, Jenkins, monitoring | ✅ Yes |
| `longhorn-apps` | Worker LVM root disk (`/mnt/longhorn-apps`) | App namespace databases (Postgres, MySQL, Redis) | ❌ |
| `nfs-client` | Synology NAS `/volume1/kubernetes/volumes` | Large blobs: Harbor registry, GitLab repos, WordPress uploads | ❌ |
| `local-path` | Local disk | ❌ Deprecated — do not use |

**Storage rules:**
- Databases, caches, message queues → Longhorn (SSD, fsync-safe)
- Large blob/object storage, media, artifacts → NFS
- etcd and k3s state → local SSD only (never NFS or Longhorn-managed)
- Always set `storageClassName` explicitly; never rely on the default silently

**Backup:** Longhorn volumes back up hourly to
`nfs://10.0.0.241/volume1/kubernetes/nodes-internal-data`, 24 snapshots retained.

### Networking

- Cloudflare tunnel → `*.rmwhs.space` → NodePort 32080 → nginx-external ingress
- TLS terminated at Cloudflare (SSL Full) — always set `ssl-redirect: "false"`
- IngressClass: `nginx-external`

### Internal DNS

| Service | DNS |
|---------|-----|
| GitLab | `gitlab-webservice-default.devops.svc.cluster.local:8181` |
| Harbor | `harbor-core.devops.svc.cluster.local:80` |
| Jenkins | `jenkins.devops.svc.cluster.local:8080` |
| SonarQube | `sonarqube-sonarqube.security.svc.cluster.local:9000` |
| Vault | `vault.devops.svc.cluster.local:8200` |
| Prometheus | `kube-prometheus-stack-prometheus.monitoring.svc.cluster.local:9090` |
| OpenSearch | `opensearch.monitoring.svc.cluster.local:9200` |
| Tempo gRPC | `tempo.monitoring.svc.cluster.local:4317` |
| Trivy server | `trivy-server.security.svc.cluster.local:4954` |

### Post-Restart Checklist

After any cluster restart, always:
1. Unseal Vault at `https://vault.rmwhs.space`
2. Verify all pods: `kubectl get pods --all-namespaces | grep -v Running | grep -v Completed`
3. Check Argo CD sync: `kubectl get applications -n argocd`
4. Restart cloudflared Docker container on the home server
5. Verify Longhorn volume health at `https://longhorn.rmwhs.space`

### Current Cluster Final State

| Component | Status | Storage |
|-----------|--------|---------|
| GitLab | ✅ Running | Longhorn (postgres) + NFS (repos, minio) |
| Harbor | ✅ Running | Longhorn (postgres, redis) + NFS (registry blobs) |
| Jenkins | ✅ Running | Longhorn |
| Vault | ✅ Running (manual unseal) | Longhorn |
| Prometheus + Grafana | ✅ Running | Longhorn (prometheus, alertmanager) + NFS (grafana) |
| OpenSearch + Dashboards | ✅ Running | Longhorn |
| Tempo | ✅ Running | Longhorn |
| Fluent Bit | ✅ Running | — |
| SonarQube | ✅ Running | Longhorn |
| Dependency-Track | ✅ Running | Longhorn |
| Kyverno | ✅ Running | — |
| Trivy Operator | ✅ Running | — |
| ZAP | ✅ Running | — |
| Argo CD | ✅ Running | — |
| homepulse-monitor | ✅ Running | longhorn-apps |
| pulseboard-ryanwaite | ✅ Running | longhorn-apps |
| snipply-hilla | ✅ Running | longhorn-apps |
| listo-reading-tracker | ✅ Running | longhorn-apps |
| rmw-wp-personal-blog | ✅ Running | longhorn-apps (mysql) + NFS (wp-content) |
| rmw-wp-agency-consulting | ✅ Running | longhorn-apps (mysql) + NFS (wp-content) |
| ai-python-demo | ✅ Running | longhorn-apps |
| OTel Demo | ✅ Running | — |

---

## Lessons Learned

**Match storage class to workload type.** NFS is not safe for databases —
SIGPIPE crashes under network jitter are a structural problem, not a tuning
problem. Databases need low-latency, consistent fsync guarantees that block
storage (Longhorn, EBS, etc.) provides. Large sequential blobs (container
images, git repos, media files) are fine on NFS. The rule: databases on block
storage, blobs on object/file storage.

**etcd must never go on NFS.** etcd requires low-latency fsync guarantees that
NFS cannot provide. A network hiccup between the control plane and NAS would
take down the entire cluster. Keep etcd on local SSD.

**StatefulSets are the hardest resource to manage in Kubernetes.** Their
`volumeClaimTemplates` are immutable by design — plan PVC naming carefully
before first deployment. Renaming later requires manual intervention.
StorageClass `parameters` are also immutable after creation.

**Verify hardware assumptions before writing the migration plan.** The worker
node disk topology was assumed, not verified. This caused the Longhorn duplicate
filesystem UUID failure. `lsblk`, `df -h`, and `blkid` cost 30 seconds and
prevent multi-hour recovery steps.

**Documentation templates must be exercised, not just written.** The
`KUBERNETES_CONTEXT.md` template for PostgreSQL was missing `subPath: pgdata`
despite documenting the requirement in the text. A template that isn't deployed
and verified will drift. Whenever a template is updated, deploy a real workload
from it to confirm it works end to end.

**Never use `sed` to insert YAML fields.** Indentation is structural in YAML.
Batch text manipulation inserts lines at the wrong depth silently. Read each
file, understand its structure, and use a structured editor.

**Harbor registry data is ephemeral.** Treat Harbor like a cache, not a source
of truth. All images must be rebuildable from source. The `build-agent` pipeline
exists for exactly this reason.

**Vault-first secrets is worth the setup cost.** Having all app secrets in
Vault from the start means no secret sprawl, no credentials in Jenkinsfiles,
and a single place to rotate values. The `withVault` pattern is clean and
explicit.

**Shift-left checks save pod spin-up cost.** Running file existence and YAML
lint checks on the Jenkins controller before provisioning a Kubernetes pod
catches the most common pipeline failures (missing files, bad YAML) instantly
and for free. A pod spin-up costs 30–60 seconds and image pull bandwidth —
shift-left checks cost milliseconds.

**One identifier, used everywhere.** Using the same `app-id` for the namespace,
image name, Vault path, secret name, SonarQube project, and subdomain
eliminates an entire class of misconfiguration bugs. Enforce this as a standard.

**Always push before triggering CI.** Unpushed commits are invisible to Jenkins.
The pipeline appears to run but is operating on stale code. Before reporting a
pipeline failure, run `git log origin/main..HEAD` to verify the expected commits
are on the remote.

**Parameters beat commented-out code.** A stage that is sometimes skipped should
be gated by a build parameter, not surrounded by `echo "skipping..."` guards or
commented out. Parameters appear in the Jenkins UI, are documented, and can be
set per-run without touching the Jenkinsfile. Commented-out code is invisible to
operators and requires a code change to re-enable.

**`docker ps` — not `docker --version` — signals DinD readiness.** `docker
--version` is a local binary call. `docker ps` proves the daemon socket is
accepting connections. Use `docker ps` as the readiness gate in every DinD
pipeline.

---

## Becoming a Kubernetes SME

This section is a guide for anyone who wants to develop deep, production-grade
Kubernetes expertise — not just enough to get things running, but enough to
reason about why things work, predict failure modes, and design reliable systems.

---

### How to Think About Kubernetes

The most important mental model shift: **Kubernetes is a control loop, not a
script runner.**

When you run `kubectl apply`, you are not telling Kubernetes to do something.
You are declaring the desired state of the world. Kubernetes continuously
reconciles the actual state of the cluster toward that desired state. This
distinction changes how you troubleshoot, design, and reason about everything.

Think of Kubernetes like a thermostat, not a light switch:
- A light switch executes a command: "turn on now"
- A thermostat maintains a state: "keep it at 72°F, always"

Every controller in Kubernetes — the Deployment controller, the StatefulSet
controller, the PVC controller — is a thermostat. It watches what exists, compares
it to what should exist, and takes action to close the gap. This is called the
**reconciliation loop** and it is the foundation of everything.

**Practical implication:** When something is wrong in Kubernetes, the question
is never "what command failed?" — it is "what is the gap between desired state
and actual state, and why is the reconciliation loop failing to close it?"

---

### Core Concepts to Master (in order)

**1. The API and objects**

Everything in Kubernetes is an object with a spec (desired state) and a status
(actual state). Learn to read both:

```bash
kubectl get pod <name> -o yaml   # see spec AND status
kubectl describe pod <name>      # human-readable status + events
```

The `Events` section of `kubectl describe` is the single most useful
troubleshooting tool in Kubernetes. Read it first, always.

**2. Pods, Deployments, StatefulSets — and why they differ**

- A **Pod** is the unit of execution. It is ephemeral. Never manage Pods directly.
- A **Deployment** manages stateless Pods. Any pod can replace any other pod.
  Rolling updates work by creating new pods and deleting old ones.
- A **StatefulSet** manages stateful Pods. Each pod has a stable identity (name,
  DNS, storage). Pods are created and deleted in order. `volumeClaimTemplates`
  are immutable because changing them would change the identity contract.

The immutability of StatefulSet `volumeClaimTemplates` caused the most
complex work in these sessions. Understanding *why* it is immutable (stable
identity is the guarantee StatefulSets exist to provide) makes the
`--cascade=orphan` workaround make sense instead of feeling like a hack.

**3. Storage: PVs, PVCs, StorageClasses, and subPath**

Think of it as a four-layer system:
- **StorageClass** — the "type" of storage available (longhorn, longhorn-apps,
  nfs-client)
- **PersistentVolume (PV)** — a specific piece of storage that exists
- **PersistentVolumeClaim (PVC)** — a request for storage by a workload
- **volumeMount.subPath** — an optional path within the volume to mount, rather
  than the volume root

The binding between PVC and PV is like a lease agreement. Once bound, it is
exclusive. The `claimRef` on a PV is the lock. The finalizer on a PVC is what
keeps it from being deleted while a pod is using it.

`subPath` matters specifically for databases on Longhorn. Longhorn volumes expose
an ext4 filesystem with `lost+found` at the root. PostgreSQL (and MySQL) check
whether their data directory is empty before initializing. `subPath: pgdata`
gives the container a clean empty subdirectory, invisible to `lost+found`.

**4. Networking: Services, DNS, Ingress**

Kubernetes networking has three layers:
- **Pod network** — every pod gets an IP, pods can talk to each other
- **Service** — a stable virtual IP that load-balances to pods. Pods come and
  go; the Service IP stays constant.
- **Ingress** — routes external HTTP/HTTPS traffic to Services based on hostname
  and path rules

Internal DNS format: `<service>.<namespace>.svc.cluster.local:<port>`. Every
service is reachable by this name from anywhere in the cluster. This is why
Jenkins can reach SonarQube at `sonarqube-sonarqube.security.svc.cluster.local:9000`
and Trivy server at `trivy-server.security.svc.cluster.local:4954`
without knowing their IPs.

**5. RBAC and Security**

Role-Based Access Control is how Kubernetes controls what pods and users can do.
In this cluster the `jenkins-agent` ServiceAccount has permissions to apply
manifests. Understanding RBAC means understanding:
- ServiceAccounts (identity for pods)
- Roles and ClusterRoles (what actions are allowed)
- RoleBindings and ClusterRoleBindings (who gets which role)

The security principle is least privilege: each workload should have exactly
the permissions it needs and no more.

**6. Node scheduling: taints, tolerations, nodeSelector, affinity**

Taints mark nodes as restricted. Tolerations allow pods to schedule onto tainted
nodes. NodeSelector requires a pod to land on a specific node. In this cluster:

```yaml
# Required for all app pods — worker node is tainted dedicated=apps:NoSchedule
tolerations:
- key: dedicated
  operator: Equal
  value: apps
  effect: NoSchedule
nodeSelector:
  kubernetes.io/hostname: rmw-home-server
```

Missing `tolerations` causes pods to stay `Pending` with "had untolerated taint".
Missing `nodeSelector` when a PVC is on the worker disk causes the pod to schedule
to the wrong node, where the volume cannot attach.

**7. Helm and GitOps**

Helm is a package manager for Kubernetes manifests. A chart is a parameterized
set of manifests. `helm upgrade --install` is idempotent — it creates if not
present, upgrades if present. The `--cascade=orphan` pattern used throughout
these sessions is a technique for working around Helm's inability to modify
immutable fields.

Argo CD implements GitOps — the Git repo is the source of truth, and Argo CD
continuously reconciles the cluster toward what the repo says. Think of Argo CD
as another reconciliation loop, at the application level, on top of Kubernetes'
own reconciliation loops.

---

### Industry-Standard Best Practices

**Immutability**
- Containers should be immutable. Never `kubectl exec` and change running state.
  Change the image, redeploy.
- ConfigMaps and Secrets should be versioned or use the `immutable` field. Avoid
  mutating them in place in production.

**Resource limits**
Every container should have `resources.requests` and `resources.limits` defined.
Requests affect scheduling (which node gets the pod). Limits affect runtime
behavior (OOMKilled if exceeded). Pods without requests are unpredictable in
resource-constrained clusters.

**Health probes**
Every Deployment should have `readinessProbe` and `livenessProbe`. Readiness
controls when a pod receives traffic. Liveness controls when a pod is restarted.
A missing readiness probe means traffic goes to pods that aren't ready, causing
errors during deployments.

**Namespace isolation**
Each application gets its own namespace. This provides blast radius containment,
RBAC boundaries, and resource quota isolation. The naming convention used in
this cluster (`pulseboard-ryanwaite`, not `pulseboard`) prevents collision and
makes namespace purpose obvious.

**Secrets management**
Never commit secrets to Git. Never put secrets in ConfigMaps (they are not
encrypted at rest). Use Vault (as established in this cluster) with the
`withVault` → `kubectl create secret --from-literal` pipeline pattern. Rotate
secrets regularly.

**Storage**
- Use Longhorn (or equivalent block storage) for databases, caches, and anything
  requiring consistent fsync performance
- Use NFS/object storage for large blobs, artifacts, and media
- Never use `hostPath` or `local-path` for production data
- etcd is the exception — it must be on fast local storage, never NFS
- Always set `storageClassName` explicitly. Never rely on the default silently
- Always use `subPath` for database engines on Longhorn to avoid the
  `lost+found` initialization failure

**Image hygiene**
- Pin base image versions in production (`jenkins/inbound-agent:3355.v388858a_47b_33`
  not `jenkins/inbound-agent:latest`)
- Scan images with Trivy before pushing to registry (`trivy image --server
  <trivy-server>` in client/server mode — no local DB download)
- Use a private registry (Harbor) — never pull directly from Docker Hub in
  production pipelines
- Treat the registry as a cache. All images must be rebuildable from source.

**GitOps discipline**
- The Git repo is the source of truth, not the cluster
- Never `kubectl apply` manually in production — always go through the pipeline
- Use Argo CD `selfHeal: true` to prevent configuration drift
- Exception: Vault unsealing and emergency recovery require manual kubectl
- Always push to remote before triggering CI — Jenkins pulls from the remote,
  not your local working directory

**CI/CD pipeline standards**
- Every pipeline must declare `SKIP_SONAR`, `SKIP_QUALITY_GATE`, and `SKIP_TRIVY`
  boolean parameters with `defaultValue: false`
- Scan stages must be gated with `when { expression { !params.SKIP_* } }`, not
  commented out or hardcoded to skip
- Harbor credentials in app pipelines come from Vault (`kv/common-app-deploy-secrets`),
  not from Jenkins `withCredentials`
- DinD readiness gate must use `docker ps`, not `docker --version`

---

### Effective Troubleshooting Techniques

**The universal troubleshooting sequence:**

```
1. kubectl get <resource> -n <namespace>
   → Is it there? What's its status?

2. kubectl describe <resource> <name> -n <namespace>
   → Read the Events section. This explains why.

3. kubectl logs <pod> -n <namespace> [--previous] [-c <container>]
   → What did the process say before it failed?

4. kubectl get events -n <namespace> --sort-by='.lastTimestamp'
   → Broader view of what happened recently in the namespace
```

**Pod not starting — decision tree:**

```
Pending    → scheduling problem (resources, taints, node selector)
             kubectl describe pod → look for "Insufficient cpu/memory"
             or "had untolerated taint" or "node(s) didn't match node selector"

Init:0/1   → init container failing
             kubectl logs <pod> -c <init-container-name>

CrashLoopBackOff → container starts but crashes
             kubectl logs <pod> --previous (logs from last crash)
             Common causes for PostgreSQL on Longhorn:
               - Missing subPath → "directory is not empty" (lost+found)
               - Wrong PGDATA + subPath → double-nested path, data not found

ImagePullBackOff → can't pull the image
             kubectl describe pod → check Events for specific error
             Is the image name correct? Does the pull secret exist?
             Can the node reach the registry?

OOMKilled  → container exceeded memory limit
             increase resources.limits.memory or fix the memory leak
```

**PVC not binding — decision tree:**

```
Pending → StorageClass doesn't exist, or provisioner can't create the volume
          kubectl describe pvc → check Events
          kubectl get storageclass → does the named class exist?
          For Longhorn: is the target node disk healthy? Check longhorn.rmwhs.space

Terminating → finalizer preventing deletion
              kubectl patch pvc ... -p '{"metadata":{"finalizers":[]}}' --type=merge

Lost → PV was deleted while PVC still exists
       Recreate the PV or delete the PVC and let it reprovision
```

**Longhorn volume not attaching — decision tree:**

```
Volume stuck in "attaching" state:
  → Is the pod on the right node? Longhorn RWO volumes attach to one node only.
  → Does the pod have the correct nodeSelector + tolerations?
  → Is there another pod holding the volume? Scale old deployment to 0 first.

Volume shows "DiskNotReady" on a node:
  → Check for duplicate filesystem UUID (two Longhorn paths on same filesystem)
  → kubectl -n longhorn-system get node.longhorn.io <node> -o yaml
  → Remove the bad disk entry via Longhorn UI → Node → Edit → remove disk
```

**Helm upgrade failing:**

```
"forbidden: updates to statefulset spec"
→ immutable field changed. Delete StatefulSet --cascade=orphan then retry.

"pre-upgrade hooks failed"
→ a hook Job or ServiceAccount is stuck. Find and force-delete it.
  kubectl get jobs -n <namespace>
  kubectl delete serviceaccount <name> -n <namespace> --force --grace-period=0

"context deadline exceeded"
→ add --timeout 10m to the helm command

"storageclass parameters are forbidden"
→ StorageClass parameters are immutable. Must delete and recreate the class,
  which requires no PVCs currently using it. With ArgoCD managing it, this
  requires a Helm values change at next upgrade.
```

**Useful diagnostic one-liners:**

```bash
# All non-running, non-completed pods across the cluster
kubectl get pods --all-namespaces | grep -v Running | grep -v Completed

# What PVC is each pod in a namespace actually using?
kubectl get pods -n <ns> -o json | \
  jq -r '.items[] | .metadata.name + " → " + \
  (.spec.volumes[]? | select(.persistentVolumeClaim) | \
  .persistentVolumeClaim.claimName)'

# All PVCs on a specific storage class
kubectl get pvc --all-namespaces -o wide | grep longhorn-apps

# Events sorted by time (what just happened?)
kubectl get events -n <namespace> --sort-by='.lastTimestamp' | tail -20

# Resource usage by node
kubectl top nodes

# Resource usage by pod
kubectl top pods -n <namespace>

# Check what's actually in a Longhorn volume (mount it from a debug pod)
kubectl run -it --rm debug --image=alpine --restart=Never -- sh
# Inside: apk add e2fsprogs; mount /dev/sdb1 /mnt; ls /mnt

# Verify unpushed commits before blaming a pipeline
git log origin/main..HEAD

# Check that a YAML file is valid and parseable by Kubernetes
kubectl apply --dry-run=client -f <file>.yaml
```

---

### How to Build Deep Expertise

**Stage 1 — Understand the primitives**
Build and break things manually before using Helm or operators. Create a
Deployment, Service, and Ingress by hand with raw YAML. Scale it. Break it.
Watch the reconciliation loop fix it. Delete a pod and watch it recreate.
This builds intuition for what Kubernetes is actually doing under the hood.

**Stage 2 — Understand failure modes**
Intentionally cause failures: fill a PVC to 100%, kill the control plane node,
delete a PV while a pod is using it, set an impossible resource request. Then
recover. Every failure mode you encounter in production you will have seen
before. These sessions covered real failure modes: emergency mode boot, H2
database corruption, stuck Terminating resources, inotify exhaustion,
Longhorn duplicate filesystem UUID, PostgreSQL `lost+found` init failure,
rolling update deadlock on PVC reattachment.

**Stage 3 — Read the source, read the docs**
The Kubernetes documentation is unusually good. The API reference explains
every field. The concepts section explains every design decision. When something
behaves unexpectedly, the answer is almost always in the docs. The StatefulSet
`volumeClaimTemplates` immutability, the finalizer behavior on PVCs, the
`--cascade=orphan` flag, the `subPath` volumeMount option — all documented.

**Stage 4 — Operate real workloads**
Running stateful production workloads — databases, message queues, caches — is
where real expertise develops. GitLab, Harbor, OpenSearch, Prometheus, Vault —
all operated in this cluster — are the same workloads running in enterprise
environments. The problems encountered here are real production problems.

**Stage 5 — Learn the ecosystem**
Kubernetes expertise means understanding the surrounding tools:
- **Helm** — packaging and upgrade lifecycle
- **Argo CD** — GitOps and drift detection
- **Longhorn** — distributed block storage with snapshot and backup
- **Prometheus + Grafana** — metrics and alerting
- **Fluent Bit + OpenSearch** — log aggregation
- **Vault** — secrets management
- **Trivy + SonarQube** — security scanning (image vulnerabilities + code quality)
- **Cert-manager** — TLS certificate automation
- **Kyverno** — policy enforcement
- **Jenkins** — CI/CD pipeline orchestration with Kubernetes pod agents

This cluster runs all of them. Operating them together under real conditions —
including the failures — is worth more than any certification exam.

**Stage 6 — Own the pipeline**
Running applications on Kubernetes is different from understanding Kubernetes.
Owning the full path from code commit to running pod — version control, CI/CD
pipeline, image build, security scanning, secrets injection, manifest apply,
rollout verification — reveals the integration failure modes that theory misses.
These sessions covered the full path for 13+ applications across two programming
language families and two deployment patterns.

**The SME mindset:**
A Kubernetes SME does not memorize commands. They understand the control loop
model deeply enough to reason about any situation from first principles. When
something breaks, they ask: "what is the desired state, what is the actual
state, and what is preventing reconciliation?" The answer to that question
leads to the fix, every time.

The corollary: when something works but shouldn't, ask the same question in
reverse — "why is the reconciliation loop not reverting this?" Understanding
ArgoCD's `selfHeal`, Kubernetes finalizers, and PVC protection all come from
this mode of thinking.
