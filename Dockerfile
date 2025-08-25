# Dockerfile - Optimizado para Google Cloud

FROM python:3.12-slim

# Instalar dependencias del sistema necesarias para psycopg2 y otras librerías
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Establece el directorio de trabajo
WORKDIR /app

# Copia e instala dependencias primero (mejor cache de Docker)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia las credenciales (solo para desarrollo - en producción no es necesario)
# COPY gcp-credentials.json .

# Copia el resto del código
COPY . .

# Crea un usuario no-root para mayor seguridad
RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app
USER app

# Expone el puerto
EXPOSE 8000

# Comando optimizado para producción
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]