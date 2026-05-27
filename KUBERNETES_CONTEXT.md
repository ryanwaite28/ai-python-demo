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

### Common App Deploy Secrets

A shared Vault path `kv/common-app-deploy-secrets` holds credentials required by **all** apps for standard deployment tasks. These are not app-specific — they cover the shared infrastructure every app depends on.

| Key | Purpose |
|-----|---------|
| `harbor_username` | Harbor registry username (image push/pull, imagePullSecret) |
| `harbor_password` | Harbor registry password |
| `opensearch_username` | OpenSearch username (Fluent Bit log forwarding) |
| `opensearch_password` | OpenSearch password |
| `mailpit_user` | Mailpit SMTP username (if auth is enabled on the Mailpit deployment) |
| `mailpit_password` | Mailpit SMTP password |

Every app Jenkinsfile must pull from `kv/common-app-deploy-secrets` alongside its own `kv/${IMAGE_NAME}` path. Combine both in a single `withVault` block. The common path is the source of truth for Harbor, OpenSearch, and Mailpit credentials — do not duplicate these values into per-app Vault paths.

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

Multiple Vault paths can be combined in one `withVault` block. The standard pattern for app pipelines is to pull `kv/common-app-deploy-secrets` alongside the app's own path:

```groovy
withVault(
  configuration: [
    vaultUrl: 'https://vault.rmwhs.space',
    vaultCredentialId: 'vault-auth-token'
  ],
  vaultSecrets: [
    [path: 'kv/common-app-deploy-secrets', secretValues: [
      [envVar: 'HARBOR_USER',     vaultKey: 'harbor_username'],
      [envVar: 'HARBOR_PASS',     vaultKey: 'harbor_password'],
      [envVar: 'OPENSEARCH_USER', vaultKey: 'opensearch_username'],
      [envVar: 'OPENSEARCH_PASS', vaultKey: 'opensearch_password']
    ]],
    [path: 'kv/myapp', secretValues: [
      [envVar: 'SECRET_KEY',  vaultKey: 'secret_key'],
      [envVar: 'DB_PASSWORD', vaultKey: 'db_password']
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

### Runtime Vault Access

Apps that need to read secrets from Vault at runtime (not just at deploy time) can have the Vault token injected into their Kubernetes namespace secret by the pipeline. This lets the application call the Vault API directly without any external credential distribution.

**When to use:** apps that rotate credentials at runtime, fetch per-request secrets, or need dynamic secret generation. For simple static secrets (DB password, API keys), the standard pipeline injection pattern is sufficient and preferred.

**How to wire it up:**

1. In the `Apply App Secret` stage, pull `vault-auth-token` via `withCredentials` and include it in the `kubectl create secret` call:

```groovy
stage('Apply App Secret') {
  steps {
    withCredentials([string(credentialsId: 'vault-auth-token', variable: 'VAULT_TOKEN')]) {
      withVault(/* ... existing withVault config ... */) {
        sh '''
          kubectl create secret generic ${IMAGE_NAME}-secret \
            --from-literal=VAULT_TOKEN=${VAULT_TOKEN} \
            --from-literal=SECRET_KEY=${SECRET_KEY} \
            --from-literal=DB_PASSWORD=${DB_PASSWORD} \
            --namespace=${K8S_NAMESPACE} \
            --dry-run=client -o yaml | kubectl apply -f -
        '''
      }
    }
  }
}
```

2. In the app's Deployment, expose `VAULT_TOKEN` and `VAULT_ADDR` from the secret:

```yaml
env:
- name: VAULT_ADDR
  value: "http://vault.devops.svc.cluster.local:8200"
- name: VAULT_TOKEN
  valueFrom:
    secretKeyRef:
      name: myapp-secret
      key: VAULT_TOKEN
