FROM nginx:alpine

COPY nginx/conf.d/default.conf /etc/nginx/conf.d/default.conf

COPY --from=builder /app/frontend/dist /usr/share/nginx/html

EXPOSE 80 443
CMD ["nginx", "-g", "daemon off;"]