# syntax=docker/dockerfile:1
FROM python:3.12-slim-trixie

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends g++ libgammu-dev pkg-config ffmpeg gammu obexftp bluez openssh-client \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv/e52modern
COPY . .

# Keeps the existing Nokia Skin Compiler and bmconv toolchain.
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export PIP_CERT=/run/secrets/proxy_ca; fi \
    && pip install --no-cache-dir -e '.[theme,phone,media,transport-discovery]' \
    && tools/s60/build.sh \
    && mkdir -p build workspace /symbian-auth \
    && chown 10001:10001 /symbian-auth \
    && chown -R 10001:10001 /srv/e52modern

USER 10001:10001
EXPOSE 8765
CMD ["python", "-m", "symport.web", "--host", "0.0.0.0", "--port", "8765"]
