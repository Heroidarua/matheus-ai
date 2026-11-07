FROM ollama/ollama:latest

EXPOSE 11434

# Script de entrada que inicia o servidor e puxa o modelo
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
