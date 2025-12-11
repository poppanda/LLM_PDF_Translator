NAME=pdf-translator
TAG=0.1.0
PROJECT_DIRECTORY=$(shell pwd)
MODEL_FILE=models/unilm/publaynet_dit-b_cascade.pth

get-models:
	if [ ! -f $(MODEL_FILE) ]; then \
		wget "https://huggingface.co/Sebas6k/DiT_weights/resolve/main/publaynet_dit-b_cascade.pth?download=true" -P models/unilm -O models/unilm/publaynet_dit-b_cascade.pth; \
	fi

docker-build:
	mkdir -p models/unilm 
	if [ ! -f $(MODEL_FILE) ]; then \
		wget "https://huggingface.co/Sebas6k/DiT_weights/resolve/main/publaynet_dit-b_cascade.pth?download=true" -P models/unilm -O models/unilm/publaynet_dit-b_cascade.pth; \
	fi
	docker build -t ${NAME}:${TAG} .

docker-run:
	docker run -it \
		--runtime=nvidia \
		--name pdf-translator \
		-v ${PROJECT_DIRECTORY}:/app \
		--gpus all \
		-p 8765:8765 \
		${NAME}:${TAG}

run-bash:
	docker run -it \
		--runtime=nvidia \
		--name pdf-translator \
		-v ${PROJECT_DIRECTORY}:/app \
		--gpus all \
		-p 8765:8765 \
		${NAME}:${TAG} /bin/bash

install-cn-font:
	wget https://github.com/Haixing-Hu/latex-chinese-fonts/blob/master/chinese/%E5%AE%8B%E4%BD%93/STSong.ttf?raw=true -O ./fonts/STSong.ttf

py-env-setup:
	uv sync 
	uv pip install --no-build-isolation "git+https://github.com/facebookresearch/detectron2.git"
