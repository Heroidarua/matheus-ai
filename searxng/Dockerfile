FROM searxng/searxng:latest

COPY settings.yml /etc/searxng/settings.yml

EXPOSE 8080

CMD ["python", "/usr/local/searxng/webapp.py"]
