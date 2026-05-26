# Kubernetes Cluster Context

This document provides the context needed to build a Jenkins CI/CD pipeline and Kubernetes manifests for deploying applications to the homelab k3s cluster at `rmwhs.space`.

Use this document alongside your project's `PROJECT.md` and `.claude/CLAUDE.md` when building deployment pipelines.

> **Security rule:** Never hardcode credentials, passwords, or secrets in any file — including Jenkinsfiles, manifests, shell scripts, or documentation. **Vault is the standard for all app secrets.** See the [Secrets Management](#secrets-management) section.

## Naming Convention

All app identifiers — namespace, image name, Vault path, Kubernetes secret name, SonarQube project key, and subdomain — must be **specific and unique** to avoid collisions across apps. Generic names like `wordpress` or `blog` are not acceptable since multiple instances may exist.

**Format:** `<app-purpose>-<owner-or-context>` or `<app-purpose>-<distinguishing-qualifier>`

| ❌ Too generic | ✅ Specific |
|---------------|------------|
| `wordpress` | `wordpress-personal-blog` |
| `blog` | `blog-ryanwaite` |
| `postgres` | `postgres-personal-blog` |
| `api` | `api-inventory-service` |

This identifier is used consistently across:

| Resource | Pattern | Example |
|----------|---------|---------|
| Kubernetes namespace | `<app-id>` | `wordpress-personal-blog` |
| Harbor image | `harbor.rmwhs.space/apps/<app-id>` | `harbor.rmwhs.space/apps/wordpress-personal-blog` |
| Vault path | `kv/<app-id>` | `kv/wordpress-personal-blog` |
| Kubernetes secret | `<app-id>-secret` | `wordpress-personal-blog-secret` |
| SonarQube project key | `<app-id>` | `wordpress-personal-blog` |
| Subdomain | `<app-id>.rmwhs.space` | `wordpress-personal-blog.rmwhs.space` |
| Jenkins `IMAGE_NAME` env var | `<app-id>` | `wordpress-personal-blog` |

In the Jenkinsfile, set this once in the `environment` block and reuse everywhere:
```groovy
environment {
  IMAGE_NAME    = 'wordpress-personal-blog'   // ← specific, unique app identifier
  K8S_NAMESPACE = 'wordpress-personal-blog'   // ← matches IMAGE_NAME
  SONAR_PROJECT = 'wordpress-personal-blog'   // ← matches IMAGE_NAME
  // ...
}
```

---

## Cluster Overview

| Property | Value |
|----------|-------|
| Distribution | k3s |
| Control Plane | `ryanwaite-optiplex-9020` (10.0.0.251) |
| Worker Node | `rmw-home-server` (10.0.0.250) |
| Domain | `*.rmwhs.space` (Cloudflare tunnel → nginx-external ingress) |
| GitOps | Argo CD 3.4.2 (app-of-apps pattern) |
| Git Source | GitLab at `gitlab.rmwhs.space` (internal: `http://gitlab-webservice-default.devops.svc.cluster.local:8181`) |

### Node Scheduling

| Node | Role | Taint |
|------|------|-------|
| `ryanwaite-optiplex-9020` | Control plane + DevSecOps workloads | None (schedules freely) |
| `rmw-home-server` | App workloads | `dedicated=apps:NoSchedule` |

To schedule on `rmw-home-server`:
```yaml
tolerations:
- key: dedicated
  operator: Equal
  value: apps
  effect: NoSchedule
nodeSelector:
  kubernetes.io/hostname: rmw-home-server
```

To schedule on the Optiplex (default, no toleration needed):
```yaml
nodeSelector:
  kubernetes.io/hostname: ryanwaite-optiplex-9020
```

---

## Secrets Management

**All secrets must flow through Vault. Never hardcode credentials in any file.**

### Vault is the Standard

Vault is the primary secrets manager for all applications. Every app maintains its own secrets at a dedicated Vault path. Jenkins credentials are reserved for platform-level access only (Harbor, GitLab, SonarQube).

| Property | Value |
|----------|-------|
| External URL | `https://vault.rmwhs.space` |
| Internal URL | `http://vault.devops.svc.cluster.local:8200` |
| Jenkins Credential ID | `vault-auth-token` |
| Secret engine | KV v2 (`kv/`) |

> Vault requires manual unsealing after every restart. Keep unseal keys secure and offline.

### App Secret Convention

Each app owns a path under `kv/` using the same specific app identifier used for the namespace and image name:

```
kv/wordpress-personal-blog    ← wordpress personal blog secrets
kv/api-inventory-service      ← inventory API secrets
kv/ai-python-demo             ← ai python demo secrets
```

> The Vault path **must match** the `IMAGE_NAME` / `K8S_NAMESPACE` value in the Jenkinsfile. Using `kv/${IMAGE_NAME}` in the pipeline ensures they always stay in sync.

### Step 1 — Create Vault Secrets Before Running the Pipeline

**This must be done before the first pipeline run.** The pipeline will fail if the Vault path does not exist.

1. Go to `https://vault.rmwhs.space` and log in
2. Navigate to **Secrets → kv → Create secret**
3. Path: `myapp` (matches the app name)
4. Add key/value pairs for all secrets the app needs, e.g.:
   - `secret_key` → `<value>`
   - `db_password` → `<value>`
   - `db_user` → `<value>`
   - `db_name` → `<value>`
5. Save

Or via CLI:
```bash
vault kv put kv/myapp \
  secret_key="..." \
  db_password="..." \
  db_user="..." \
  db_name="..."
```

### Step 2 — Pull Secrets in the Jenkinsfile with `withVault`

Use the `withVault` step to inject secrets as environment variables at pipeline runtime:

```groovy
withVault(
  configuration: [
    vaultUrl: 'https://vault.rmwhs.space',
    vaultCredentialId: 'vault-auth-token'
  ],
  vaultSecrets: [[
    path: 'kv/myapp',
    secretValues: [
      [envVar: 'SECRET_KEY',   vaultKey: 'secret_key'],
      [envVar: 'DB_PASSWORD',  vaultKey: 'db_password'],
      [envVar: 'DB_USER',      vaultKey: 'db_user'],
      [envVar: 'DB_NAME',      vaultKey: 'db_name']
    ]
  ]]
) {
  sh '''
    kubectl create secret generic myapp-secret \
      --from-literal=SECRET_KEY=${SECRET_KEY} \
      --from-literal=DB_PASSWORD=${DB_PASSWORD} \
      --from-literal=DB_USER=${DB_USER} \
      --from-literal=DB_NAME=${DB_NAME} \
      --namespace=${K8S_NAMESPACE} \
      --dry-run=client -o yaml | kubectl apply -f -
  '''
}
```

Multiple Vault paths can be combined in one `withVault` block:

```groovy
withVault(
  configuration: [
    vaultUrl: 'https://vault.rmwhs.space',
    vaultCredentialId: 'vault-auth-token'
  ],
  vaultSecrets: [
    [path: 'kv/myapp', secretValues: [
      [envVar: 'SECRET_KEY', vaultKey: 'secret_key'],
      [envVar: 'DB_PASSWORD', vaultKey: 'db_password']
    ]],
    [path: 'kv/shared', secretValues: [
      [envVar: 'SMTP_PASSWORD', vaultKey: 'smtp_password']
    ]]
  ]
) {
  sh '...'
}
```

### Injecting Vault Secrets into Kubernetes Secrets

The expected pattern is: Vault → `withVault` in Jenkins → `kubectl create secret` → pod `secretKeyRef`. This keeps Vault as the single source of truth while making secrets available to Kubernetes workloads without any agent needing direct Vault access at runtime.

```
Vault (kv/myapp)
      ↓ withVault in Jenkinsfile
Environment variables in pipeline
      ↓ kubectl create secret --from-literal
Kubernetes Secret in app namespace
      ↓ secretKeyRef in pod spec
App container environment
```

It is acceptable (and recommended) to have a dedicated pipeline stage that reads from Vault and writes to a Kubernetes secret. The secret manifest committed to the repo is a **template only** — no values.

### Jenkins Credentials (Platform Use Only)

Jenkins credentials are reserved for platform-level access. App secrets go in Vault.

| Credential ID | Type | Used For |
|--------------|------|---------|
| `vault-auth-token` | Secret Text | Authenticating `withVault` calls |
| `harbor-credentials` | Username/Password | Docker login to Harbor + image pulls |
| `gitlab-root-token` | Username/Password | GitLab API access and repo cloning |
| `sonarqube-token` | Secret Text | SonarQube analysis authentication |

#### Using `harbor-credentials` in the Pipeline

`harbor-credentials` is pre-configured as a Kubernetes imagePullSecret in `jenkins-agents`. Propagate it to new namespaces via `withCredentials` — never hardcode the password:

```groovy
stage('Prepare K8s Namespace & Registry Secret') {
  steps {
    withCredentials([usernamePassword(
      credentialsId: 'harbor-credentials',
      usernameVariable: 'HARBOR_USER',
      passwordVariable: 'HARBOR_PASS'
    )]) {
      sh '''
        kubectl create namespace ${K8S_NAMESPACE} --dry-run=client -o yaml | kubectl apply -f -
        kubectl create secret docker-registry harbor-credentials \
          --docker-server=${HARBOR_REGISTRY} \
          --docker-username=${HARBOR_USER} \
          --docker-password=${HARBOR_PASS} \
          --namespace=${K8S_NAMESPACE} \
          --dry-run=client -o yaml | kubectl apply -f -
      '''
    }
  }
}
```

### Kubernetes Secret Manifests

Secret manifest files in the repo are **templates only** — structure with no values. Real values are injected by the pipeline from Vault:

```yaml
# k8s/secret.yaml — TEMPLATE ONLY, commit this
# Real values injected by Jenkinsfile via withVault + kubectl --from-literal
apiVersion: v1
kind: Secret
metadata:
  name: myapp-secret
  namespace: myapp
type: Opaque
# No stringData here — populated by the pipeline's 'Apply App Secret' stage
```

---

## Storage

### Storage Classes

| Class | Provisioner | Default | Backend |
|-------|-------------|---------|---------|
| `nfs-client` | nfs-subdir-external-provisioner | ✅ Yes | Synology NAS — `/volume1/kubernetes/volumes` |
| `local-path` | rancher.io/local-path | ❌ No | Local disk — **deprecated, do not use** |

**Always use `nfs-client` for new PVCs.** All application storage lives on the NAS for centralized backup and replication. Omitting `storageClassName` is fine since `nfs-client` is the default.

### PVC Example
```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: myapp-data
  namespace: myapp
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: nfs-client
  resources:
    requests:
      storage: 10Gi
```

---

## Networking

### Traffic Flow

| Path | Route |
|------|-------|
| External (`*.rmwhs.space`) | Cloudflare Tunnel → NodePort 32080 → `nginx-external` ingress |
| Internal (within cluster) | Direct ClusterIP / CoreDNS rewrite |

**Cloudflare Tunnel limitations:**
- The wildcard `*.rmwhs.space` record is a **tunnel type** — not a proxied A record and cannot be grey-clouded or bypassed with DNS-only mode
- **100 MB upload limit** per request enforced by Cloudflare Tunnel — large image pushes (e.g., to Harbor) from outside the cluster fail with HTTP 413
- TLS passes through the tunnel to nginx-ingress, which terminates it using certs issued by cert-manager

### TLS / cert-manager

TLS certificates for all ingresses are issued by **cert-manager** using Let's Encrypt ACME with Cloudflare DNS01 challenge. cert-manager is deployed in the `cert-manager` namespace and managed via Argo CD.

| Property | Value |
|----------|-------|
| ClusterIssuer | `letsencrypt-prod` |
| Challenge type | DNS01 via Cloudflare |
| API token secret | `cloudflare-api-token` in **`cert-manager` namespace** |
| cert-manager namespace | `cert-manager` |

> **GitLab cert-manager conflict:** The GitLab Helm chart deploys its own cert-manager pods in the `devops` namespace (`gitlab-certmanager`, `gitlab-certmanager-cainjector`, `gitlab-certmanager-webhook`). These steal the `kube-system/cert-manager-controller` leader lease and prevent the dedicated cert-manager from issuing any certificates. Resolution: scale all three GitLab cert-manager deployments to 0 replicas and delete both `gitlab-certmanager-webhook` ValidatingWebhookConfiguration and MutatingWebhookConfiguration.

> **ACME account mismatch:** If cert-manager instances are switched (e.g., from GitLab's to the dedicated one), delete all existing `challenge`, `order`, and `certificaterequest` objects cluster-wide before retrying. Let's Encrypt returns 403 if a different ACME account tries to finalize orders created by a different instance. cert-manager recreates them with the correct account automatically.

### Ingress

- **IngressClass**: `nginx-external`
- **ssl-redirect**: always `"true"` — nginx-ingress handles the HTTP→HTTPS redirect
- Every ingress must include the `cert-manager.io/cluster-issuer` annotation and a `tls` spec so cert-manager provisions the certificate automatically

### Ingress Template

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: myapp
  namespace: myapp
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    nginx.ingress.kubernetes.io/proxy-read-timeout: "300"
    nginx.ingress.kubernetes.io/proxy-body-size: "10m"
spec:
  ingressClassName: nginx-external
  tls:
  - hosts:
    - myapp.rmwhs.space
    secretName: myapp-tls
  rules:
  - host: myapp.rmwhs.space
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: myapp
            port:
              number: 8080
```

> Set `proxy-body-size: "0"` (unlimited) for services that receive large uploads, such as Harbor or file upload APIs.

### Harbor Internal Routing (CoreDNS Split-Horizon)

Harbor's token auth always generates HTTPS token URLs using `harbor.rmwhs.space` (derived from `externalURL`). Pods inside the cluster must resolve `harbor.rmwhs.space` to the cluster-internal nginx-ingress service — not to the Cloudflare Tunnel endpoint — to avoid the 100 MB upload limit and tunnel latency.

A CoreDNS rewrite rule in the `coredns-custom` ConfigMap in `kube-system` handles this cluster-wide:

```yaml
# kube-system ConfigMap: coredns-custom
# key: harbor.override
rewrite name harbor.rmwhs.space ingress-nginx-controller.ingress-nginx.svc.cluster.local
```

This dynamically follows the nginx-ingress ClusterIP (no hardcoded IP). All `docker push` / `docker pull` operations from Jenkins agent pods and other in-cluster workloads route through the cluster network, bypassing Cloudflare entirely.

> **Do not** use `hostAliases` with a static IP for Harbor — ClusterIPs can be reassigned and are harder to maintain than the CoreDNS rewrite.

The `coredns-custom` ConfigMap is managed in this repo and applied via Argo CD. After any change, CoreDNS picks up the rewrite without a pod restart.

---

## Container Registry

| Property | Value |
|----------|-------|
| Registry | `harbor.rmwhs.space` |
| Projects | `apps/` (application images), `devops/` (tooling images) |
| Pull Secret Name | `harbor-credentials` |
| Jenkins Credential ID | `harbor-credentials` |

> **In-cluster pushes bypass Cloudflare** via CoreDNS rewrite — see [Harbor Internal Routing](#harbor-internal-routing-coredns-split-horizon). All `docker push` commands from Jenkins agents go through the cluster network and are not subject to Cloudflare's 100 MB limit.

### Image Naming Convention
```
harbor.rmwhs.space/apps/<app-name>:<build-number>
harbor.rmwhs.space/apps/<app-name>:latest
```

### Referencing in Deployment
```yaml
spec:
  imagePullSecrets:
  - name: harbor-credentials   # must exist in the app namespace
  containers:
  - name: myapp
    image: harbor.rmwhs.space/apps/myapp:latest
```

> The `harbor-credentials` secret must be created in the app namespace by the pipeline before the deployment is applied. See the [Jenkins CI/CD](#jenkins-cicd) section.

---

## Jenkins CI/CD

| Property | Value |
|----------|-------|
| External URL | `https://jenkins.rmwhs.space` |
| Internal URL | `http://jenkins.devops.svc.cluster.local:8080` |
| Agent Namespace | `jenkins-agents` |

### Jenkins Agent Image

There is **one agent image for all application pipelines**:

| Image | Harbor Path | Tools |
|-------|-------------|-------|
| `jenkins-agent-base` | `harbor.rmwhs.space/devops/jenkins-agent-base:latest` | `kubectl`, `helm`, `docker CLI`, `sonar-scanner 6.2.1`, `trivy`, `yq`, `jq`, `git` |

The agent is **deliberately language-agnostic.** It does not ship Node, Python, Go, JVM, PHP, Ruby, or .NET runtimes. Every app brings its own toolchain inside its Dockerfile — see [Application Repository Layout](#application-repository-layout) and [Dockerfile Conventions](#dockerfile-conventions).

> **Deprecation:** The language-specific agent images (`jenkins-agent-node`, `jenkins-agent-python`, `jenkins-agent-go`, `jenkins-agent-jvm`, `jenkins-agent-php`, `jenkins-agent-ruby`, `jenkins-agent-dotnet`) are deprecated. New app pipelines must use `jenkins-agent-base` only. Do not create new language-specific agent variants.

#### Why a single agent

- The agent stays small and fast to pull
- No language-version drift between the agent and the runtime image (the runtime image *is* the test environment)
- Apps choose their own stack without waiting for a coordinated agent update
- Test failures fail the `docker build` step naturally — no separate test stage to maintain

### Application Repository Layout

**Each application lives in its own Git repository.** This repo (`k8s-infrastructure`) holds platform configuration only; app code, app Dockerfiles, and app pipelines all live in per-app repos.

| File / Folder in app repo | Purpose |
|---------------------------|---------|
| `Dockerfile` | Builds, tests, and packages the app. The language toolchain lives here. |
| `Jenkinsfile` | CI/CD pipeline — follows the [Standard Jenkinsfile Template](#standard-jenkinsfile-template) |
| `k8s/` | Kubernetes manifests (deployment, service, ingress, configmap, secret template, servicemonitor, …) |
| Source code | Organized by language convention |

The agent runs the pipeline; the Dockerfile runs the build and tests; the manifests describe the deployment. Each piece has one job.

### Dockerfile Conventions

Every app's Dockerfile **must** satisfy two requirements:

1. **Unit tests run inside the build** — typically in a multi-stage build's "build" stage, before producing the final runtime image. A failed test fails `docker build`, which fails the pipeline at the `Build & Login` stage — before scan, push, or deploy. This is the test gate.
2. **A `SKIP_TESTS` build arg short-circuits the tests** — for fast debug iteration only. The Jenkinsfile exposes a matching `SKIP_TESTS` boolean parameter and forwards it via `--build-arg`.

#### Multi-stage Dockerfile example

```dockerfile
# syntax=docker/dockerfile:1
FROM python:3.13-slim AS build

ARG SKIP_TESTS=false

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# Tests run as part of the build. SKIP_TESTS=true skips them (debug only).
RUN if [ "$SKIP_TESTS" = "true" ]; then \
      echo "WARNING: tests skipped (SKIP_TESTS=true)"; \
    else \
      pytest tests/ -q; \
    fi

FROM python:3.13-slim AS runtime
WORKDIR /app
COPY --from=build /app /app
CMD ["python", "main.py"]
```

The same pattern works for any language:

```dockerfile
# Node example
ARG SKIP_TESTS=false
RUN if [ "$SKIP_TESTS" = "true" ]; then echo "tests skipped"; else npm test; fi

# Go example
ARG SKIP_TESTS=false
RUN if [ "$SKIP_TESTS" = "true" ]; then echo "tests skipped"; else go test ./...; fi
```

> `SKIP_TESTS=true` is for **debug iterations only.** Never merge or deploy an image built with tests skipped. The pipeline parameter exists to unblock pipeline debugging (e.g. when chasing a Harbor or k8s issue), not as a routine flag.

### DinD (Docker-in-Docker) Requirements

All pipelines that build Docker images require a DinD sidecar. Key requirements:

- **`--mtu=1400`** is mandatory in DinD daemon args. k3s overlay network MTU is ~1450; DinD defaults to 1500. The mismatch causes `curl: (35) Connection reset by peer` on large downloads (Helm, OS packages) inside the DinD daemon during image builds.
- **`DOCKER_TLS_CERTDIR: ""`** disables TLS on the Docker socket — use unencrypted TCP on port 2375 between the builder and DinD containers.
- The builder container sets `DOCKER_HOST: tcp://localhost:2375`.

```yaml
- name: dind
  image: docker:24-dind
  securityContext:
    privileged: true
  args:
  - "--mtu=1400"
  env:
  - name: DOCKER_TLS_CERTDIR
    value: ""
```

### Build Parameters

Use a `parameters` block in every Jenkinsfile to give operators control over what runs in each pipeline execution. Sensible defaults mean routine runs need no changes; operators can activate optional stages when needed.

**Universal parameters** (all pipelines):

| Parameter | Type | Default | Purpose |
|-----------|------|---------|---------|
| `SKIP_TESTS` | Boolean | `false` | Skip the in-Dockerfile unit-test step via `--build-arg SKIP_TESTS=true`. **Debug iteration only — never merge or deploy a build made with tests skipped.** |
| `SKIP_TRIVY` | Boolean | `false` | Skip Trivy vulnerability scan (useful when iterating quickly or debugging other stages) |

**App-type-specific parameters** (add as applicable based on the app's architecture):

| Parameter | Type | Default | Use When |
|-----------|------|---------|----------|
| `RUN_MIGRATION` | Boolean | `true` | App has a relational database — run schema migrations on every deploy |
| `RESET_DB` | Boolean | `false` | Wipe and recreate the database (**destructive** — data loss, use intentionally) |
| `SEED_DB` | Boolean | `false` | Run database seed/fixture data after migration |
| `CLEAR_CACHE` | Boolean | `false` | App uses Redis — flush the cache on deploy |
| `DEPLOY_ALL` | Boolean | `false` | Force redeploy all pods even if the image tag did not change |

**Design rules:**
- Destructive operations (`RESET_DB`, `CLEAR_CACHE`) must default to `false`
- Safe-to-repeat operations (`RUN_MIGRATION`) can default to `true`
- Each parameter gates exactly one stage with `when { expression { params.PARAM_NAME } }`
- Add only the parameters that apply to the app's architecture — don't add `RUN_MIGRATION` to a stateless app

### Trivy Server (Scan API)

Trivy runs as a long-lived **server in the `security` namespace**, analogous to SonarQube. Pipelines connect to it as a client and never download or maintain the vulnerability DB themselves. This eliminates DB download time, parallel scan lock contention, and per-pipeline cache management entirely.

| Property | Value |
|----------|-------|
| Internal URL | `http://trivy-server.security.svc.cluster.local:4954` |
| Image | `aquasec/trivy:0.55.2` |
| Cache | PVC `trivy-server-cache` (10Gi, `nfs-client`) — DB persists across restarts |
| Manifests | `apps/security/trivy-server/` (Deployment + Service + PVC) |
| Argo CD App | `apps/argocd/argocd-trivy-server.yaml` |

The server auto-refreshes its vulnerability DB on a schedule. Clients don't need write access to the DB.

#### Directive

**All pipelines MUST scan images via the Trivy server.** Do not download the Trivy DB inside pipelines, do not mount per-pipeline cache directories, do not pre-warm databases with shared `cp -rl` hacks. Every scan is a server call.

Pin `TRIVY_SERVER` once in the pipeline's `environment` block and reuse it:

```groovy
environment {
  TRIVY_SERVER = 'http://trivy-server.security.svc.cluster.local:4954'
  // ...
}
```

#### Pattern A — Trivy CLI in the agent (preferred for app pipelines)

The jenkins-agent images (`jenkins-agent-base` and all language variants) ship the `trivy` binary. Call it directly — no `docker run`, no `--network host`, no extra containers:

```sh
trivy image \
  --server ${TRIVY_SERVER} \
  --exit-code 0 \
  --severity HIGH,CRITICAL \
  --no-progress \
  --format table \
  ${FULL_IMAGE}
```

This works because the agent container shares the pod's network namespace and resolves cluster DNS natively. Use this pattern in every standard app pipeline.

#### Pattern B — `docker run aquasec/trivy:latest` in DinD-only builders (e.g. `build-agent.Jenkinsfile`)

When the builder container is `docker:24-cli` (no Trivy CLI present) the scan must happen in an ephemeral container. The container is spawned by DinD's daemon, which puts it on the daemon's bridge network by default — that network **cannot resolve cluster DNS**. Add `--network host` so the container shares the pod's net ns and reaches `trivy-server.security.svc.cluster.local`:

```sh
docker run --rm \
  --network host \
  -v /var/run/docker.sock:/var/run/docker.sock \
  aquasec/trivy:latest image \
  --server ${TRIVY_SERVER} \
  --exit-code 0 \
  --severity CRITICAL \
  --no-progress \
  --format table \
  --timeout 15m \
  ${FULL_IMAGE}
```

Mount `/var/run/docker.sock` so the trivy client can read the just-built image from DinD's local cache — no registry pull needed. See [build-agent.Jenkinsfile](build-agent.Jenkinsfile) for the canonical multi-image example.

#### Operational notes

- Parallel scans are safe — the server handles concurrent requests with no per-client locking.
- Never pass `--skip-db-update` or `--download-db-only` — those are server-side concerns.
- The server auto-refreshes its DB; if a fresh CVE just landed and you need to force refresh, restart the `trivy-server` deployment.
- If scans suddenly fail with "connection refused", check `kubectl rollout status deployment/trivy-server -n security` — that's almost always the cause.

### Standard Jenkinsfile Template

All app pipelines use the single `jenkins-agent-base` image. The app's Dockerfile owns the language toolchain and tests.

```groovy
pipeline {
  parameters {
    booleanParam(name: 'SKIP_TESTS',    defaultValue: false, description: 'Skip in-Dockerfile unit tests (debug only — never deploy)')
    booleanParam(name: 'SKIP_TRIVY',    defaultValue: false, description: 'Skip Trivy vulnerability scan')
    booleanParam(name: 'RUN_MIGRATION', defaultValue: true,  description: 'Run database migrations on deploy')
    // Add app-specific params: RESET_DB, CLEAR_CACHE, SEED_DB, DEPLOY_ALL, etc.
  }

  agent {
    kubernetes {
      namespace 'jenkins-agents'
      inheritFrom 'jenkins-agent'
      yaml """
apiVersion: v1
kind: Pod
spec:
  serviceAccountName: jenkins-agent
  imagePullSecrets:
  - name: harbor-credentials
  containers:
  - name: jenkins-agent
    image: harbor.rmwhs.space/devops/jenkins-agent-base:latest
    imagePullPolicy: Always
    command: [sleep]
    args: [infinity]
    tty: true
    env:
    - name: DOCKER_HOST
      value: tcp://localhost:2375
  - name: dind
    image: docker:24-dind
    securityContext:
      privileged: true
    args:
    - "--mtu=1400"
    env:
    - name: DOCKER_TLS_CERTDIR
      value: ""
"""
      defaultContainer 'jenkins-agent'
    }
  }

  environment {
    HARBOR_REGISTRY = 'harbor.rmwhs.space'
    HARBOR_PROJECT  = 'apps'
    IMAGE_NAME      = 'myapp'                          // ← replace with specific app identifier
    IMAGE_TAG       = "${BUILD_NUMBER}"
    FULL_IMAGE      = "${HARBOR_REGISTRY}/${HARBOR_PROJECT}/${IMAGE_NAME}:${IMAGE_TAG}"
    LATEST_IMAGE    = "${HARBOR_REGISTRY}/${HARBOR_PROJECT}/${IMAGE_NAME}:latest"
    SONAR_PROJECT   = 'myapp'                          // ← must match SonarQube project key
    K8S_NAMESPACE   = 'myapp'                          // ← app namespace
    TRIVY_SERVER    = 'http://trivy-server.security.svc.cluster.local:4954'
  }

  stages {

    stage('Checkout') {
      steps {
        checkout scm
        sh 'git log --oneline -5'
      }
    }

    stage('Pre-flight Checks') {
      steps {
        sh 'kubectl version --client'
        sh 'docker info'
        sh 'trivy --version'
        sh 'sonar-scanner --version'
      }
    }

    stage('Prepare K8s Namespace & Registry Secret') {
      steps {
        withCredentials([usernamePassword(
          credentialsId: 'harbor-credentials',
          usernameVariable: 'HARBOR_USER',
          passwordVariable: 'HARBOR_PASS'
        )]) {
          sh '''
            kubectl create namespace ${K8S_NAMESPACE} --dry-run=client -o yaml | kubectl apply -f -
            kubectl create secret docker-registry harbor-credentials \
              --docker-server=${HARBOR_REGISTRY} \
              --docker-username=${HARBOR_USER} \
              --docker-password=${HARBOR_PASS} \
              --namespace=${K8S_NAMESPACE} \
              --dry-run=client -o yaml | kubectl apply -f -
          '''
        }
      }
    }

    stage('Apply App Secret') {
      // Pull app secrets from Vault and inject into the cluster as a Kubernetes secret.
      // Vault path must exist before running the pipeline: kv/<app-name>
      // Add one secretValues entry per key needed by the app.
      steps {
        withVault(
          configuration: [
            vaultUrl: 'https://vault.rmwhs.space',
            vaultCredentialId: 'vault-auth-token'
          ],
          vaultSecrets: [[
            path: "kv/${IMAGE_NAME}",
            secretValues: [
              [envVar: 'SECRET_KEY',  vaultKey: 'secret_key'],
              [envVar: 'DB_PASSWORD', vaultKey: 'db_password']
              // add more keys as needed
            ]
          ]]
        ) {
          sh '''
            kubectl create secret generic ${IMAGE_NAME}-secret \
              --from-literal=SECRET_KEY=${SECRET_KEY} \
              --from-literal=DB_PASSWORD=${DB_PASSWORD} \
              --namespace=${K8S_NAMESPACE} \
              --dry-run=client -o yaml | kubectl apply -f -
          '''
        }
      }
    }

    stage('SonarQube Scan') {
      steps {
        withSonarQubeEnv('SonarQube') {
          sh '''
            sonar-scanner \
              -Dsonar.projectKey=${SONAR_PROJECT} \
              -Dsonar.projectName="${IMAGE_NAME}" \
              -Dsonar.sources=. \
              -Dsonar.exclusions=**/migrations/**,**/__pycache__/**,**/node_modules/**,**/tests/**
          '''
        }
      }
    }

    stage('Quality Gate') {
      steps {
        timeout(time: 5, unit: 'MINUTES') {
          waitForQualityGate abortPipeline: true
        }
      }
    }

    stage('Build & Login') {
      // Log in to Harbor before building so credentials persist for both build and push.
      // SKIP_TESTS is forwarded to the Dockerfile — tests run inside the build by default.
      steps {
        withCredentials([usernamePassword(
          credentialsId: 'harbor-credentials',
          usernameVariable: 'HARBOR_USER',
          passwordVariable: 'HARBOR_PASS'
        )]) {
          sh '''
            echo "${HARBOR_PASS}" | docker login ${HARBOR_REGISTRY} \
              -u ${HARBOR_USER} --password-stdin
            docker build \
              --build-arg SKIP_TESTS=${SKIP_TESTS} \
              -t ${FULL_IMAGE} \
              -t ${LATEST_IMAGE} \
              .
          '''
        }
      }
    }

    stage('Trivy Image Scan') {
      when { expression { !params.SKIP_TRIVY } }
      steps {
        sh '''
          trivy image \
            --server ${TRIVY_SERVER} \
            --exit-code 0 \
            --severity HIGH,CRITICAL \
            --no-progress \
            --format table \
            ${FULL_IMAGE}
        '''
      }
    }

    stage('Push to Harbor') {
      steps {
        sh '''
          docker push ${FULL_IMAGE}
          docker push ${LATEST_IMAGE}
        '''
      }
    }

    stage('Run Migrations') {
      when { expression { params.RUN_MIGRATION } }
      steps {
        sh '''
          kubectl apply -f k8s/migration-job.yaml -n ${K8S_NAMESPACE}
          kubectl wait --for=condition=complete job/db-migrate \
            -n ${K8S_NAMESPACE} --timeout=120s
          kubectl delete job/db-migrate -n ${K8S_NAMESPACE} --ignore-not-found
        '''
      }
    }

    stage('Deploy to Kubernetes') {
      steps {
        sh '''
          kubectl apply -f k8s/configmap.yaml
          kubectl apply -f k8s/deployment.yaml
          kubectl apply -f k8s/service.yaml
          kubectl apply -f k8s/ingress.yaml
          kubectl apply -f k8s/servicemonitor.yaml
          kubectl rollout status deployment/${IMAGE_NAME} \
            -n ${K8S_NAMESPACE} --timeout=300s
        '''
      }
    }

  }

  post {
    success {
      echo "Deployed ${FULL_IMAGE} to ${K8S_NAMESPACE} successfully."
    }
    failure {
      echo "Pipeline failed."
    }
  }
}
```

---

## SonarQube

| Property | Value |
|----------|-------|
| External URL | `https://sonarqube.rmwhs.space` |
| Internal URL | `http://sonarqube-sonarqube.security.svc.cluster.local:9000` |
| Jenkins config name | `SonarQube` |
| Webhook URL | `http://jenkins.devops.svc.cluster.local:8080/sonarqube-webhook/` |
| Jenkins Credential ID | `sonarqube-token` |

**Before running the pipeline**, create the project in SonarQube:
1. SonarQube UI → **Projects → Create Project → Manually**
2. Project key must exactly match `SONAR_PROJECT` in the Jenkinsfile
3. The webhook back to Jenkins is already configured globally

---

## Observability

### Prometheus Metrics

Expose a `/metrics` endpoint in your app and add a ServiceMonitor so Prometheus scrapes it automatically:

```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: myapp
  namespace: myapp
  labels:
    release: kube-prometheus-stack   # required label for discovery
spec:
  selector:
    matchLabels:
      app: myapp
  endpoints:
  - port: http
    path: /metrics
    interval: 15s
  namespaceSelector:
    matchNames:
    - myapp
```

Add pod annotations for annotation-based discovery (backup to ServiceMonitor):
```yaml
annotations:
  prometheus.io/scrape: "true"
  prometheus.io/path: "/metrics"
  prometheus.io/port: "8080"
```

### Log Collection (Fluent Bit Sidecar)

Add Fluent Bit as a sidecar to ship structured JSON logs to OpenSearch. The app writes dated JSON log files to a shared volume; Fluent Bit tails them and forwards to OpenSearch.

#### Fluent Bit ConfigMap
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: myapp-fluent-bit
  namespace: myapp
data:
  fluent-bit.conf: |
    [SERVICE]
        Flush         5
        Daemon        Off
        Parsers_File  /fluent-bit/etc/parsers.conf
        storage.path  /var/lib/fluent-bit/storage

    [INPUT]
        Name              tail
        Path              /logs/app.*.log
        Parser            json_log
        Tag               myapp
        Refresh_Interval  30
        DB                /var/lib/fluent-bit/tail.db
        Skip_Long_Lines   On
        Mem_Buf_Limit     5MB

    [FILTER]
        Name    modify
        Match   myapp
        Rename  level log_level

    [OUTPUT]
        Name               opensearch
        Match              myapp
        Host               opensearch.monitoring.svc.cluster.local
        Port               9200
        # Credentials injected via Kubernetes secret — see opensearch-credentials secret
        HTTP_User          ${OPENSEARCH_USER}
        HTTP_Passwd        ${OPENSEARCH_PASS}
        tls                Off
        Logstash_Format    On
        Logstash_Prefix    myapp-logs
        Logstash_DateFormat %Y.%m.%d
        Suppress_Type_Name On
        Retry_Limit        3
        storage.total_limit_size 32M

  parsers.conf: |
    [PARSER]
        Name        json_log
        Format      json
        Time_Key    timestamp
        Time_Format %Y-%m-%dT%H:%M:%S.%LZ
        Time_Keep   On
```

> OpenSearch credentials for Fluent Bit should be stored as a Kubernetes secret injected by the pipeline using the `opensearch-credentials` Jenkins credential ID. Never hardcode them in the ConfigMap.

#### Sidecar Container Spec (add to Deployment)
```yaml
# In containers:
- name: fluent-bit
  image: fluent/fluent-bit:3.2
  envFrom:
  - secretRef:
      name: opensearch-credentials   # contains OPENSEARCH_USER and OPENSEARCH_PASS
  volumeMounts:
  - name: app-logs
    mountPath: /logs
    readOnly: true
  - name: fluent-bit-config
    mountPath: /fluent-bit/etc
  - name: fluent-bit-state
    mountPath: /var/lib/fluent-bit
  resources:
    requests:
      cpu: 50m
      memory: 64Mi
    limits:
      cpu: 100m
      memory: 128Mi

# In volumes:
- name: app-logs
  emptyDir: {}
- name: fluent-bit-config
  configMap:
    name: myapp-fluent-bit
- name: fluent-bit-state
  emptyDir: {}
```

### Observability Endpoints

| Service | Internal DNS | Purpose |
|---------|-------------|---------|
| Prometheus | `kube-prometheus-stack-prometheus.monitoring.svc.cluster.local:9090` | Metrics storage |
| OpenSearch | `opensearch.monitoring.svc.cluster.local:9200` | Log storage |
| Tempo gRPC | `tempo.monitoring.svc.cluster.local:4317` | Trace ingestion (OTLP) |
| Tempo HTTP | `tempo.monitoring.svc.cluster.local:4318` | Trace ingestion (HTTP) |
| Grafana | `https://grafana.rmwhs.space` | Dashboards |
| OpenSearch Dashboards | `https://opensearch-dashboards.rmwhs.space` | Log analytics |

---

## Standard Kubernetes Manifests

### Namespace
```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: myapp
```

### ConfigMap (non-sensitive config only)
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: myapp-config
  namespace: myapp
data:
  APP_ENV: production
  PORT: "8080"
  LOG_FORMAT: json
  SERVICE_NAME: myapp
```

### Secret (structure template — values injected by pipeline)
```yaml
# k8s/secret.yaml — commit this template, never real values
# Pipeline creates/updates the actual secret via kubectl --from-literal
apiVersion: v1
kind: Secret
metadata:
  name: myapp-secret
  namespace: myapp
type: Opaque
# No stringData here — populated by the pipeline's 'Apply App Secret' stage
```

### Deployment
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp
  namespace: myapp
  labels:
    app: myapp
spec:
  replicas: 2
  selector:
    matchLabels:
      app: myapp
  template:
    metadata:
      labels:
        app: myapp
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/path: "/metrics"
        prometheus.io/port: "8080"
    spec:
      imagePullSecrets:
      - name: harbor-credentials
      containers:
      - name: myapp
        image: harbor.rmwhs.space/apps/myapp:latest
        ports:
        - containerPort: 8080
          name: http
        envFrom:
        - configMapRef:
            name: myapp-config
        env:
        - name: SECRET_KEY
          valueFrom:
            secretKeyRef:
              name: myapp-secret
              key: SECRET_KEY
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: myapp-secret
              key: DATABASE_URL
        resources:
          requests:
            cpu: 100m
            memory: 256Mi
          limits:
            cpu: 500m
            memory: 512Mi
        readinessProbe:
          httpGet:
            path: /
            port: 8080
          initialDelaySeconds: 15
          periodSeconds: 10
        livenessProbe:
          httpGet:
            path: /
            port: 8080
          initialDelaySeconds: 30
          periodSeconds: 30
```

### Service
```yaml
apiVersion: v1
kind: Service
metadata:
  name: myapp
  namespace: myapp
  labels:
    app: myapp
spec:
  selector:
    app: myapp
  ports:
  - port: 8080
    targetPort: 8080
    name: http
  type: ClusterIP
```

### PostgreSQL Database
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: postgres
  namespace: myapp
spec:
  replicas: 1
  selector:
    matchLabels:
      app: postgres
  template:
    metadata:
      labels:
        app: postgres
    spec:
      containers:
      - name: postgres
        image: postgres:15-alpine
        ports:
        - containerPort: 5432
        env:
        - name: POSTGRES_DB
          valueFrom:
            secretKeyRef:
              name: myapp-secret
              key: POSTGRES_DB
        - name: POSTGRES_USER
          valueFrom:
            secretKeyRef:
              name: myapp-secret
              key: POSTGRES_USER
        - name: POSTGRES_PASSWORD
          valueFrom:
            secretKeyRef:
              name: myapp-secret
              key: POSTGRES_PASSWORD
        volumeMounts:
        - name: postgres-data
          mountPath: /var/lib/postgresql/data
        resources:
          requests:
            cpu: 100m
            memory: 256Mi
          limits:
            cpu: 500m
            memory: 512Mi
      volumes:
      - name: postgres-data
        persistentVolumeClaim:
          claimName: myapp-postgres-pvc
---
apiVersion: v1
kind: Service
metadata:
  name: postgres
  namespace: myapp
spec:
  selector:
    app: postgres
  ports:
  - port: 5432
    targetPort: 5432
  type: ClusterIP
```

### Database Migrations (Init Container)
```yaml
initContainers:
- name: db-migrate
  image: harbor.rmwhs.space/apps/myapp:latest
  command: ["flask", "db", "upgrade"]   # adjust per framework
  envFrom:
  - configMapRef:
      name: myapp-config
  env:
  - name: DATABASE_URL
    valueFrom:
      secretKeyRef:
        name: myapp-secret
        key: DATABASE_URL
```

---

## App Repository Directory Structure

Every app has its own Git repo with this layout:

```
myapp/                               # app repo root
├── Jenkinsfile                      # CI/CD pipeline (Standard Jenkinsfile Template)
├── Dockerfile                       # multi-stage build, runs tests, accepts SKIP_TESTS arg
├── <source code>                    # organized by language convention
├── tests/                           # invoked by the Dockerfile's test step
└── k8s/                             # Kubernetes manifests
    ├── configmap.yaml               # non-sensitive env vars
    ├── secret.yaml                  # structure template only — no real values
    ├── deployment.yaml              # or deployment-with-fluent-bit.yaml
    ├── service.yaml
    ├── ingress.yaml
    ├── servicemonitor.yaml          # if app exposes /metrics
    ├── fluent-bit-configmap.yaml    # if using log sidecar
    └── postgres.yaml                # if app needs a database
```

The agent never touches the source code with language-specific tools — `docker build` does. The agent only runs `kubectl`, `helm`, `docker`, `sonar-scanner`, `trivy`, `yq`, `jq`, and `git`.

---

## Argo CD App Registration (GitOps)

To manage your app via GitOps, add an Application manifest to the `k8s-infrastructure` repo:

```yaml
# apps/myapp/application.yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: myapp
  namespace: argocd
spec:
  project: default
  source:
    repoURL: http://gitlab-webservice-default.devops.svc.cluster.local:8181/kubernetes/k8s-infrastructure.git
    targetRevision: HEAD
    path: apps/myapp
  destination:
    server: https://kubernetes.default.svc
    namespace: myapp
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
    - CreateNamespace=true
```

> Note: Apps deployed via Jenkins pipeline (not Argo CD) manage their own lifecycle. Choose one approach per app — don't mix Jenkins deploys with Argo CD selfHeal on the same workload.

---

## DevSecOps Stack Reference

| Tool | External URL | Purpose |
|------|-------------|---------|
| Jenkins | `https://jenkins.rmwhs.space` | CI/CD pipelines |
| GitLab | `https://gitlab.rmwhs.space` | Source control |
| Harbor | `https://harbor.rmwhs.space` | Container registry |
| SonarQube | `https://sonarqube.rmwhs.space` | SAST / code quality |
| Trivy Server | (internal: `trivy-server.security.svc.cluster.local:4954`) | Container image vulnerability scan API |
| Trivy Operator | (internal CRDs) | Continuous cluster-resource vulnerability scanning |
| Argo CD | `https://argocd.rmwhs.space` | GitOps deployment |
| Vault | `https://vault.rmwhs.space` | Secrets management |
| Grafana | `https://grafana.rmwhs.space` | Metrics dashboards |
| OpenSearch Dashboards | `https://opensearch-dashboards.rmwhs.space` | Log analytics |
| Headlamp | `https://headlamp.rmwhs.space` | Kubernetes UI |
| Dependency-Track | `https://dependency-track.rmwhs.space` | SCA / SBOM |

---

## Namespaces

| Namespace | Purpose |
|-----------|---------|
| `devops` | Jenkins, GitLab, Harbor, Vault |
| `monitoring` | Prometheus, Grafana, OpenSearch, Tempo, Fluent Bit |
| `security` | Kyverno, Trivy Operator, SonarQube, Dependency-Track, ZAP |
| `argocd` | Argo CD |
| `cert-manager` | cert-manager (TLS certificate issuance) |
| `otel-demo` | OpenTelemetry demo app |
| `jenkins-agents` | Ephemeral Jenkins build pods |
| `ingress-nginx` | nginx-external ingress controller |
| `<your-app>` | Each app gets its own dedicated namespace |

---

## Internal Service DNS Quick Reference

Format: `<service>.<namespace>.svc.cluster.local:<port>`

| Service | Internal DNS |
|---------|-------------|
| GitLab | `gitlab-webservice-default.devops.svc.cluster.local:8181` |
| Harbor | `harbor-core.devops.svc.cluster.local:80` |
| Jenkins | `jenkins.devops.svc.cluster.local:8080` |
| SonarQube | `sonarqube-sonarqube.security.svc.cluster.local:9000` |
| Trivy Server | `trivy-server.security.svc.cluster.local:4954` |
| Vault | `vault.devops.svc.cluster.local:8200` |
| Prometheus | `kube-prometheus-stack-prometheus.monitoring.svc.cluster.local:9090` |
| OpenSearch | `opensearch.monitoring.svc.cluster.local:9200` |
| Tempo gRPC | `tempo.monitoring.svc.cluster.local:4317` |
| Tempo HTTP | `tempo.monitoring.svc.cluster.local:4318` |
