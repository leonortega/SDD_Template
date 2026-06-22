FROM mcr.microsoft.com/dotnet/sdk:10.0.300

ARG GITLEAKS_VERSION=8.30.1
ARG TRIVY_VERSION=0.70.0
ARG NODE_MAJOR=22
ARG KUBECTL_VERSION=1.36.2

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        gnupg \
        git \
        jq \
        tar \
        unzip \
        zip \
        docker.io \
    && curl -fsSL https://deb.nodesource.com/setup_${NODE_MAJOR}.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && curl -sSfL "https://github.com/gitleaks/gitleaks/releases/download/v${GITLEAKS_VERSION}/gitleaks_${GITLEAKS_VERSION}_linux_x64.tar.gz" \
        | tar -xz -C /usr/local/bin gitleaks \
    && curl -sSfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh \
        | sh -s -- -b /usr/local/bin "v${TRIVY_VERSION}" \
    && curl -sL https://aka.ms/InstallAzureCLIDeb | bash \
    && kubectl_arch="$(dpkg --print-architecture)" \
    && case "$kubectl_arch" in amd64) kubectl_arch="amd64" ;; arm64) kubectl_arch="arm64" ;; *) echo "Unsupported kubectl architecture: $kubectl_arch" >&2; exit 1 ;; esac \
    && curl -fsSLo /usr/local/bin/kubectl "https://dl.k8s.io/release/v${KUBECTL_VERSION}/bin/linux/${kubectl_arch}/kubectl" \
    && chmod +x /usr/local/bin/kubectl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN dotnet --info >/dev/null \
    && git --version >/dev/null \
    && jq --version >/dev/null \
    && zip --version >/dev/null \
    && gitleaks version >/dev/null \
    && trivy --version >/dev/null \
    && az version >/dev/null \
    && docker --version >/dev/null \
    && kubectl version --client=true >/dev/null \
    && node --version >/dev/null \
    && npm --version >/dev/null
