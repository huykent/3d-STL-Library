FROM python:3.12-slim

# System deps for pyrender EGL backend and archive extraction
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglx-mesa0 \
    libgles2 \
    libegl1 \
    libgomp1 \
    unrar-free \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Ensure thumbnails and temp dirs exist
RUN mkdir -p /app/thumbnails /app/temp

# EGL backend for pyrender on headless Linux (set before pyrender import)
ENV PYOPENGL_PLATFORM=egl

RUN chmod +x start.sh

EXPOSE 8000

CMD ["./start.sh"]
