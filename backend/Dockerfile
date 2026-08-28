FROM python:3.12-slim

# System deps for pyrender EGL backend and archive extraction
# Enable non-free repo for unrar (RAR5 support)
RUN sed -i 's/Components: main/Components: main contrib non-free non-free-firmware/g' /etc/apt/sources.list.d/debian.sources || true \
    && sed -i 's/main/main contrib non-free non-free-firmware/g' /etc/apt/sources.list || true \
    && apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglx-mesa0 \
    libgles2 \
    libegl1 \
    libglu1-mesa \
    libgomp1 \
    unrar \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Ensure thumbnails, sessions and temp dirs exist
RUN mkdir -p /app/thumbnails /app/temp /app/sessions

# EGL backend for pyrender on headless Linux (set before pyrender import)
ENV PYOPENGL_PLATFORM=egl

RUN chmod +x start.sh

EXPOSE 8000

CMD ["./start.sh"]
