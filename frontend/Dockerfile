# Stage 1: Build the application
FROM node:20-alpine AS builder

WORKDIR /app

ARG VITE_API_URL
ENV VITE_API_URL=$VITE_API_URL

# Install dependencies
COPY package*.json ./
RUN npm install --force
RUN npm install -g typescript
RUN npm install --force --save-dev autoprefixer
RUN npm install --force --save-dev @tailwindcss/postcss
RUN npm install --force --save-dev tailwindcss autoprefixer postcss



# Build the application
COPY . .
RUN npm run build

# Stage 2: Production image
FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]

