FROM python:3.12-slim AS builder

WORKDIR /build
COPY pyproject.toml malicious_backend.py ./
RUN python -m pip install --prefix=/install .

# A compromised builder-local check is intentionally ineffective.
RUN find /install -name 'python*' -print -quit

FROM python:3.12-slim AS builder-output-validator

COPY --from=builder /install /install
RUN collision="$(find /install/bin -maxdepth 1 \( -name 'python*' -o -name 'pip*' \) -print -quit)" && \
    if [ -n "$collision" ]; then echo "Builder output replaces protected runtime executable: $collision" >&2; exit 1; fi
