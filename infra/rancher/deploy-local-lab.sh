#!/usr/bin/env bash
set -euo pipefail

environment=""
namespace=""
site_image=""
api_image=""
site_host=""
api_host=""
commit_sha=""

while [ "$#" -gt 0 ]; do
  case "$1" in
    --environment) environment="$2"; shift 2 ;;
    --namespace) namespace="$2"; shift 2 ;;
    --site-image) site_image="$2"; shift 2 ;;
    --api-image) api_image="$2"; shift 2 ;;
    --site-host) site_host="$2"; shift 2 ;;
    --api-host) api_host="$2"; shift 2 ;;
    --commit-sha) commit_sha="$2"; shift 2 ;;
    *) echo "Unknown argument: $1" >&2; exit 1 ;;
  esac
done

test -n "$environment"
test -n "$namespace"
test -n "$site_image"
test -n "$api_image"

if [ -z "$commit_sha" ]; then
  commit_sha="${GITHUB_SHA:-unknown}"
fi

site_digest="${site_image##*@}"
api_digest="${api_image##*@}"

case "$environment" in
  dev)
    aspnet_environment="Development"
    log_level="Debug"
    site_host="${site_host:-site.dev.sdd.localhost}"
    api_host="${api_host:-api.dev.sdd.localhost}"
    ;;
  qa)
    aspnet_environment="Staging"
    log_level="Debug"
    site_host="${site_host:-site.qa.sdd.localhost}"
    api_host="${api_host:-api.qa.sdd.localhost}"
    ;;
  prod)
    aspnet_environment="Production"
    log_level="Warning"
    site_host="${site_host:-site.prod.sdd.localhost}"
    api_host="${api_host:-api.prod.sdd.localhost}"
    ;;
  *)
    echo "environment must be dev, qa, or prod." >&2
    exit 1
    ;;
esac

if ! kubectl config current-context | grep -qx "rancher-desktop"; then
  echo "kubectl current context must be rancher-desktop." >&2
  exit 1
fi

case "$site_image" in *@sha256:*) ;; *) echo "site image must be pinned by digest." >&2; exit 1 ;; esac
case "$api_image" in *@sha256:*) ;; *) echo "api image must be pinned by digest." >&2; exit 1 ;; esac

kubectl create namespace "$namespace" --dry-run=client -o yaml | kubectl apply -f -

if [ -n "${NEXUS_DOCKER_REGISTRY:-}" ] && [ -n "${NEXUS_DOCKER_USERNAME:-}" ] && [ -n "${NEXUS_DOCKER_PASSWORD:-}" ]; then
  kubectl -n "$namespace" create secret docker-registry nexus-docker-registry \
    --docker-server="$NEXUS_DOCKER_REGISTRY" \
    --docker-username="$NEXUS_DOCKER_USERNAME" \
    --docker-password="$NEXUS_DOCKER_PASSWORD" \
    --dry-run=client -o yaml | kubectl apply -f -
fi

kubectl -n "$namespace" apply -f - <<YAML
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: api-sqlite-data
  labels:
    app.kubernetes.io/part-of: sdd-template
    sddtemplate.dev/environment: ${environment}
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 1Gi
---
apiVersion: v1
kind: Service
metadata:
  name: api
  labels:
    app.kubernetes.io/name: api
    app.kubernetes.io/part-of: sdd-template
    sddtemplate.dev/environment: ${environment}
spec:
  selector:
    app.kubernetes.io/name: api
  ports:
    - name: http
      port: 8080
      targetPort: 8080
---
apiVersion: v1
kind: Service
metadata:
  name: site
  labels:
    app.kubernetes.io/name: site
    app.kubernetes.io/part-of: sdd-template
    sddtemplate.dev/environment: ${environment}
spec:
  selector:
    app.kubernetes.io/name: site
  ports:
    - name: http
      port: 8080
      targetPort: 8080
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api
  labels:
    app.kubernetes.io/name: api
    app.kubernetes.io/part-of: sdd-template
    sddtemplate.dev/environment: ${environment}
    sddtemplate.dev/commit-sha: ${commit_sha}
