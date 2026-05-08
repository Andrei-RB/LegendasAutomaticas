FROM python:3.11-slim

# Evitar a geração de arquivos .pyc e não bufferizar os logs no console
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Definir diretório de trabalho
WORKDIR /app

# Instalar dependências do sistema operacional
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copiar os requerimentos e instalar dependências Python
COPY requirements.txt /app/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copiar o código fonte do projeto
COPY . /app/

# O container pode servir como múltiplos serviços (API, Worker, Frontend)
# O comando de execução (CMD) será especificado no docker-compose.yml
