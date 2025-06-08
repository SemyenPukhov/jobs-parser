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

# Create .env.production file with VITE_API_URL
RUN echo "VITE_API_URL=$VITE_API_URL" > .env.production

# Build the application
RUN npm run build

# Production stage - just copy the built files
FROM scratch

# Copy built assets from build stage
COPY --from=build /app/dist /usr/share/nginx/html 