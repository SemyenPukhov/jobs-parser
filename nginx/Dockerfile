### Stage 1: Build frontend
FROM node:20-alpine AS builder

WORKDIR /app
COPY ../frontend ./

RUN npm ci
RUN npm run build

### Stage 2: Serve with nginx
FROM nginx:alpine

COPY conf.d/default.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80 443
CMD ["nginx", "-g", "daemon off;"]
