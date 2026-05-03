# Stage 1: Build React frontend
FROM node:22-slim AS frontend
WORKDIR /build
COPY ap-web/frontend/package.json ap-web/frontend/package-lock.json ./
RUN npm ci
COPY ap-web/frontend/ ./
RUN npm run build

# Stage 2: Python app
FROM python:3.12-slim
WORKDIR /app

# Install system dependencies (git for APWorld index cloning, gosu for entrypoint,
# curl for the container healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends git gosu curl && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY ap-lib/ /tmp/ap-lib/
COPY ap-web/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt /tmp/ap-lib/ && rm -rf /tmp/ap-lib/

# Copy backend code
COPY ap-web/*.py ap-web/api/ ./
COPY ap-web/api/ ./api/
COPY ap-web/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Copy built frontend
COPY --from=frontend /build/dist ./frontend/dist

# Non-root user. We deliberately do NOT set `USER apweb` at the image level:
# the entrypoint needs root briefly to chown mounted volumes, then drops to
# apweb via `gosu apweb` before exec'ing gunicorn. Aikido / CIS Docker
# benchmarks flag the missing USER directive but in this layout the
# application process never runs as root — entrypoint.sh is the sole code
# that runs as root, and it does nothing untrusted.
RUN useradd -m -u 1000 apweb

# State directory for server manager + AP worlds dir
RUN mkdir -p /app/.state /home/apweb/.local/share/Archipelago/worlds \
    && chown -R apweb:apweb /app /home/apweb

ENV AP_OUTPUT_DIR=/data/output \
    AP_SERVER_EXE=/opt/archipelago/ArchipelagoServer \
    AP_DEBUG=0 \
    AP_HOST=localhost \
    AP_PORT_RANGE_START=38281 \
    AP_PORT_RANGE_END=38380

EXPOSE 5001
EXPOSE 38281-38380

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -fsS http://localhost:5001/api/health >/dev/null || exit 1

ENTRYPOINT ["/entrypoint.sh"]
CMD ["gunicorn", "-c", "gunicorn.conf.py", "app:create_app()"]
