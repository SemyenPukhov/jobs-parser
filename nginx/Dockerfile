# Stage 1: Build frontend
FROM node:20-alpine as frontend-builder

WORKDIR /app

# Copy frontend files
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --force

# Copy source code
COPY frontend/ ./

# Принимаем build arg и устанавливаем ENV ПЕРЕД сборкой
ARG VITE_API_URL
ENV VITE_API_URL=$VITE_API_URL

# Build with environment variable
RUN npm run build

# Stage 2: Nginx
FROM nginx:alpine

# Copy nginx config
COPY nginx/conf.d/default.conf /etc/nginx/conf.d/default.conf

# Copy built frontend from previous stage
COPY --from=frontend-builder /app/dist /usr/share/nginx/html

EXPOSE 80