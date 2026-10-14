# frontend

React + Ant Design 保险商城和智能客服前端。

当前状态：M0 最小启动骨架。

## 本地运行

```powershell
docker compose up frontend --build
```

访问：

```text
http://localhost:5173
```

## 后端地址配置

本地开发默认代理到 `http://127.0.0.1:8001`。如需覆盖，复制 `.env.example` 为 `.env.local` 后修改 `VITE_BACKEND_HOST` 和 `VITE_BACKEND_PORT`。

容器运行时通过 `BACKEND_HOST` 和 `BACKEND_PORT` 配置 Nginx 代理目标，默认值为 `backend:8001`。
