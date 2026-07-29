FROM mcr.microsoft.com/playwright:v1.57.0-noble

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        git \
        zip \
        python3 \
        python3-pip \
        gitleaks \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Docker CLI from Docker's official apt repo (for docker build/push/save in CI)
RUN curl -fsSL https://download.docker.com/linux/ubuntu/gpg     | gpg --dearmor -o /etc/apt/keyrings/docker.gpg     && echo 'deb [signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu noble stable'     | tee /etc/apt/sources.list.d/docker.list     && apt-get update     && apt-get install -y --no-install-recommends docker-ce-cli     && apt-get clean     && rm -rf /var/lib/apt/lists/*

# Install kubectl matching Docker Desktop K8s server version (v1.36)
RUN curl -fsSL https://pkgs.k8s.io/core:/stable:/v1.36/deb/Release.key \
    | gpg --dearmor -o /etc/apt/keyrings/kubernetes-apt-keyring.gpg \
    && echo 'deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] https://pkgs.k8s.io/core:/stable:/v1.36/deb/ /' \
    | tee /etc/apt/sources.list.d/kubernetes.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends kubectl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install kustomize v5.4.3 (direct download)
RUN curl -fsSL -o /tmp/kustomize.tar.gz     https://github.com/kubernetes-sigs/kustomize/releases/download/kustomize/v5.4.3/kustomize_v5.4.3_linux_amd64.tar.gz     && tar xzf /tmp/kustomize.tar.gz -C /usr/local/bin/     && chmod +x /usr/local/bin/kustomize     && rm /tmp/kustomize.tar.gz     && kustomize version
RUN curl -fsSL https://raw.githubusercontent.com/kubernetes-sigs/kustomize/master/hack/install_kustomize.sh \
    | bash -s -- /usr/local/bin kustomize v5.4.3 \
    && kustomize version 2>/dev/null || true

# Install Semgrep (SAST) and Checkov (IaC) via pip (--break-system-packages for PEP 668)
RUN pip3 install --break-system-packages --no-cache-dir semgrep checkov

# Pre-cache Semgrep rules for all project languages (CI has no internet)
RUN mkdir -p /tmp/semgrep-dummy \
    && echo 'print("x")' > /tmp/semgrep-dummy/test.py \
    && echo 'let x = 1' > /tmp/semgrep-dummy/test.js \
    && echo 'let x: number = 1' > /tmp/semgrep-dummy/test.ts \
    && echo 'const el = <div/>' > /tmp/semgrep-dummy/test.tsx \
    && echo 'key: value' > /tmp/semgrep-dummy/test.yml \
    && semgrep scan --config=auto --quiet /tmp/semgrep-dummy 2>&1 \
    && rm -rf /tmp/semgrep-dummy

# Install Trivy (SCA) from GitHub releases
RUN curl -fsSL -o /tmp/trivy.deb \
    https://github.com/aquasecurity/trivy/releases/download/v0.72.0/trivy_0.72.0_Linux-64bit.deb \
    && dpkg -i /tmp/trivy.deb \
    && rm /tmp/trivy.deb

# Pre-cache Trivy vulnerability DB (CI container has no internet, must fail if no connection)
RUN trivy image --download-db-only --quiet 2>&1

RUN node --version >/dev/null \
    && npm --version >/dev/null \
    && test -d /ms-playwright \
    && zip --version >/dev/null \
    && python3 --version >/dev/null \
    && pip3 --version >/dev/null \
    && gitleaks version >/dev/null \
    && semgrep --version >/dev/null \
    && checkov --version >/dev/null \
    && trivy --version >/dev/null
