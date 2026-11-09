FROM ghcr.io/astral-sh/uv:0.11.23@sha256:d0a0a753ab981624b49c97abc98821c1c09f4ca69d1ef5cee69c501be3d88479 AS uv
FROM python:3.13.14-slim-bookworm@sha256:67a1e1f215ccda113cfc024e8639049257e88f273898f595b61476d128d387e8
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_NO_CACHE=1 UV_PYTHON_DOWNLOADS=never PYTHONDONTWRITEBYTECODE=1
COPY services/runtime/pyproject.toml services/runtime/uv.lock /app/services/runtime/
RUN uv sync --project services/runtime --locked --no-dev --extra team --no-install-project
COPY services/runtime/veya /app/services/runtime/veya
COPY services/runtime/migrations /app/services/runtime/migrations
RUN uv sync --project services/runtime --locked --no-dev --extra team --no-editable \
    && useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin veya
ENV PATH="/app/services/runtime/.venv/bin:$PATH"
USER 10001:10001
EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=7s --start-period=20s --retries=3 \
    CMD ["python", "-m", "veya.team.health"]
CMD ["uvicorn", "veya.team.app:from_environment", "--factory", "--host", "0.0.0.0", "--port", "8080", "--no-access-log"]
