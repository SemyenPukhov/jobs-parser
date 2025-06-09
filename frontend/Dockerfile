# Use node base image
FROM node:20-alpine as builder

# Set working directory
WORKDIR /app


ARG VITE_API_URL
ENV VITE_API_URL=$VITE_API_URL


# Install dependencies
COPY package.json package-lock.json ./
RUN npm ci --force

# Copy source code
COPY . .

# Build assets
RUN npm run build

# Final production image
FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]