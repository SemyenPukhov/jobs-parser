FROM nginx:alpine

# Копируем конфиг
COPY conf.d/default.conf /etc/nginx/conf.d/default.conf

# Копируем собранный фронтенд
COPY ../frontend/dist /usr/share/nginx/html

EXPOSE 80