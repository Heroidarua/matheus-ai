FROM searxng/searxng:latest

# Copia as configurações customizadas
COPY searxng/settings.yml /etc/searxng/settings.yml

# Instala nginx
RUN apt-get update && apt-get install -y nginx && rm -rf /var/lib/apt/lists/*

# Configuração do nginx (proxy para porta 8080)
RUN echo 'server { \n    listen 10000; \n    location / { \n        proxy_pass http://127.0.0.1:8080; \n        proxy_set_header Host $host; \n        proxy_set_header X-Real-IP $remote_addr; \n        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for; \n    } \n}' > /etc/nginx/sites-available/default

# Remove o site padrão
RUN rm -f /etc/nginx/sites-enabled/default && ln -s /etc/nginx/sites-available/default /etc/nginx/sites-enabled/default

# Inicia nginx + SearXNG
CMD ["sh", "-c", "nginx && python /usr/local/searxng/webapp.py"]
