#!/bin/bash
# ═══════════════════════════════════════════════════════════
# AI Agent 全栈助手 — 无 Docker 直接部署脚本
# 国内网络友好，不需要 Docker Hub
# 使用方式：bash deploy-no-docker.sh
# ═══════════════════════════════════════════════════════════

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "========================================"
echo "  AI Agent 全栈助手 — 直接部署"
echo "  无需 Docker · 国内网络友好"
echo "========================================"
echo ""

PROJECT_DIR="/opt/ai-learning"
cd $PROJECT_DIR

# ── 1. 安装系统依赖 ──
echo -e "${YELLOW}[1/6] 安装系统依赖...${NC}"
apt update -qq
apt install -y -qq python3 python3-pip python3-venv nginx curl > /dev/null 2>&1
echo -e "${GREEN}  OK${NC}"

# ── 2. 配置 Python 虚拟环境 ──
echo -e "${YELLOW}[2/6] 配置 Python 环境...${NC}"
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip -q

# 使用清华镜像加速
pip install -r requirements.txt -q -i https://pypi.tuna.tsinghua.edu.cn/simple
echo -e "${GREEN}  OK${NC}"

# ── 3. 检查 .env ──
echo -e "${YELLOW}[3/6] 检查配置...${NC}"
if [ ! -f .env ]; then
    cp .env.example .env
    echo "  ⚠️  请先编辑 .env 填入 API Key："
    echo "     nano /opt/ai-learning/.env"
    echo "     然后重新运行 bash deploy-no-docker.sh"
    exit 1
fi
echo -e "${GREEN}  OK${NC}"

# ── 4. 配置 Nginx ──
echo -e "${YELLOW}[4/6] 配置 Nginx 反向代理...${NC}"
cat > /etc/nginx/sites-available/ai-agent << 'NGINX_EOF'
server {
    listen 80;
    server_name _;
    client_max_body_size 10m;

    # FastAPI 后端
    location /api/ {
        proxy_pass http://127.0.0.1:8000/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_buffering off;
        proxy_read_timeout 120s;
    }
    location /docs {
        proxy_pass http://127.0.0.1:8000/docs;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
    }
    location /openapi.json {
        proxy_pass http://127.0.0.1:8000/openapi.json;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
    }

    # Streamlit 前端
    location / {
        proxy_pass http://127.0.0.1:8501/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400;
    }
    location /_stcore/stream {
        proxy_pass http://127.0.0.1:8501/_stcore/stream;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400;
    }
}
NGINX_EOF

# 启用站点
ln -sf /etc/nginx/sites-available/ai-agent /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx
echo -e "${GREEN}  OK${NC}"

# ── 5. 配置 systemd 服务 ──
echo -e "${YELLOW}[5/6] 配置后台服务...${NC}"

# 后端服务
cat > /etc/systemd/system/ai-backend.service << SYSTEMD_EOF
[Unit]
Description=AI Agent FastAPI Backend
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$PROJECT_DIR
Environment="PATH=$PROJECT_DIR/venv/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=$PROJECT_DIR/venv/bin/uvicorn day23_api_refinement:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
SYSTEMD_EOF

# 前端服务
cat > /etc/systemd/system/ai-frontend.service << SYSTEMD_EOF
[Unit]
Description=AI Agent Streamlit Frontend
After=ai-backend.service
Requires=ai-backend.service

[Service]
Type=simple
User=root
WorkingDirectory=$PROJECT_DIR
Environment="PATH=$PROJECT_DIR/venv/bin:/usr/local/bin:/usr/bin:/bin"
Environment="API_BASE=http://127.0.0.1:8000"
ExecStart=$PROJECT_DIR/venv/bin/streamlit run day24_streamlit_frontend.py \
    --server.address=127.0.0.1 \
    --server.port=8501 \
    --server.headless=true \
    --browser.gatherUsageStats=false
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
SYSTEMD_EOF

systemctl daemon-reload
echo -e "${GREEN}  OK${NC}"

# ── 6. 启动服务 ──
echo -e "${YELLOW}[6/6] 启动服务...${NC}"
systemctl enable ai-backend ai-frontend
systemctl restart ai-backend

echo "  等待后端启动..."
sleep 5

# 检查后端
if curl -s http://127.0.0.1:8000/ > /dev/null 2>&1; then
    echo -e "  ${GREEN}✅ 后端 OK${NC}"
else
    echo "  ⚠️  后端启动中，等待 10 秒..."
    sleep 10
fi

systemctl restart ai-frontend
sleep 3

echo ""
echo "========================================"
echo -e "  ${GREEN}部署完成！${NC}"
echo ""
echo "  🌐 网站地址：http://$(curl -s ifconfig.me 2>/dev/null || echo '你的公网IP')"
echo "  📖 API 文档：http://你的IP/docs"
echo ""
echo "  常用命令："
echo "    systemctl status ai-backend   # 查看后端状态"
echo "    systemctl status ai-frontend  # 查看前端状态"
echo "    journalctl -u ai-backend -f   # 查看后端日志"
echo "    journalctl -u ai-frontend -f  # 查看前端日志"
echo "    systemctl restart ai-backend  # 重启后端"
echo "========================================"
