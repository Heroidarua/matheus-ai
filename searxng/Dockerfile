FROM searxng/searxng:latest

# Copia as configurações customizadas
COPY searxng/settings.yml /etc/searxng/settings.yml

# Força o SearXNG a escutar na porta 10000 (Render)
ENV PORT=10000
ENV SEARXNG_SERVER_PORT=10000

# Usa o entrypoint oficial da imagem
ENTRYPOINT ["/usr/local/bin/searxng-entrypoint.sh"]
CMD ["--port", "10000"]
