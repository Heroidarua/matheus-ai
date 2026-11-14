FROM ollama/ollama:latest

EXPOSE 11434

# Iniciar servidor e puxar modelo TINY em runtime (cabe em 512MB RAM)
ENTRYPOINT ["/bin/sh", "-c"]
CMD ["ollama serve & sleep 5 && ollama pull llama3.2:1b && wait"]
