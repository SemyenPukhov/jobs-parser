# Build stage
FROM node:20-slim as build

WORKDIR /app

ARG VITE_API_URL
RUN echo "Building with VITE_API_URL: $VITE_API_URL"

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm install --force

# Copy the rest of the application
COPY . .

# Debug VITE_API_URL before build
RUN echo "VITE_API_URL in Dockerfile build: $VITE_API_URL"

# Create .env.production file with VITE_API_URL
RUN echo "VITE_API_URL=$VITE_API_URL" > .env.production
RUN echo "Contents of .env.production:"
RUN cat .env.production

# Build the application
RUN npm run build

# Debug built files
RUN echo "Contents of dist directory:"
RUN ls -la dist

# Production stage - just copy the built files
FROM nginx:alpine

# Copy built assets from build stage
COPY --from=build /app/dist /usr/share/nginx/html

# Debug copied files
RUN echo "Contents of nginx html directory:"
RUN ls -la /usr/share/nginx/html

# Expose port
EXPOSE 80 