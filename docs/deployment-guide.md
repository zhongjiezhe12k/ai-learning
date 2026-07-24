# 阿里云部署指南 — AI Agent 全栈助手

> 适用：阿里云 ECS + Docker Compose | 预计费用：~50 元/月

---

## 1. 前置准备

| 准备项 | 说明 |
|--------|------|
| 阿里云账号 | [免费注册](https://www.aliyun.com) |
| ECS 实例 | 2vCPU + 4GB 内存 + 40GB 云盘（最低配 ~50元/月）|
| 操作系统 | Ubuntu 22.04（推荐）或 CentOS 7.9 |
| 域名（可选） | 有域名体验更好，没有也能用公网 IP |

---

## 2. 购买并配置 ECS

### 2.1 创建实例

1. 登录 [阿里云 ECS 控制台](https://ecs.console.aliyun.com)
2. 点击「创建实例」
3. 配置：
   - 地域：离你最近的（如 广州/深圳）
   - 镜像：Ubuntu 22.04
   - 规格：2 vCPU / 4 GiB（ecs.c7.large 或 ecs.g7.large）
   - 系统盘：40 GB ESSD
   - 勾选「分配公网 IPv4 地址」
   - 按量付费（不玩了随时释放，不花钱）

### 2.2 安全组配置

在实例的安全组中添加以下入方向规则：

| 端口 | 协议 | 来源 | 说明 |
|------|------|------|------|
| 22 | TCP | 0.0.0.0/0 | SSH 远程连接 |
| 80 | TCP | 0.0.0.0/0 | HTTP（网站访问） |
| 443 | TCP | 0.0.0.0/0 | HTTPS（如果需要）|

> ⚠️ 不要把 8000/8501 暴露到公网！所有流量通过 nginx 80 端口进入。

---

## 3. 服务器环境配置

### 3.1 SSH 登录

```bash
ssh root@<你的公网IP>
```

### 3.2 安装 Docker

```bash
# 一键安装
curl -fsSL https://get.docker.com | sh

# 启动 Docker
systemctl start docker
systemctl enable docker

# 验证
docker --version
```

### 3.3 安装 Docker Compose

```bash
# 新版 Docker 自带 compose 插件
docker compose version

# 如果没有，手动安装
apt install docker-compose-plugin -y
```

---

## 4. 部署项目

### 4.1 克隆代码

```bash
cd /opt
git clone https://github.com/zhongjiezhe12k/ai-learning.git
cd ai-learning
```

### 4.2 配置 API Key

```bash
cp .env.example .env
vim .env
```

编辑内容：
```ini
BAILIAN_API_KEY=sk-xxxxxxxxxxxxxxxxxxxx
```

### 4.3 一键部署

```bash
# 给脚本执行权限
chmod +x deploy.sh

# 运行
bash deploy.sh
```

等待 2-3 分钟，看到 "部署完成" 即可。

### 4.4 验证

```bash
# 健康检查
curl http://localhost/api/
# → {"status":"running","version":"2.0.0",...}

# 访问前端
curl http://localhost/
```

---

## 5. 访问你的应用

浏览器打开：`http://<你的公网IP>`

| 地址 | 内容 |
|------|------|
| http://你的IP | Streamlit 聊天界面 |
| http://你的IP/docs | Swagger API 文档 |
| http://你的IP/api/ | 健康检查 |

---

## 6. 常用运维命令

```bash
# 进入项目目录
cd /opt/ai-learning

# 查看运行状态
docker compose ps

# 查看日志
docker compose logs -f          # 所有服务
docker compose logs -f backend  # 只看后端

# 重启服务
docker compose restart

# 更新代码后重新部署
git pull
docker compose build --no-cache backend
docker compose up -d

# 停止服务
docker compose down

# 查看资源占用
docker stats
```

---

## 7. （可选）配置域名 + HTTPS

### 7.1 域名解析

在域名 DNS 设置中添加 A 记录：
```
ai.yourdomain.com → <公网IP>
```

### 7.2 Nginx 配置 HTTPS

修改 `nginx.conf` 添加 SSL 证书配置（可用 Let's Encrypt 免费证书）。

```bash
# 安装 certbot
apt install certbot python3-certbot-nginx -y

# 获取证书
certbot --nginx -d ai.yourdomain.com
```

---

## 8. （可选）GitHub Actions 自动部署

创建 `.github/workflows/deploy.yml`：

```yaml
name: Deploy to Alibaba Cloud
on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Deploy via SSH
        uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.ECS_HOST }}
          username: root
          key: ${{ secrets.ECS_SSH_KEY }}
          script: |
            cd /opt/ai-learning
            git pull
            docker compose build --no-cache backend frontend
            docker compose up -d
```

设置 GitHub Secrets：
- `ECS_HOST`：你的公网 IP
- `ECS_SSH_KEY`：SSH 私钥

---

## 9. 费用估算

| 项目 | 配置 | 月费用 |
|------|------|--------|
| ECS 实例 | 2vCPU 4GB | ~50 元 |
| 系统盘 | 40GB ESSD | ~14 元 |
| 公网 IP | 按流量 | ~10 元（小流量）|
| **合计** | | **~75 元/月** |

> 💡 按量付费：不用时可以「释放」实例，停止计费。面试前再创建新实例部署即可。

---

## 10. Docker 架构图（部署视图）

```
┌──────────────────────────────────────────────┐
│              ECS 实例 (阿里云)                 │
│                                              │
│  ┌────────────────────────────────────────┐  │
│  │  Nginx (80)                            │  │
│  │  ├── /api/*    → backend:8000          │  │
│  │  ├── /docs     → backend:8000          │  │
│  │  └── /*        → frontend:8501         │  │
│  └──────┬──────────────────┬──────────────┘  │
│         │                  │                  │
│  ┌──────▼─────┐    ┌──────▼─────┐           │
│  │  backend    │    │  frontend  │           │
│  │  (FastAPI)  │    │ (Streamlit)│           │
│  │  :8000      │    │  :8501     │           │
│  │  internal   │    │  internal  │           │
│  └─────────────┘    └────────────┘           │
│                                              │
│  Docker Network: agent-network (bridge)      │
└──────────────────────────────────────────────┘
```

---

> 有任何问题可以问 AI：把报错信息复制给 ChatGPT/Claude，通常 5 分钟解决。
