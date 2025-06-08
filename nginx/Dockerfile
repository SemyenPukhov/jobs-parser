### Stage 1: Build frontend
FROM node:20-alpine AS builder

WORKDIR /app
COPY frontend ./frontend
WORKDIR /app/frontend
RUN npm ci --legacy-peer-deps
RUN npm run build

### Stage 2: NGINX
FROM nginx:alpine

COPY nginx/conf.d/default.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/frontend/dist /usr/share/nginx/html

EXPOSE 80 443
CMD ["nginx", "-g", "daemon off;"]
