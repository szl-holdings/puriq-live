FROM python:3.14-slim@sha256:a2b82f3c48559aa0a8446d9af49826b6e2b2016f4cd2afabfe6013ec53729170

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1
ARG PURIQ_SOURCE_REVISION=UNAVAILABLE
ENV PURIQ_SOURCE_REVISION=${PURIQ_SOURCE_REVISION}

WORKDIR /app
COPY requirements.txt constraints-runtime.txt ./
# Upgrade the image's package installer before resolving application packages.
# The strict container audit includes pip; do not suppress its findings.
RUN python -m pip install --disable-pip-version-check --no-cache-dir --only-binary=:all: 'pip==26.2.1' \
    && python -m pip install --disable-pip-version-check --no-cache-dir --only-binary=:all: -r requirements.txt

COPY app.py puriq_market.py puriq_research.py puriq_research_routes.py szl_puriq.py ./
COPY puriq_verity.py puriq_reference.py puriq_price_routes.py ./
COPY LICENSE NOTICE ./
COPY static/research/ ./static/research/
COPY static/signed-prices/ ./static/signed-prices/
COPY tools/vendor_vela.py ./tools/vendor_vela.py
RUN python tools/vendor_vela.py

RUN useradd --create-home --uid 1000 --shell /usr/sbin/nologin szl
USER szl

EXPOSE 7860
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:7860/healthz', timeout=4).read()"

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860", "--no-server-header"]
