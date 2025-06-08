FROM nginx:alpine

# Copy the built frontend files
COPY --from=frontend /usr/share/nginx/html /usr/share/nginx/html

# Copy nginx configuration
COPY conf.d/default.conf /etc/nginx/conf.d/default.conf

# Expose ports
EXPOSE 80 443

# Start nginx
CMD ["nginx", "-g", "daemon off;"] 