FROM python:3.11-slim

WORKDIR /app

# 先复制依赖文件，方便利用 Docker 缓存
COPY requirements.txt .

# 安装依赖
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# 复制项目代码
COPY chatbot.py .
COPY ChatGPT.py .
COPY db.py .

# 容器启动时运行 chatbot
CMD ["python", "chatbot.py"]