# Stage 1: Build frontend
FROM node:20-alpine as frontend-builder

WORKDIR /app

# Copy frontend files
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --force

COPY frontend/ ./
RUN npm run build

# Stage 2: Nginx
FROM nginx:alpine

# Copy nginx config
COPY nginx/conf.d/default.conf /etc/nginx/conf.d/default.conf

# Copy built frontend from previous stage
COPY --from=frontend-builder /app/dist /usr/share/nginx/html

EXPOSE 80