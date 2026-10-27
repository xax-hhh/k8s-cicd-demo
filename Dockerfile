
FROM nginx:1.30.4

COPY index.html /usr/share/nginx/html/index.html

EXPOSE 80
