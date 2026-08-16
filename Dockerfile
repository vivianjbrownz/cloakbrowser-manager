ARG RUNTIME_BASE_IMAGE=ghcr.io/vivianjbrownz/cloakbrowser-manager@sha256:bf578160bb81d4cc7dea5a8c35c639adb75ef69f50b45e8e3eec67d0deb05a81

# Routine releases keep the deployed browser binary, fonts, libraries, and
# Python dependency set stable. Deliberate foundation upgrades use
# Dockerfile.full and then pin the validated digest above.
FROM node:20-slim AS frontend-builder
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend/ ./
RUN npm run build

FROM ${RUNTIME_BASE_IMAGE}

LABEL org.opencontainers.image.source="https://github.com/vivianjbrownz/cloakbrowser-manager"
LABEL org.opencontainers.image.description="BeginOS inventory build of CloakBrowser Manager"
LABEL org.opencontainers.image.licenses="MIT"

COPY backend/ /app/backend/
COPY --from=frontend-builder /build/dist /app/frontend/dist
COPY entrypoint.sh /entrypoint.sh
RUN find /app/backend -type d -name __pycache__ -prune -exec rm -rf {} + \
    && chmod +x /entrypoint.sh
