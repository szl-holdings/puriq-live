FROM python:3.12-slim@sha256:423ed6ab25b1921a477529254bfeeabf5855151dc2c3141699a1bfc852199fbf

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1
ARG PURIQ_SOURCE_REVISION=UNAVAILABLE
ENV PURIQ_SOURCE_REVISION=${PURIQ_SOURCE_REVISION}

WORKDIR /app
COPY requirements.txt ./requirements.txt
RUN python -m pip install --disable-pip-version-check --no-cache-dir -r requirements.txt

COPY app.py puriq_market.py szl_puriq.py ./

RUN useradd --create-home --uid 1000 --shell /usr/sbin/nologin szl \
    && chown -R szl:szl /app
USER szl

EXPOSE 7860
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:7860/healthz', timeout=4).read()"

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860", "--no-server-header"]
