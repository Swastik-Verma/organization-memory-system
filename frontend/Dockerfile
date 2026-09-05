# Frontend Dockerfile — multi-stage build: npm build → nginx serve
# Build context is frontend/ directory only

# Stage 1: Build the React app
FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# Stage 2: Serve with nginx
FROM nginx:alpine

# Copy built static files
COPY --from=build /app/dist /usr/share/nginx/html

# Custom nginx config to handle SPA routing
# (without this, refreshing on /entities/xyz gives a 404)
RUN echo 'server { \
    listen 80; \
    root /usr/share/nginx/html; \
    index index.html; \
    location / { \
        try_files $uri $uri/ /index.html; \
    } \
}' > /etc/nginx/conf.d/default.conf

EXPOSE 80