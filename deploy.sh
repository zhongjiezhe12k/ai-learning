#!/bin/bash
# ═══════════════════════════════════════════════════════════
# AI Agent 全栈助手 — 一键部署脚本
# 使用方式：bash deploy.sh
# ═══════════════════════════════════════════════════════════

set -e

echo "========================================"
echo "  AI Agent 全栈助手 — Docker 部署"
echo "========================================"
echo ""

# 检查 .env 文件
if [ ! -f .env ]; then
    echo "❌ 未找到 .env 文件"
    echo "   请先配置 API Key："
    echo "   cp .env.example .env"
    echo "   然后编辑 .env 填入 BAILIAN_API_KEY"
    exit 1
fi

# 检查 Docker
if ! command -v docker &> /dev/null; then
    echo "❌ 未安装 Docker，请先安装："
    echo "   curl -fsSL https://get.docker.com | sh"
    exit 1
fi

# 检查 docker-compose
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "❌ 未安装 docker-compose"
    exit 1
fi

COMPOSE_CMD="docker-compose"
if docker compose version &> /dev/null 2>&1; then
    COMPOSE_CMD="docker compose"
fi

echo "✅ 环境检查通过"
echo ""

# 构建并启动
echo "📦 构建镜像..."
$COMPOSE_CMD build --no-cache

echo ""
echo "🚀 启动服务..."
$COMPOSE_CMD up -d

echo ""
echo "⏳ 等待服务就绪..."
sleep 8

# 健康检查
echo ""
echo "🔍 健康检查..."
if curl -s http://localhost/healthz > /dev/null 2>&1; then
    echo "   ✅ 前端 OK"
else
    echo "   ⚠️  前端启动中（可能需要 10-30 秒）"
fi

if curl -s http://localhost/api/ > /dev/null 2>&1; then
    echo "   ✅ 后端 OK"
else
    echo "   ⚠️  后端启动中"
fi

echo ""
echo "========================================"
echo "  部署完成！"
echo ""
echo "  🌐 前端：http://localhost"
echo "  📖 API 文档：http://localhost/docs"
echo "  ❤️  健康检查：http://localhost/api/"
echo ""
echo "  查看日志：$COMPOSE_CMD logs -f"
echo "  停止服务：$COMPOSE_CMD down"
echo "========================================"
