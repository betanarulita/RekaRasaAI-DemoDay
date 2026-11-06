FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HOST=0.0.0.0 PORT=8000 APP_ENV=production DATABASE_PATH=/var/data/rekarasa.sqlite3
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py visual_content.py catalog_import.py governance_policy.py cloudflare_images.py comfy_workflows.py ./
COPY agent ./agent
COPY governance ./governance
COPY migrations ./migrations
COPY static ./static
COPY image ./image
EXPOSE 8000
CMD ["python", "-c", "from waitress import serve; import app, os; serve(app.application, host=os.getenv('HOST','0.0.0.0'), port=int(os.getenv('PORT','8000')), threads=4, channel_timeout=65)"]
