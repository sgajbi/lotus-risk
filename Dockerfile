FROM python:3.12-slim

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
    LOTUS_CI_PIPELINE_RUN_ID="${LOTUS_CI_PIPELINE_RUN_ID}"

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
COPY scripts ./scripts
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -e "."
RUN python -c "import importlib.util, sys; forbidden=('pytest','ruff','mypy','bandit','deptry','radon','vulture','pre_commit'); present=[name for name in forbidden if importlib.util.find_spec(name) is not None]; sys.exit('Runtime image contains dev tooling: '+', '.join(present)) if present else print('runtime dependency guard passed')"

EXPOSE 8130
CMD ["uvicorn", "src.app.main:app", "--host", "0.0.0.0", "--port", "8130"]
