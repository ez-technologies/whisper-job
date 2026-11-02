# Only for generating test audio. Never part of the job's image.
FROM python:3.12-slim
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch==2.8.0 \
 && pip install --no-cache-dir transformers==4.57.1 numpy==2.3.5 av==16.0.1 accelerate==1.11.0