```

3. The app can now call the Vault HTTP API or use a Vault SDK directly:

```python
# Python example
import os, requests
vault_addr  = os.environ['VAULT_ADDR']
vault_token = os.environ['VAULT_TOKEN']
secret = requests.get(
    f"{vault_addr}/v1/kv/data/myapp",
    headers={"X-Vault-Token": vault_token}
).json()['data']['data']
```

> The Vault token in `vault-auth-token` has broad platform-level access. Treat it as a privileged credential in the app's Kubernetes secret — restrict secret access with RBAC and never log or expose the token value.

### Jenkins Credentials (Platform Use Only)

Jenkins credentials are reserved for platform-level access. App secrets go in Vault. Harbor and OpenSearch credentials for app pipelines come from `kv/common-app-deploy-secrets` — do not use `harbor-credentials` in app Jenkinsfiles.

| Credential ID | Type | Used For |
|--------------|------|---------|
| `vault-auth-token` | Secret Text | Authenticating `withVault` calls |
| `harbor-credentials` | Username/Password | Pre-configured imagePullSecret in `jenkins-agents` namespace (platform use only) |
| `gitlab-root-token` | Username/Password | GitLab API access and repo cloning |
| `sonarqube-token` | Secret Text | SonarQube analysis authentication |

#### Using `harbor-credentials` in the Pipeline

`harbor-credentials` is pre-configured as a Kubernetes imagePullSecret in `jenkins-agents`. App pipelines create their own namespace imagePullSecret using Harbor credentials pulled from Vault (`kv/common-app-deploy-secrets`) — not via `withCredentials`. The example below is for platform-level tooling only:

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

1. **Tests run inside the build** — in a multi-stage build's "build" stage, before producing the final runtime image. A failed test fails `docker build`, which fails the pipeline before scan, push, or deploy. This is the test gate.
2. **Each test scope has its own `SKIP_*` build arg** — one arg per test scope, not a single blunt `SKIP_TESTS`. The Jenkinsfile exposes matching boolean parameters and forwards them via `--build-arg`.

#### Multi-stage Dockerfile example (Python)

```dockerfile
# syntax=docker/dockerfile:1
FROM python:3.13-slim AS build

ARG SKIP_UNIT_TESTS=false
ARG SKIP_INTEGRATION_TESTS=false

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

RUN if [ "$SKIP_UNIT_TESTS" = "true" ]; then \
      echo "WARNING: unit tests skipped"; \
    else \
      pytest tests/unit/ -q; \
    fi

RUN if [ "$SKIP_INTEGRATION_TESTS" = "true" ]; then \
      echo "WARNING: integration tests skipped"; \
    else \
      pytest tests/integration/ -q; \
    fi

FROM python:3.13-slim AS runtime
WORKDIR /app
COPY --from=build /app /app
CMD ["python", "main.py"]
```

The same pattern for other languages:

```dockerfile
# Node example
ARG SKIP_UNIT_TESTS=false
ARG SKIP_INTEGRATION_TESTS=false
RUN if [ "$SKIP_UNIT_TESTS" != "true" ]; then npm run test:unit; fi
RUN if [ "$SKIP_INTEGRATION_TESTS" != "true" ]; then npm run test:integration; fi

# Go example
ARG SKIP_UNIT_TESTS=false
ARG SKIP_INTEGRATION_TESTS=false
RUN if [ "$SKIP_UNIT_TESTS" != "true" ]; then go test ./internal/...; fi
RUN if [ "$SKIP_INTEGRATION_TESTS" != "true" ]; then go test ./integration/...; fi
```

> All `SKIP_*` args default to `false` — every test scope runs by default. Skipping is for **debug iterations only.** Never merge or deploy an image built with any test scope skipped. Add only the args that correspond to real test scopes in the app — do not add `SKIP_INTEGRATION_TESTS` to an app that has no integration tests.

### DinD (Docker-in-Docker) Requirements

All pipelines that build Docker images require a DinD sidecar. Key requirements:

- **`--mtu=1400`** is mandatory in DinD daemon args. k3s overlay network MTU is ~1450; DinD defaults to 1500. The mismatch causes `curl: (35) Connection reset by peer` on large downloads (Helm, OS packages) inside the DinD daemon during image builds.
- **`DOCKER_TLS_CERTDIR: ""`** disables TLS on the Docker socket — use unencrypted TCP on port 2375 between the builder and DinD containers.
- The builder container sets `DOCKER_HOST: tcp://localhost:2375`.
- **Daemon readiness wait: always use `docker --version`, never `docker info`.** `docker info` connects to the daemon and queries running state; it has been observed to hang or fail transiently before the daemon is fully initialized. `docker --version` is a local binary check that exits immediately and reliably signals the CLI is present and the socket is reachable.

