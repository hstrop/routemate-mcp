FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml requirements.txt ./
COPY src ./src
COPY servers_config.example.json ./
RUN python -m pip install --no-cache-dir -e .

ENV PYTHONPATH=/app/src \
    ROUTEMATE_MODE=offline \
    ROUTEMATE_HOST=0.0.0.0 \
    ROUTEMATE_PORT=8000 \
    ROUTEMATE_OUTPUT_DIR=/app/runtime_output
RUN mkdir -p /app/runtime_output
VOLUME ["/app/runtime_output"]
EXPOSE 8000
CMD ["uvicorn", "routemate.api:app", "--host", "0.0.0.0", "--port", "8000"]
