# Build stage
FROM node:20-slim as build

WORKDIR /app

ARG VITE_API_URL

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm install --force

# Copy the rest of the application
COPY . .

# Build the application, ensuring VITE_API_URL is passed
RUN VITE_API_URL=${VITE_API_URL} npm run build

# Production stage
FROM nginx:alpine

# Copy built assets from build stage
COPY --from=build /app/dist /usr/share/nginx/html

# Expose port
EXPOSE 80

# Start nginx
CMD ["nginx", "-g", "daemon off;"] 