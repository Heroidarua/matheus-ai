#!/bin/sh

# Iniciar ollama serve em background
ollama serve &

# Aguardar servidor iniciar
sleep 5

# Puxar modelo (se ainda não existir)
ollama pull llama3.2:1b

# Manter container rodando
wait
