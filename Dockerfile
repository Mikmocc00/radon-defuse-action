FROM ubuntu:20.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
  && apt-get install -y python3-pip python3-dev git \
  && cd /usr/local/bin \
  && ln -s /usr/bin/python3 python \
  && pip3 install --upgrade pip

RUN git config --global --add safe.directory '*'

COPY entrypoint.py /entrypoint.py
COPY requirements.txt /requirements.txt
COPY extractors/ /extractors/

RUN pip3 install -r requirements.txt

ENTRYPOINT ["python3", "/entrypoint.py"]
