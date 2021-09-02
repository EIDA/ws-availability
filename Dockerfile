FROM gricad-registry.univ-grenoble-alpes.fr/osug/resif/resif_docker/obspy:1.2.1-python-3.8-slim
RUN pip install --upgrade pip
RUN pip install --no-cache-dir gunicorn
COPY requirements.txt /
RUN pip install --no-cache-dir -r /requirements.txt

WORKDIR /appli
COPY start.py config.py ./
COPY apps ./apps/
COPY templates ./templates/
COPY static ./static/

CMD ["/bin/bash", "-c", "gunicorn --workers 2 --timeout 60 --bind 0.0.0.0:9001 start:app"]
