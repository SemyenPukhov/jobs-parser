FROM nginx:alpine

# Копируем Nginx конфиг
COPY conf.d/default.conf /etc/nginx/conf.d/default.conf

# Копируем собранный фронтенд из build-контекста
COPY ../frontend/dist /usr/share/nginx/html

# Открываем порты
EXPOSE 80 443

# Запускаем nginx
CMD ["nginx", "-g", "daemon off;"]
