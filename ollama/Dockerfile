FROM ollama/ollama:latest

EXPOSE 11434

# Usar ENTRYPOINT para sobrescrever o entrypoint padrão da imagem
ENTRYPOINT ["/bin/sh", "-c"]
CMD ["ollama serve & sleep 5 && ollama pull llama3.2:1b && wait"]
