FROM mcr.microsoft.com/playwright:v1.57.0-noble

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        git \
        zip \
        python3 \
        gitleaks \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install kubectl (latest stable)
RUN curl -fsSL https://pkgs.k8s.io/core:/stable:/v1.30/deb/Release.key \
    | gpg --dearmor -o /etc/apt/keyrings/kubernetes-apt-keyring.gpg \
    && echo 'deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] https://pkgs.k8s.io/core:/stable:/v1.30/deb/ /' \
    | tee /etc/apt/sources.list.d/kubernetes.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends kubectl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install kustomize v5.4.3
RUN curl -fsSL https://raw.githubusercontent.com/kubernetes-sigs/kustomize/master/hack/install_kustomize.sh \
    | bash -s -- /usr/local/bin kustomize v5.4.3 \
    && kustomize version 2>/dev/null || true

RUN node --version >/dev/null \
    && npm --version >/dev/null \
    && test -d /ms-playwright \
    && zip --version >/dev/null \
    && python3 --version >/dev/null \
    && gitleaks version >/dev/null
