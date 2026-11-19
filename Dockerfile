# 单阶段构建：Python 后端 + 已打包好的前端 dist（dist 由本地 npm run build 后复制到构建上下文）
FROM python:3.13-slim
WORKDIR /app

# 系统依赖（lxml、pillow 等可能需要编译）
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libxml2-dev libxslt1-dev \
    && rm -rf /var/lib/apt/lists/*

# Python 依赖
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# 后端代码
COPY backend/app/ ./app/
COPY backend/scripts/ ./scripts/

# 前端构建产物：直接从构建上下文的 frontend/dist 拷入镜像
# 放到 /frontend/dist —— 与 main.py 中 BASE_DIR.parent/frontend/dist 对应
# （容器内 app/ 在 /app，故 BASE_DIR=/app，BASE_DIR.parent=/，即 /frontend/dist）
COPY frontend/dist/ /frontend/dist/

# 数据目录（图片、SQLite 库），默认 /app/data，可通过 -v 挂载卷持久化
ENV DATA_DIR=/app/data \
    HOST=0.0.0.0 \
    PORT=8100 \
    PYTHONUNBUFFERED=1
RUN mkdir -p /app/data

EXPOSE 8100

# 启动时：空库会自动初始化（main.py lifespan 内的 init_database），无需手动建表
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8100"]
