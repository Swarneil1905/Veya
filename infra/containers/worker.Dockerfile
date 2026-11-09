FROM ghcr.io/astral-sh/uv:0.11.23@sha256:d0a0a753ab981624b49c97abc98821c1c09f4ca69d1ef5cee69c501be3d88479 AS uv
FROM python:3.13.14-slim-bookworm@sha256:67a1e1f215ccda113cfc024e8639049257e88f273898f595b61476d128d387e8
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_NO_CACHE=1 UV_PYTHON_DOWNLOADS=never PYTHONDONTWRITEBYTECODE=1
COPY services/worker/pyproject.toml services/worker/uv.lock /app/services/worker/
RUN uv sync --project services/worker --locked --no-dev --no-install-project
COPY services/worker/veya_worker /app/services/worker/veya_worker
RUN uv sync --project services/worker --locked --no-dev --no-editable \
    && useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin veya \
    && mkdir /state && chown 10001:10001 /state
ENV PATH="/app/services/worker/.venv/bin:$PATH"
USER 10001:10001
VOLUME ["/state"]
HEALTHCHECK --interval=10s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-m", "veya_worker.health", "--storage", "/state"]
CMD ["veya-worker", "--address", "temporal:7233", "--storage", "/state"]
