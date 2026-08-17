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

git fetch origin main
git reset --hard origin/main
git clean -fd --quiet

AFTER_COMMIT=$(git rev-parse HEAD)
echo "  Trước: $BEFORE_COMMIT"
echo "  Sau:   $AFTER_COMMIT"

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
echo "2. Phân tích thay đổi..."
CHANGED_FILES=$(git diff --name-only "$BEFORE_COMMIT" "$AFTER_COMMIT")
echo "$CHANGED_FILES"

BACKEND_CHANGED=false
FRONTEND_CHANGED=false
DEPS_CHANGED=false   # requirements.txt, Dockerfile, docker-compose.yml, .env

if echo "$CHANGED_FILES" | grep -qE "^backend/"; then
    BACKEND_CHANGED=true
fi
if echo "$CHANGED_FILES" | grep -qE "^frontend/"; then
    FRONTEND_CHANGED=true
fi
# Nếu dependency hoặc infra thay đổi → phải rebuild image
if echo "$CHANGED_FILES" | grep -qE "requirements.*\.txt|Dockerfile|docker-compose\.yml|\.env"; then
    DEPS_CHANGED=true
fi

# ── 3. Update từng phần ───────────────────────────────────────────────────────
echo ""
echo "3. Áp dụng thay đổi..."

# ── Case A: Infra/deps thay đổi → rebuild toàn bộ (chậm nhưng cần thiết) ──
if [ "$DEPS_CHANGED" = true ]; then
    echo "  ⚙️  Infra thay đổi (Dockerfile/requirements/docker-compose) → Rebuild toàn bộ..."
    docker compose build
    docker compose up -d
    echo "  ✅ Toàn bộ stack đã rebuild xong."

else
    # ── Case B: Chỉ source code thay đổi ──────────────────────────────────

    if [ "$BACKEND_CHANGED" = true ]; then
        echo "  🐍 Backend thay đổi → Copy file trực tiếp + restart (không rebuild image)..."
        # Copy toàn bộ backend/app vào container đang chạy — Python không cần compile
        docker cp backend/app/. api:/app/app/    2>/dev/null || true
        docker cp backend/app/. worker:/app/app/ 2>/dev/null || true
        docker restart api worker
        echo "  ✅ api + worker đã restart (~10s)"
    fi

    if [ "$FRONTEND_CHANGED" = true ]; then
        echo "  ⚛️  Frontend thay đổi → Build với Docker cache (nhanh hơn --no-cache)..."
        # Dùng cache — layer node_modules được tái sử dụng nếu package.json không đổi
        docker compose build frontend
        docker compose up -d --no-deps frontend
        echo "  ✅ frontend đã rebuild xong."
    fi

    if [ "$BACKEND_CHANGED" = false ] && [ "$FRONTEND_CHANGED" = false ]; then
        echo "  ℹ️  Chỉ có docs/scripts thay đổi — không cần restart gì cả."
    fi
fi

# ── 4. Dọn dẹp image cũ ──────────────────────────────────────────────────────
echo ""
echo "4. Dọn dẹp Docker image cũ..."
docker image prune -f

echo ""
echo "=========================================="
echo "    Update hoàn tất thành công!           "
echo "=========================================="
