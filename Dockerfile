# FitPilot AI 健身助手 — Docker 多阶段构建
# 目标：生产镜像尽量精简，开发镜像包含调试工具

# ── 阶段 1：基础环境 ──────────────────────────────────────────────────────────
FROM python:3.12-slim AS base

ARG APP_USER=echomind
ARG APP_UID=1000
ARG APP_HOME=/home/${APP_USER}

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app \
    HOME=${APP_HOME} \
    XDG_CACHE_HOME=${APP_HOME}/.cache

# No system packages needed — health check uses Python stdlib urllib

# ── 阶段 2：安装 Python 依赖 ──────────────────────────────────────────────────
FROM base AS dependencies

COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# 预下载 ChromaDB 内置的 ONNX embedding 模型（~79MB），避免运行时下载超时
# 使用 Python 标准库，避免依赖 curl、wget、apt-get 等系统工具。
RUN python - <<'PY'
from pathlib import Path
import tarfile
import time
import urllib.request

url = (
    "https://chroma-onnx-models.s3.amazonaws.com/"
    "all-MiniLM-L6-v2/onnx.tar.gz"
)

target_dir = Path(
    "/home/echomind/.cache/chroma/onnx_models/all-MiniLM-L6-v2"
)
archive_path = target_dir / "onnx.tar.gz"

target_dir.mkdir(parents=True, exist_ok=True)

for attempt in range(1, 4):
    try:
        print(f"Downloading Chroma ONNX model, attempt {attempt}/3...")

        with urllib.request.urlopen(url, timeout=180) as response:
            with archive_path.open("wb") as output:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    output.write(chunk)

        print("Extracting Chroma ONNX model...")

        with tarfile.open(archive_path, mode="r:gz") as archive:
            archive.extractall(target_dir, filter="data")

        archive_path.unlink(missing_ok=True)
        print("Chroma ONNX model installed successfully.")
        break

    except Exception:
        archive_path.unlink(missing_ok=True)

        if attempt == 3:
            raise

        print("Download failed; retrying in 5 seconds...")
        time.sleep(5)
PY


# ── 阶段 3：生产镜像 ──────────────────────────────────────────────────────────
FROM base AS production

ARG APP_USER=echomind
ARG APP_UID=1000
ARG APP_HOME=/home/${APP_USER}

# 先创建运行用户（必须在 COPY --chown 之前）
RUN useradd -m -u ${APP_UID} ${APP_USER}

# 从依赖阶段复制已安装的包
COPY --from=dependencies /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=dependencies /usr/local/bin /usr/local/bin
# 复制预下载的 ONNX 模型缓存（使用 --chown 确保所有权正确）
COPY --from=dependencies --chown=${APP_USER}:${APP_USER} \
    ${APP_HOME}/.cache/chroma \
    ${APP_HOME}/.cache/chroma

# 复制应用代码
COPY --chown=${APP_USER}:${APP_USER} . .

# 创建必要目录
RUN mkdir -p /app/data/chroma /app/logs /app/config && \
    chown -R ${APP_USER}:${APP_USER} /app/data /app/logs /app/config

USER ${APP_USER}

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=5)"

CMD ["python", "-m", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]

# ── 阶段 4：开发镜像 ──────────────────────────────────────────────────────────
FROM dependencies AS development

COPY . .

RUN mkdir -p /app/data/chroma /app/logs /app/config /app/tests && \
    chmod -R 777 /app/data /app/logs

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
