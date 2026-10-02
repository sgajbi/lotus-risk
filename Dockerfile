FROM python:3.12-alpine3.23@sha256:33a47b0a92c0766bdd77cd82bbaa4c320ce48db01a2bfe1782920ca7a16e3744 AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build
COPY pyproject.toml README.md ./
COPY src ./src
RUN python -m pip install --upgrade pip && \
    python -m pip install --prefix=/install .

FROM python:3.12-alpine3.23@sha256:33a47b0a92c0766bdd77cd82bbaa4c320ce48db01a2bfe1782920ca7a16e3744 AS builder-output-validator

COPY --from=builder /install /install
RUN collision="$(find /install -mindepth 1 ! -path /install/bin ! -path '/install/bin/*' ! -path /install/lib ! -path /install/lib/python3.12 ! -path /install/lib/python3.12/site-packages ! -path '/install/lib/python3.12/site-packages/*' -print -quit)" && \
    if [ -n "$collision" ]; then echo "Builder output escapes dependency roots: $collision" >&2; exit 1; fi && \
    collision="$(find /install/bin -maxdepth 1 \( -name 'python*' -o -name 'pip*' \) -print -quit)" && \
    if [ -n "$collision" ]; then echo "Builder output replaces protected runtime executable: $collision" >&2; exit 1; fi

FROM python:3.12-alpine3.23@sha256:33a47b0a92c0766bdd77cd82bbaa4c320ce48db01a2bfe1782920ca7a16e3744 AS runtime

ARG LOTUS_GIT_COMMIT_SHA=unknown
ARG LOTUS_GIT_BRANCH=unknown
ARG LOTUS_SERVICE_VERSION=0.1.0
ARG LOTUS_BUILD_TIMESTAMP=unknown
ARG LOTUS_REPO_URL=unknown
ARG LOTUS_IMAGE_DIGEST=unavailable-before-publish
ARG LOTUS_CI_PIPELINE_RUN_ID=unknown

LABEL org.opencontainers.image.revision="${LOTUS_GIT_COMMIT_SHA}" \
      org.opencontainers.image.ref.name="${LOTUS_GIT_BRANCH}" \
      org.opencontainers.image.version="${LOTUS_SERVICE_VERSION}" \
      org.opencontainers.image.created="${LOTUS_BUILD_TIMESTAMP}" \
      org.opencontainers.image.source="${LOTUS_REPO_URL}" \
      org.opencontainers.image.digest="${LOTUS_IMAGE_DIGEST}" \
      com.lotus.git.branch="${LOTUS_GIT_BRANCH}" \
      com.lotus.ci.pipeline-run-id="${LOTUS_CI_PIPELINE_RUN_ID}"

ENV LOTUS_GIT_COMMIT_SHA="${LOTUS_GIT_COMMIT_SHA}" \
    LOTUS_GIT_BRANCH="${LOTUS_GIT_BRANCH}" \
    LOTUS_SERVICE_VERSION="${LOTUS_SERVICE_VERSION}" \
    LOTUS_BUILD_TIMESTAMP="${LOTUS_BUILD_TIMESTAMP}" \
    LOTUS_REPO_URL="${LOTUS_REPO_URL}" \
    LOTUS_IMAGE_DIGEST="${LOTUS_IMAGE_DIGEST}" \
    LOTUS_CI_PIPELINE_RUN_ID="${LOTUS_CI_PIPELINE_RUN_ID}" \
    LOTUS_REPO_ROOT="/app" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY --from=builder-output-validator /install /usr/local
COPY contracts/domain-data-products ./contracts/domain-data-products

RUN /usr/local/bin/python3.12 -I -S -c "import pathlib, shutil, sysconfig; roots={pathlib.Path(sysconfig.get_path(name)).resolve() for name in ('purelib','platlib')}; targets={path for root in roots for pattern in ('pip','pip-*.dist-info') for path in root.glob(pattern)}; assert targets; [shutil.rmtree(path) if path.is_dir() else path.unlink() for path in targets]"
RUN /usr/local/bin/python3.12 -I -S -c "import ensurepip, pathlib, shutil, sysconfig; path=pathlib.Path(ensurepip.__file__).parent.resolve(); stdlib=pathlib.Path(sysconfig.get_path('stdlib')).resolve(); assert path == stdlib / 'ensurepip'; shutil.rmtree(path)"
RUN apk upgrade --no-cache
RUN addgroup -S -g 10001 lotus && \
    adduser -S -D -H -u 10001 -G lotus -s /sbin/nologin lotus && \
    chown lotus:lotus /app
USER lotus
RUN /usr/local/bin/python3.12 -I -S -c "import importlib.machinery, pathlib, sys, sysconfig; forbidden=('pip','ensurepip','pytest','ruff','mypy','bandit','deptry','radon','vulture','pre_commit','sitecustomize','usercustomize'); install_roots={pathlib.Path(sysconfig.get_path(name)).resolve() for name in ('purelib','platlib')}; pth_files=sorted(str(path) for root in install_roots for path in root.glob('*.pth')); sys.exit('Runtime image contains startup path files: '+', '.join(pth_files)) if pth_files else None; archive_paths=sorted(str(path) for raw_path in sys.path if raw_path and (path:=pathlib.Path(raw_path)).is_file()); sys.exit('Runtime image contains import-path archives: '+', '.join(archive_paths)) if archive_paths else None; roots={*(str(pathlib.Path(raw_path).resolve()) for raw_path in sys.path if raw_path), *(str(path) for path in install_roots)}; present=[name for name in forbidden if importlib.machinery.PathFinder.find_spec(name, list(roots)) is not None]; sys.exit('Runtime image contains forbidden tooling: '+', '.join(present)) if present else print('runtime dependency guard passed')"

EXPOSE 8130
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8130/health/ready', timeout=3).read()"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8130"]
