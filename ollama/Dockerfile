FROM ollama/ollama:latest

# Iniciar ollama serve em background
RUN (ollama serve &) && sleep 3

# Puxar modelo pequeno (3B, roda em CPU)
RUN ollama pull llama3.2:3b

EXPOSE 11434

CMD ["ollama", "serve"]
