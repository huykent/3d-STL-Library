#!/bin/bash

# Navigate to the script's directory (project root on VPS)
cd "$(dirname "$0")"

echo "=========================================="
echo "    Updating 3D STL Library Server        "
echo "=========================================="

# ── 1. Pull latest code ────────────────────────────────────────────────────────
echo ""
echo "1. Pulling latest code from GitHub..."
BEFORE_COMMIT=$(git rev-parse HEAD)
GIT_OUTPUT=$(git pull origin main)
echo "$GIT_OUTPUT"
AFTER_COMMIT=$(git rev-parse HEAD)

if [ "$BEFORE_COMMIT" = "$AFTER_COMMIT" ]; then
    echo ""
    echo "✅ Already up to date. Không có bản mới — bỏ qua khởi động lại."
    echo "=========================================="
    echo "    Không có thay đổi nào.                "
    echo "=========================================="
    exit 0
fi

# ── 2. Phát hiện thư mục nào thay đổi ────────────────────────────────────────
echo ""
echo "2. Phân tích thay đổi so với commit trước..."
CHANGED_FILES=$(git diff --name-only "$BEFORE_COMMIT" "$AFTER_COMMIT")
echo "Files thay đổi:"
echo "$CHANGED_FILES"

BACKEND_CHANGED=false
FRONTEND_CHANGED=false
COMPOSE_CHANGED=false

if echo "$CHANGED_FILES" | grep -qE "^backend/"; then
    BACKEND_CHANGED=true
    echo "  → Backend (api + worker) có thay đổi"
fi

if echo "$CHANGED_FILES" | grep -qE "^frontend/"; then
    FRONTEND_CHANGED=true
    echo "  → Frontend có thay đổi"
fi

if echo "$CHANGED_FILES" | grep -qE "^docker-compose\.yml$|^\.env"; then
    COMPOSE_CHANGED=true
    echo "  → docker-compose.yml hoặc .env có thay đổi — rebuild toàn bộ"
fi

# ── 3. Rebuild + restart chỉ những service liên quan ─────────────────────────
echo ""

# Nếu docker-compose hoặc .env thay đổi: rebuild toàn bộ
if [ "$COMPOSE_CHANGED" = true ]; then
    echo "3. docker-compose hoặc .env thay đổi → Rebuild toàn bộ stack..."
    docker builder prune -f
    docker image prune -f
    docker compose down
    docker compose build --no-cache
    docker compose up -d
    echo "✅ Toàn bộ stack đã được rebuild và khởi động lại."

else
    SERVICES_TO_REBUILD=""

    if [ "$BACKEND_CHANGED" = true ]; then
        SERVICES_TO_REBUILD="$SERVICES_TO_REBUILD api worker"
    fi

    if [ "$FRONTEND_CHANGED" = true ]; then
        SERVICES_TO_REBUILD="$SERVICES_TO_REBUILD frontend"
    fi

    if [ -z "$SERVICES_TO_REBUILD" ]; then
        echo "3. Không có service nào cần rebuild (chỉ docs/scripts thay đổi)."
    else
        echo "3. Rebuilding service(s):$SERVICES_TO_REBUILD ..."
        # Build image mới cho từng service
        docker compose build --no-cache $SERVICES_TO_REBUILD

        # Restart từng service (không down toàn stack)
        docker compose up -d --no-deps $SERVICES_TO_REBUILD

        echo "✅ Đã rebuild và restart:$SERVICES_TO_REBUILD"
    fi
fi

# ── 4. Dọn dẹp image cũ không dùng ──────────────────────────────────────────
echo ""
echo "4. Dọn dẹp Docker image cũ..."
docker image prune -f

echo ""
echo "=========================================="
echo "    Update hoàn tất thành công!           "
echo "=========================================="
