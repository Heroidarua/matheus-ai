FROM ollama/ollama:latest

EXPOSE 11434

# Iniciar servidor e puxar modelo em runtime
CMD ["sh", "-c", "ollama serve & sleep 5 && ollama pull llama3.2:1b && wait"]
