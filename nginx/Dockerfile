FROM nginx:alpine

# ✅ Правильный путь
COPY nginx/conf.d/default.conf /etc/nginx/conf.d/default.conf

# ✅ Фронтенд
COPY frontend/dist /usr/share/nginx/html

EXPOSE 80