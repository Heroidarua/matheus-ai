FROM ollama/ollama:latest

# Puxar modelo pequeno (3B, roda em CPU)
RUN ollama pull llama3.2:3b

EXPOSE 11434

CMD ["ollama", "serve"]
