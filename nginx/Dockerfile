FROM nginx:alpine

COPY nginx/conf.d/default.conf /etc/nginx/conf.d/default.conf

# Frontend files will be mounted via volume in docker-compose
VOLUME ["/usr/share/nginx/html"]

EXPOSE 80 443
CMD ["nginx", "-g", "daemon off;"]