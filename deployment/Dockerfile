FROM python:3.14-slim
WORKDIR /app
COPY requirements-laptop.txt ./
RUN pip install --no-cache-dir -r requirements-laptop.txt
ENV INCIDENTLAB_DISABLE_LLM=1 CUDA_VISIBLE_DEVICES=-1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
COPY incidentlab ./incidentlab
COPY web ./web
RUN useradd --uid 10001 --create-home incidentlab && mkdir -p artifacts data/processed && chown -R incidentlab:incidentlab /app
USER incidentlab
EXPOSE 8768
CMD ["python", "-m", "uvicorn", "incidentlab.research_server:app", "--host", "0.0.0.0", "--port", "8768", "--workers", "1"]
