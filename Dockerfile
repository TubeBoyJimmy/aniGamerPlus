FROM python:3.13-slim

# 系統依賴 + ffmpeg + cifs-utils（掛載 SMB share）
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        g++ gcc make \
        libevent-dev libffi-dev libxml2-dev libxslt-dev zlib1g-dev \
        ffmpeg cifs-utils \
    && rm -rf /var/lib/apt/lists/*

# 時區設定（排程功能需要正確時區）
ENV TZ=Asia/Taipei
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

WORKDIR /app
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

COPY . .

ENTRYPOINT ["python3", "-u", "aniGamerPlus.py"]
