# Используем стабильный образ Python
FROM python:3.11-slim

# Устанавливаем системные зависимости и Chrome без использования apt-key
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    unzip \
    curl \
    && wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /usr/share/keyrings/googlechrome-linux-keyring.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/googlechrome-linux-keyring.gpg] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update && apt-get install -y \
    google-chrome-stable \
    --no-install-recommends \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Устанавливаем рабочую директорию
WORKDIR /app

# Создаем не-root пользователя
RUN useradd -m botuser
USER botuser

# Копируем зависимости и устанавливаем их
COPY --chown=botuser:botuser requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Копируем все файлы проекта
COPY --chown=botuser:botuser . .

# Создаем необходимые директории
RUN mkdir -p logs data

# Запускаем бота
CMD ["python", "bot.py"]