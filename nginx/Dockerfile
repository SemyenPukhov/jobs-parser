FROM nginx:alpine

# Копируем конфигурацию nginx
COPY nginx/conf.d/default.conf /etc/nginx/conf.d/default.conf

# Создаем директорию для статических файлов
RUN mkdir -p /usr/share/nginx/html

# Устанавливаем правильные права
RUN chown -R nginx:nginx /usr/share/nginx/html && \
    chmod -R 755 /usr/share/nginx/html

# Используем пользователя nginx
USER nginx

EXPOSE 80 443