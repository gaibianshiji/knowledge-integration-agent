FROM modelscope-registry.cn-beijing.cr.aliyuncs.com/modelscope-repo/python:3.10

# Install Node.js
RUN apt-get update && apt-get install -y curl && \
    curl -fsSL https://deb.nodesource.com/setup_18.x | bash - && \
    apt-get install -y nodejs && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /home/user/app

# Install Python dependencies
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy and build frontend
COPY frontend/ ./frontend/
RUN cd frontend && npm install && npm run build

# Copy backend
COPY backend/ ./backend/

# Create data directories
RUN mkdir -p backend/data/parsed backend/data/graphs backend/data/chunks backend/data/index backend/data/integration backend/data/uploads

# Copy .env
COPY .env.example ./backend/.env

WORKDIR /home/user/app/backend

EXPOSE 7860

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
