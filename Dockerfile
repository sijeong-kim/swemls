FROM ubuntu:oracular
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get -yq install python3-pip python3-venv

WORKDIR /app/

COPY requirements.txt .

RUN python3 -m venv /venv && \
    /venv/bin/pip3 install --no-cache-dir -r requirements.txt

COPY config/ ./config/
COPY checkpoints/best_model.pth ./checkpoints/best_model.pth
COPY src/ ./src/
COPY main.py .

ENTRYPOINT ["/venv/bin/python3", "/app/main.py"]
