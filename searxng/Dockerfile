FROM searxng/searxng:latest

# Define o diretório de trabalho como a pasta searxng
WORKDIR /app

# Copia as configurações customizadas para dentro da imagem
COPY searxng/settings.yml /etc/searxng/settings.yml

# A imagem oficial já tem o CMD padrão, não precisa redefinir
