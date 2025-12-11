FROM nvidia/cuda:12.9.0-cudnn-runtime-ubuntu24.04

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_PREFER_BINARY=1 \
    CUDA_HOME=/usr/local/cuda-12.9 \
    DEBCONF_NOWARNINGS=yes
RUN rm /bin/sh && ln -s /bin/bash /bin/sh
RUN printf "Types: deb\nURIs: https://mirrors.tuna.tsinghua.edu.cn/ubuntu/\nSuites: noble noble-updates noble-security\nComponents: main restricted universe multiverse\nSigned-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg" >> /etc/apt/sources.list.d/ubuntu.sources

RUN apt-get update \
    && apt-get -y upgrade \
    && apt-get install -y \
        poppler-utils \
        libpoppler-dev \
        wget \
        curl \
        git \
        ffmpeg \
        libsm6 \
        libxext6 \
        python3 \
        python3-venv \
        python3-pip
    # && apt-get clean \
    # && rm -rf /var/lib/apt/lists/* \
    # && rm -rf /tmp/* /var/tmp/*

WORKDIR /app

ADD . /app/

RUN python3 -m venv /app/venv

RUN /app/venv/bin/pip install --upgrade pip \
    && /app/venv/bin/pip install uv
RUN /app/venv/bin/uv sync
RUN /app/venv/bin/uv pip install --no-build-isolation "git+https://github.com/facebookresearch/detectron2.git"

ENTRYPOINT [ "/app/venv/bin/uv", "run", "server.py" ]
