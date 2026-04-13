# syntax=docker/dockerfile:1
FROM python:3.13-slim@sha256:d168b8d9eb761f4d3fe305ebd04aeb7e7f2de0297cec5fb2f8f6403244621664 AS base

LABEL org.opencontainers.image.source="https://github.com/mick-gsk/drift"
LABEL org.opencontainers.image.description="Catches structural erosion from AI-generated code that passes all your tests"
LABEL org.opencontainers.image.licenses="MIT"

# Install git (required for history-based signals)
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

# Install drift-analyzer from PyPI
ARG DRIFT_VERSION=drift-analyzer
RUN pip install --no-cache-dir ${DRIFT_VERSION}

# Non-root user for security
RUN useradd --create-home --shell /bin/bash drift
USER drift

WORKDIR /src

ENTRYPOINT ["drift"]
CMD ["--help"]
