FROM searxng/searxng:latest

# Copia as configurações customizadas
COPY settings.yml /etc/searxng/settings.yml

# Garante que a porta 8080 está exposta
EXPOSE 8080

# Comando padrão da imagem oficial
CMD ["python", "/usr/local/searxng/webapp.py"]
