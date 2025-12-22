FROM python:3.13-bookworm

COPY requirements.txt /app/requirements.txt

RUN set -ex \
    && pip install --upgrade pip \
    && pip install --no-cache-dir -r /app/requirements.txt


COPY . /app
WORKDIR /app

RUN python manage.py collectstatic --no-input


EXPOSE 80

CMD ["gunicorn", "--bind", "0.0.0.0:80", "--workers", "3", "openCGaT.wsgi:application"]
