FROM searxng/searxng:latest

# Copia as configurações customizadas
COPY searxng/settings.yml /etc/searxng/settings.yml

# Instala socat (Alpine usa apk, não apt-get)
RUN apk add --no-cache socat

# Inicia socat (10000 -> 8080) + SearXNG
CMD ["sh", "-c", "socat TCP-LISTEN:10000,fork,reuseaddr TCP:127.0.0.1:8080 & python /usr/local/searxng/webapp.py"]
