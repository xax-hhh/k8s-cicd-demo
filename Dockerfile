FROM nginx:1.30.4

RUN ln -sf /dev/stdout /var/log/nginx/access.log \
    && ln -sf /dev/stderr /var/log/nginx/error.log

COPY index.html /usr/share/nginx/html/index.html

EXPOSE 80