```groovy
sh '''
    echo "Waiting for Docker daemon..."
    timeout 30 sh -c 'until docker --version > /dev/null 2>&1; do sleep 1; done'
    echo "Docker daemon ready."
'''
```

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

#### Critical stages — never skippable

Two stages are always mandatory and must not be gated by any parameter:

| Stage | Why |
|-------|-----|
| **Build Docker image** | The image is the artifact. Skipping it means nothing was built. |
| **Deploy to Kubernetes** | The whole purpose of the pipeline. Skipping defeats the CI/CD contract. |

Every other stage is optional and should be controlled by a dedicated boolean parameter.

#### Universal parameters (all app pipelines)

| Parameter | Type | Default | Purpose |
|-----------|------|---------|---------|
| `SKIP_SONAR` | Boolean | `false` | Skip SonarQube static analysis scan |
| `SKIP_QUALITY_GATE` | Boolean | `false` | Skip waiting for SonarQube quality gate result |
| `SKIP_TRIVY` | Boolean | `false` | Skip Trivy vulnerability scan |

#### Fine-grained test parameters

Rather than a single `SKIP_TESTS` flag, **each test scope gets its own parameter.** This lets operators skip a slow integration suite without disabling fast unit tests, or re-run only a specific scope when debugging.

| Parameter | Type | Default | Scope |
|-----------|------|---------|-------|
| `SKIP_UNIT_TESTS` | Boolean | `false` | In-Dockerfile unit tests — fastest feedback loop |
| `SKIP_INTEGRATION_TESTS` | Boolean | `false` | In-Dockerfile integration tests (DB, cache, external service mocks) |
| `SKIP_E2E_TESTS` | Boolean | `false` | End-to-end tests (if the app has them — omit if not applicable) |

Add only the test parameters that correspond to actual test scopes in the app's Dockerfile. Do not add `SKIP_INTEGRATION_TESTS` to an app that has no integration tests.

Each parameter must be forwarded to `docker build` as a `--build-arg`:

```groovy
sh """
  docker build \\
    --build-arg SKIP_UNIT_TESTS=${params.SKIP_UNIT_TESTS} \\
    --build-arg SKIP_INTEGRATION_TESTS=${params.SKIP_INTEGRATION_TESTS} \\
    -t ${FULL_IMAGE} -t ${LATEST_IMAGE} .
"""
```

> All test parameters default to `false` — tests run by default. Skipping any test scope is for **debug iteration only.** Never merge or deploy a build where tests were skipped.

#### App-type-specific parameters (add as applicable)

| Parameter | Type | Default | Use When |
|-----------|------|---------|----------|
| `RUN_MIGRATION` | Boolean | `true` | App has a relational database — run schema migrations on every deploy |
| `RESET_DB` | Boolean | `false` | Wipe and recreate the database (**destructive** — data loss, use intentionally) |
| `SEED_DB` | Boolean | `false` | Run database seed/fixture data after migration |
| `CLEAR_CACHE` | Boolean | `false` | App uses Redis — flush the cache on deploy |
| `FORCE_REDEPLOY` | Boolean | `false` | Force pod rollout even if the image tag did not change |

