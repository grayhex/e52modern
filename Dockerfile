FROM python:3.12-slim-trixie

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends g++ \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv/e52modern
COPY . .

# Keeps the existing Nokia Skin Compiler and bmconv toolchain.
RUN pip install --no-cache-dir -e '.[theme]' \
    && tools/s60/build.sh \
    && mkdir -p build workspace \
    && chown -R 10001:10001 /srv/e52modern

USER 10001:10001
EXPOSE 8765
CMD ["python", "-m", "symport.web", "--host", "0.0.0.0", "--port", "8765"]
