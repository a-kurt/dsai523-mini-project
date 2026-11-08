# syntax=docker/dockerfile:1
FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
COPY requirements.txt ./
# The optional mount keeps a managed environment's proxy CA out of the image.
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then \
      PIP_CERT=/run/secrets/proxy_ca pip install --no-cache-dir -r requirements.txt; \
    else pip install --no-cache-dir -r requirements.txt; fi
RUN groupadd --system court && useradd --system --gid court --home /app court
COPY --chown=court:court movie_court ./movie_court
COPY --chown=court:court scripts/container-start.sh ./scripts/container-start.sh
RUN mkdir -p /app/instance && chown court:court /app/instance
USER court
EXPOSE 8080
CMD ["sh", "scripts/container-start.sh"]
