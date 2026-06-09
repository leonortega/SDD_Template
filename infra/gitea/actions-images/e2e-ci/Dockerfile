FROM mcr.microsoft.com/playwright:v1.57.0-noble

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        git \
        zip \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN node --version >/dev/null \
    && npm --version >/dev/null \
    && test -d /ms-playwright \
    && zip --version >/dev/null
