FROM node:22-alpine AS build
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM alpine:3.23 AS web
RUN apk add --no-cache nginx nginx-mod-http-brotli gettext \
    && rm -f /etc/nginx/http.d/default.conf \
    && mkdir -p /run/nginx /var/lib/nginx/tmp /usr/share/nginx/html /usr/share/nginx/static /etc/nginx/snippets \
    && chown -R nginx:nginx /run/nginx /var/lib/nginx /usr/share/nginx
COPY frontend/nginx.conf /etc/nginx/nginx.conf
COPY frontend/default.conf.template /etc/nginx/http.d/default.conf.template
COPY frontend/security-headers.conf /etc/nginx/snippets/security-headers.conf
COPY frontend/nginx-entrypoint.sh /usr/local/bin/nginx-entrypoint.sh
COPY --from=build --chown=nginx:nginx /web/dist/ /usr/share/nginx/html/
RUN chmod 755 /usr/local/bin/nginx-entrypoint.sh
USER nginx
EXPOSE 8080
ENTRYPOINT ["/usr/local/bin/nginx-entrypoint.sh"]
CMD ["nginx", "-g", "daemon off;"]
