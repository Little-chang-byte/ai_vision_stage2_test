FROM python:3.11-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 YOLO_AUTOINSTALL=false
# The existing YOLO weights run on CPU; avoid downloading unused CUDA libraries.
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "src.web_app:app", "--host", "0.0.0.0", "--port", "8000"]