**Design rules:**
- Destructive operations (`RESET_DB`, `CLEAR_CACHE`) must default to `false`
- Safe-to-repeat operations (`RUN_MIGRATION`) can default to `true`
- Each parameter gates exactly one stage with `when { expression { params.PARAM_NAME } }`
- Add only the parameters that apply to the app's architecture — don't add `RUN_MIGRATION` to a stateless app
- The critical stages (build + deploy) are never gated — they always run

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
    // ── Static analysis & security (skippable, default: run) ──
    booleanParam(name: 'SKIP_SONAR',              defaultValue: false, description: 'Skip SonarQube static analysis scan')
    booleanParam(name: 'SKIP_QUALITY_GATE',        defaultValue: false, description: 'Skip SonarQube quality gate wait')
    booleanParam(name: 'SKIP_TRIVY',               defaultValue: false, description: 'Skip Trivy vulnerability scan')
    // ── Per-scope test parameters (skippable, default: run) ──
    booleanParam(name: 'SKIP_UNIT_TESTS',          defaultValue: false, description: 'Skip unit tests in Docker build (debug only — never deploy)')
    booleanParam(name: 'SKIP_INTEGRATION_TESTS',   defaultValue: false, description: 'Skip integration tests in Docker build (debug only — never deploy)')
    // Add SKIP_E2E_TESTS if the app has end-to-end tests.
    // ── Deployment options (app-specific — add what applies) ──
    booleanParam(name: 'RUN_MIGRATION',            defaultValue: true,  description: 'Run database migrations on deploy')
    // Add app-specific params: RESET_DB, CLEAR_CACHE, SEED_DB, FORCE_REDEPLOY, etc.
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
        sh 'docker --version'
        sh 'trivy --version'
        sh 'sonar-scanner --version'
      }
    }

    stage('Prepare K8s Namespace & Registry Secret') {
      // Harbor credentials come from Vault kv/common-app-deploy-secrets, not Jenkins credentials.
      steps {
        withVault(
          configuration: [
            vaultUrl: 'https://vault.rmwhs.space',
            vaultCredentialId: 'vault-auth-token'
          ],
          vaultSecrets: [[
            path: 'kv/common-app-deploy-secrets',
            secretValues: [
              [envVar: 'HARBOR_USER', vaultKey: 'harbor_username'],
              [envVar: 'HARBOR_PASS', vaultKey: 'harbor_password']
            ]
          ]]
        ) {
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
      // Pull common secrets (Harbor, OpenSearch) and app-specific secrets from Vault.
      // Vault path kv/<app-name> must exist before the first pipeline run.
      // Add one secretValues entry per app-specific key needed.
      steps {
        withVault(
          configuration: [
            vaultUrl: 'https://vault.rmwhs.space',
            vaultCredentialId: 'vault-auth-token'
          ],
          vaultSecrets: [
            [path: 'kv/common-app-deploy-secrets', secretValues: [
              [envVar: 'HARBOR_USER',     vaultKey: 'harbor_username'],
              [envVar: 'HARBOR_PASS',     vaultKey: 'harbor_password'],
              [envVar: 'OPENSEARCH_USER', vaultKey: 'opensearch_username'],
              [envVar: 'OPENSEARCH_PASS', vaultKey: 'opensearch_password']
            ]],
            [path: "kv/${IMAGE_NAME}", secretValues: [
              [envVar: 'SECRET_KEY',  vaultKey: 'secret_key'],
              [envVar: 'DB_PASSWORD', vaultKey: 'db_password']
              // add more app-specific keys as needed
            ]]
          ]
        ) {
          sh '''
            kubectl create secret generic ${IMAGE_NAME}-secret \
              --from-literal=SECRET_KEY=${SECRET_KEY} \
              --from-literal=DB_PASSWORD=${DB_PASSWORD} \
              --namespace=${K8S_NAMESPACE} \
              --dry-run=client -o yaml | kubectl apply -f -
            kubectl create secret generic opensearch-credentials \
              --from-literal=OPENSEARCH_USER=${OPENSEARCH_USER} \
              --from-literal=OPENSEARCH_PASS=${OPENSEARCH_PASS} \
              --namespace=${K8S_NAMESPACE} \
              --dry-run=client -o yaml | kubectl apply -f -
          '''
        }
      }
    }

    stage('SonarQube Scan') {
      when { expression { !params.SKIP_SONAR } }
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
      when { expression { !params.SKIP_SONAR && !params.SKIP_QUALITY_GATE } }
      steps {
        timeout(time: 5, unit: 'MINUTES') {
          waitForQualityGate abortPipeline: true
        }
      }
    }

    stage('Build & Login') {
      // Harbor credentials come from Vault kv/common-app-deploy-secrets.
      // Per-scope SKIP_* args are forwarded to the Dockerfile build args.
      // Build and Deploy stages are NEVER skipped — they are the critical path.
      steps {
        withVault(
          configuration: [
            vaultUrl: 'https://vault.rmwhs.space',
            vaultCredentialId: 'vault-auth-token'
          ],
          vaultSecrets: [[
            path: 'kv/common-app-deploy-secrets',
            secretValues: [
              [envVar: 'HARBOR_USER', vaultKey: 'harbor_username'],
              [envVar: 'HARBOR_PASS', vaultKey: 'harbor_password']
            ]
          ]]
        ) {
          sh """
            echo "\${HARBOR_PASS}" | docker login \${HARBOR_REGISTRY} \\
              -u \${HARBOR_USER} --password-stdin
            docker build \\
              --build-arg SKIP_UNIT_TESTS=${params.SKIP_UNIT_TESTS} \\
              --build-arg SKIP_INTEGRATION_TESTS=${params.SKIP_INTEGRATION_TESTS} \\
              -t \${FULL_IMAGE} \\
              -t \${LATEST_IMAGE} \\
              .
          """
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

> OpenSearch credentials for Fluent Bit are sourced from `kv/common-app-deploy-secrets` in Vault (`opensearch_username` / `opensearch_password`). The `Apply App Secret` pipeline stage injects them into the `opensearch-credentials` Kubernetes secret in the app namespace. Never hardcode them in the ConfigMap.

#### Sidecar Container Spec (add to Deployment)
```yaml
# In containers:
- name: fluent-bit
  image: fluent/fluent-bit:3.2
  envFrom:
  - secretRef:
      name: opensearch-credentials   # injected by pipeline from kv/common-app-deploy-secrets
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

## Email (Mailpit)

Mailpit is a shared SMTP catch-all for the cluster. Every email sent to it is captured and visible in the web UI — nothing is forwarded externally unless a relay is explicitly configured.

| Purpose | Address |
|---------|---------|
| SMTP (send) | `email-mailpit.email-mailpit.svc.cluster.local:1025` |
| Web UI (view) | `https://email-mailpit.rmwhs.space` |
| REST API | `https://email-mailpit.rmwhs.space/api/v1` |

> SMTP on port 1025 is unencrypted — traffic stays inside the cluster. Do not expose it externally.

### Configuring Your App to Send Email

Non-sensitive SMTP connection details go in the ConfigMap. Credentials go in the Kubernetes secret, sourced from Vault `kv/common-app-deploy-secrets` (`mailpit_user` / `mailpit_password`).

```yaml
# k8s/configmap.yaml
data:
  SMTP_HOST: "email-mailpit.email-mailpit.svc.cluster.local"
  SMTP_PORT: "1025"
  SMTP_FROM: "noreply@your-app.rmwhs.space"
```

Pull Mailpit credentials from `kv/common-app-deploy-secrets` in the `Apply App Secret` pipeline stage alongside Harbor and OpenSearch:

```groovy
withVault(
  configuration: [vaultUrl: 'https://vault.rmwhs.space', vaultCredentialId: 'vault-auth-token'],
  vaultSecrets: [[
    path: 'kv/common-app-deploy-secrets',
    secretValues: [
      [envVar: 'HARBOR_USER',      vaultKey: 'harbor_username'],
      [envVar: 'HARBOR_PASS',      vaultKey: 'harbor_password'],
      [envVar: 'OPENSEARCH_USER',  vaultKey: 'opensearch_username'],
      [envVar: 'OPENSEARCH_PASS',  vaultKey: 'opensearch_password'],
      [envVar: 'MAILPIT_USER',     vaultKey: 'mailpit_user'],
      [envVar: 'MAILPIT_PASSWORD', vaultKey: 'mailpit_password'],
    ]
  ]]
) {
  sh '''
    kubectl create secret generic ${IMAGE_NAME}-secret \
      --from-literal=MAILPIT_USER=${MAILPIT_USER} \
      --from-literal=MAILPIT_PASSWORD=${MAILPIT_PASSWORD} \
      ... \
      --namespace=${K8S_NAMESPACE} --dry-run=client -o yaml | kubectl apply -f -
  '''
}
```

Reference them in the Deployment from the secret — never from the ConfigMap:

```yaml
# k8s/deployment.yaml
envFrom:
  - configMapRef:
      name: your-app-config   # SMTP_HOST, SMTP_PORT, SMTP_FROM
env:
  - name: SMTP_USER
    valueFrom:
      secretKeyRef:
        name: myapp-secret
        key: MAILPIT_USER
  - name: SMTP_PASSWORD
    valueFrom:
      secretKeyRef:
        name: myapp-secret
        key: MAILPIT_PASSWORD
```

### Framework Examples

#### Node.js — Nodemailer

```javascript
const transporter = nodemailer.createTransport({
  host: process.env.SMTP_HOST,
  port: parseInt(process.env.SMTP_PORT),
  secure: false,
  auth: {
    user: process.env.SMTP_USER,
    pass: process.env.SMTP_PASSWORD,
  },
});

await transporter.sendMail({
  from: process.env.SMTP_FROM,
  to: 'user@example.com',
  subject: 'Hello',
  text: 'Message body',
});
```

#### Python — smtplib

```python
import smtplib, os
from email.mime.text import MIMEText

def send_email(to, subject, body):
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = os.environ['SMTP_FROM']
    msg['To'] = to
    with smtplib.SMTP(os.environ['SMTP_HOST'], int(os.environ['SMTP_PORT'])) as server:
        server.login(os.environ['SMTP_USER'], os.environ['SMTP_PASSWORD'])
        server.sendmail(msg['From'], [to], msg.as_string())
```

#### Python — Django

```python
# settings.py
EMAIL_BACKEND      = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST         = os.environ.get('SMTP_HOST', 'email-mailpit.email-mailpit.svc.cluster.local')
EMAIL_PORT         = int(os.environ.get('SMTP_PORT', 1025))
EMAIL_HOST_USER    = os.environ.get('SMTP_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('SMTP_PASSWORD', '')
EMAIL_USE_TLS      = False
EMAIL_USE_SSL      = False
DEFAULT_FROM_EMAIL = os.environ.get('SMTP_FROM', 'noreply@rmwhs.space')
```

#### Go — net/smtp

```go
func sendEmail(to, subject, body string) error {
    host := os.Getenv("SMTP_HOST")
    port := os.Getenv("SMTP_PORT")
    from := os.Getenv("SMTP_FROM")
    auth := smtp.PlainAuth("", os.Getenv("SMTP_USER"), os.Getenv("SMTP_PASSWORD"), host)
    msg := []byte("From: " + from + "\r\nTo: " + to + "\r\nSubject: " + subject + "\r\n\r\n" + body + "\r\n")
    return smtp.SendMail(host+":"+port, auth, from, []string{to}, msg)
}
```

#### PHP — PHPMailer

```php
$mail = new PHPMailer();
$mail->isSMTP();
$mail->Host       = getenv('SMTP_HOST');
$mail->Port       = (int) getenv('SMTP_PORT');
$mail->SMTPAuth   = true;
$mail->Username   = getenv('SMTP_USER');
$mail->Password   = getenv('SMTP_PASSWORD');
$mail->SMTPSecure = false;
$mail->setFrom(getenv('SMTP_FROM'));
```

#### Laravel

```ini
# .env / Kubernetes ConfigMap (non-sensitive) + Secret (credentials)
MAIL_MAILER=smtp
MAIL_HOST=email-mailpit.email-mailpit.svc.cluster.local
MAIL_PORT=1025
MAIL_USERNAME=${SMTP_USER}
MAIL_PASSWORD=${SMTP_PASSWORD}
MAIL_ENCRYPTION=null
MAIL_FROM_ADDRESS=noreply@rmwhs.space
```

#### Ruby — Mail gem

```ruby
Mail.defaults do
  delivery_method :smtp,
    address:              ENV['SMTP_HOST'],
    port:                 ENV['SMTP_PORT'].to_i,
    user_name:            ENV['SMTP_USER'],
    password:             ENV['SMTP_PASSWORD'],
    enable_starttls_auto: false
end
```

#### Rails

```ruby
# config/environments/production.rb
config.action_mailer.delivery_method = :smtp
config.action_mailer.smtp_settings = {
  address:  ENV.fetch('SMTP_HOST', 'email-mailpit.email-mailpit.svc.cluster.local'),
  port:     ENV.fetch('SMTP_PORT', 1025).to_i,
  user_name:     ENV['SMTP_USER'],
  password:      ENV['SMTP_PASSWORD'],
  authentication: :plain,
}
```

### Viewing Captured Emails

Open `https://email-mailpit.rmwhs.space` — all messages appear here regardless of the `To` address. Nothing is delivered to real inboxes.

```bash
# REST API
curl https://email-mailpit.rmwhs.space/api/v1/messages       # list
curl https://email-mailpit.rmwhs.space/api/v1/message/<id>   # get by ID
curl -X DELETE https://email-mailpit.rmwhs.space/api/v1/messages  # delete all
```

### Notes

- **All email is captured.** Mailpit does not forward messages to external addresses unless SMTP relay is explicitly enabled on the Mailpit deployment.
- **No TLS on port 1025.** Traffic stays inside the cluster; TLS termination is not needed on the internal SMTP connection.
- **Message retention.** Keeps the last 500 messages by default (configurable via `apps/email-mailpit/values.yaml` → `messages.maxMessages`).

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
| `email-mailpit` | Mailpit shared SMTP catch-all |
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
| Mailpit SMTP | `email-mailpit.email-mailpit.svc.cluster.local:1025` |
| Mailpit UI | `https://email-mailpit.rmwhs.space` |

---

## Industry Best Practices & Standards

### The Core Philosophy: Decoupling

Enterprise systems architecture decouples the **application layer** from the **data layer**. This produces workloads that scale, fail, and release independently — each component owns its own lifecycle.

**Why separate pods?**

- **Independent scalability** — stateless application tiers scale horizontally without the complexity of scaling a stateful database tier.
- **Fault isolation** — an application crash (e.g., memory leak) does not threaten database availability or data integrity.
- **Release velocity** — application updates deploy multiple times per day without touching the database pod.

### Standard Deployment Models

| Feature | Application (Stateless) | Database (Stateful) |
|:--------|:------------------------|:--------------------|
| **Controller** | `Deployment` | `StatefulSet` |
| **Storage** | Ephemeral or shared (NFS / S3) | Persistent (block storage / local PV) |
| **Network ID** | Dynamic IP (ClusterIP) | Stable hostname (ordinal index) |
| **Backup strategy** | Code-based (GitOps) | Snapshot / WAL-based |

### When to Use Multi-Container Pods (Sidecars)

Multi-container pods are reserved for **helper processes** that share the same lifecycle as the main application. Do not co-locate independent services in a single pod.

| Pattern | Examples |
|:--------|:---------|
| Log forwarders | Fluent Bit, Fluentd, Logstash agents |
| Proxies | Cloudflare Tunnel, Envoy (service mesh), auth proxies |
| Secret management | Vault agent sidecar injectors (secrets via shared volume) |

### Best Practices Summary

| Category | Standard Practice |
|:---------|:-----------------|
| Pod architecture | One functional unit per pod (decoupled) |
| Scaling strategy | Independent horizontal scaling per layer |
| Lifecycle management | Stateless → `Deployment`; Stateful → `StatefulSet` |
| Resource allocation | Isolate by workload type (CPU-bound vs. I/O-bound) |
| Secrets | Externalized via Vault (pipeline injection) — never hardcoded |
| Configuration | Decoupled from image via `ConfigMap` |
| Connectivity | Internal DNS (service discovery) over localhost |
| Sidecar usage | Only for helper tasks: logging, proxies, auth |

### Security & Configuration Standards

- **Secrets** — never hardcode credentials. Use Vault injection at the pipeline level (the standard for this cluster). See [Secrets Management](#secrets-management).
- **Environment** — use `envFrom` to map ConfigMaps and Secrets for cleaner deployment manifests.
- **Probes** — always implement `liveness` and `readiness` probes so traffic only reaches healthy pods. Omitting probes means Kubernetes cannot distinguish a crashed pod from a starting one.