spec:
  replicas: 1
  selector:
    matchLabels:
      app.kubernetes.io/name: api
  template:
    metadata:
      labels:
        app.kubernetes.io/name: api
        app.kubernetes.io/part-of: sdd-template
        sddtemplate.dev/environment: ${environment}
        sddtemplate.dev/commit-sha: ${commit_sha}
      annotations:
        sddtemplate.dev/image-digest: ${api_digest}
    spec:
      imagePullSecrets:
        - name: nexus-docker-registry
      containers:
        - name: api
          image: ${api_image}
          imagePullPolicy: IfNotPresent
          ports:
            - containerPort: 8080
          env:
            - name: ASPNETCORE_ENVIRONMENT
              value: "${aspnet_environment}"
            - name: Logging__LogLevel__Default
              value: "${log_level}"
            - name: Serilog__MinimumLevel__Default
              value: "${log_level}"
            - name: SDDTEMPLATE_APP
              value: "api"
            - name: SDDTEMPLATE_ENVIRONMENT
              value: "${environment}"
            - name: SDDTEMPLATE_NAMESPACE
              value: "${namespace}"
            - name: SDDTEMPLATE_COMMIT_SHA
              value: "${commit_sha}"
            - name: SDDTEMPLATE_IMAGE_DIGEST
              value: "${api_digest}"
            - name: Cors__AllowedOrigins__0
              value: "http://${site_host}"
            - name: ConnectionStrings__ClientsDb
              value: "Data Source=/home/data/app.db"
          volumeMounts:
            - name: sqlite-data
              mountPath: /home/data
          readinessProbe:
            httpGet:
              path: /health
              port: 8080
            initialDelaySeconds: 5
            periodSeconds: 10
          livenessProbe:
            httpGet:
              path: /health
              port: 8080
            initialDelaySeconds: 20
            periodSeconds: 20
      volumes:
        - name: sqlite-data
          persistentVolumeClaim:
            claimName: api-sqlite-data
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: site
  labels:
    app.kubernetes.io/name: site
    app.kubernetes.io/part-of: sdd-template
    sddtemplate.dev/environment: ${environment}
    sddtemplate.dev/commit-sha: ${commit_sha}
spec:
  replicas: 1
  selector:
    matchLabels:
      app.kubernetes.io/name: site
  template:
    metadata:
      labels:
        app.kubernetes.io/name: site
        app.kubernetes.io/part-of: sdd-template
        sddtemplate.dev/environment: ${environment}
        sddtemplate.dev/commit-sha: ${commit_sha}
      annotations:
        sddtemplate.dev/image-digest: ${site_digest}
    spec:
      imagePullSecrets:
        - name: nexus-docker-registry
      containers:
        - name: site
          image: ${site_image}
          imagePullPolicy: IfNotPresent
          ports:
            - containerPort: 8080
          env:
            - name: ASPNETCORE_ENVIRONMENT
              value: "${aspnet_environment}"
            - name: Logging__LogLevel__Default
              value: "${log_level}"
            - name: Serilog__MinimumLevel__Default
              value: "${log_level}"
            - name: SDDTEMPLATE_APP
              value: "site"
            - name: SDDTEMPLATE_ENVIRONMENT
              value: "${environment}"
            - name: SDDTEMPLATE_NAMESPACE
              value: "${namespace}"
            - name: SDDTEMPLATE_COMMIT_SHA
              value: "${commit_sha}"
            - name: SDDTEMPLATE_IMAGE_DIGEST
              value: "${site_digest}"
            - name: Api__BaseUrl
              value: "http://api:8080"
          readinessProbe:
            httpGet:
              path: /health
              port: 8080
            initialDelaySeconds: 5
            periodSeconds: 10
          livenessProbe:
            httpGet:
              path: /health
              port: 8080
            initialDelaySeconds: 20
            periodSeconds: 20
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: app
  labels:
    app.kubernetes.io/part-of: sdd-template
    sddtemplate.dev/environment: ${environment}
spec:
  rules:
    - host: ${site_host}
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: site
                port:
                  number: 8080
    - host: ${api_host}
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: api
                port:
                  number: 8080
YAML

kubectl -n "$namespace" rollout status deployment/api --timeout=180s
kubectl -n "$namespace" rollout status deployment/site --timeout=180s
kubectl -n "$namespace" get deployment api -o jsonpath='{.spec.template.spec.containers[0].image}' | grep -Fx "$api_image"
kubectl -n "$namespace" get deployment site -o jsonpath='{.spec.template.spec.containers[0].image}' | grep -Fx "$site_image"
