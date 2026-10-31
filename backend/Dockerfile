FROM python:3.14-slim AS wheels

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /build
COPY requirements.txt ./requirements.txt
RUN python -m pip wheel --wheel-dir /wheels -r requirements.txt

FROM python:3.14-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PATH="/home/app/.local/bin:$PATH"

RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --create-home --home-dir /home/app app
WORKDIR /app
COPY --from=wheels /wheels /wheels
COPY requirements.txt /tmp/requirements.txt
RUN python -m pip install --no-cache-dir --no-index --find-links=/wheels \
      -r /tmp/requirements.txt \
    && rm -rf /wheels /tmp/requirements.txt
COPY --chown=app:app . /app
COPY --chmod=755 docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN mkdir -p /app/staticfiles && chown -R app:app /app

USER 10001:10001
EXPOSE 8000
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "--bind=0.0.0.0:8000", "--workers=3", "--access-logfile=-", "--access-logformat=%(h)s %(U)s %(s)s %(L)s"]
