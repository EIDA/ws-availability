FROM gricad-registry.univ-grenoble-alpes.fr/osug/resif/resif_docker/obspy:1.2.1-python-3.8-slim
MAINTAINER RESIF DC <resif-dc@univ-grenoble-alpes.fr>
RUN pip install --no-cache-dir gunicorn
COPY requirements.txt /
RUN pip install --no-cache-dir -r /requirements.txt

WORKDIR /appli
COPY start.py config.py ./
COPY apps ./apps/
COPY templates ./templates/
COPY static ./static/

CMD ["/bin/bash", "-c", "gunicorn --bind 0.0.0.0:8000 start:app"]
