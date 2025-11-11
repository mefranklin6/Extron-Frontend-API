FROM python:latest

COPY . /app
WORKDIR /app
CMD ["python", "port_instantiation_helper.py"]