#!/bin/sh

# Replace environment variables in the HTML file
envsubst '${VITE_API_URL}' < /usr/share/nginx/html/index.html > /usr/share/nginx/html/index.html.tmp
mv /usr/share/nginx/html/index.html.tmp /usr/share/nginx/html/index.html

# Start nginx
exec nginx -g 'daemon off;' 