FROM python:3.10-bookworm


COPY requirements.txt /app/requirements.txt

RUN set -ex \
    && python -m venv /env \
    && /env/bin/pip install --upgrade pip \
    && /env/bin/pip install --no-cache-dir -r /app/requirements.txt


COPY . /app
WORKDIR /app

RUN /env/bin/python manage.py collectstatic --no-input

ENV VIRTUAL_ENV /env
ENV PATH /env/bin:$PATH

EXPOSE 80

CMD ["gunicorn", "--bind", "0.0.0.0:80", "--workers", "3", "openCGaT.wsgi:application"]
