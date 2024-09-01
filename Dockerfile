FROM python:3.11

WORKDIR /app

STOPSIGNAL SIGINT

COPY ./requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /app/requirements.txt

COPY ./src /app/src
COPY ./alembic.ini /app/alembic.ini
COPY ./config.py /app/config.py
COPY ./log.yaml /app/log.yaml
COPY ./init-db.sh /app/init-db.sh

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "80", "--log-config", "log.yaml"]
