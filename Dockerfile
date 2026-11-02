# Whisper as a one-shot job: starts, transcribes one file, prints JSON, exits.
FROM python:3.12-slim AS build
ARG MODEL=small
RUN pip install --no-cache-dir --prefix=/install \
      faster-whisper==1.2.1 av==19.0.2 ctranslate2==4.8.4 onnxruntime==1.31.1 \
      requests==2.34.2 tokenizers==0.23.3 huggingface_hub==2.4.0 numpy==2.5.4 \
 && PYTHONPATH=/install/lib/python3.12/site-packages python -c "from huggingface_hub import snapshot_download as s; s('Systran/faster-whisper-${MODEL}', local_dir='/model', allow_patterns=['config.json','model.bin','tokenizer.json','vocabulary.*','preprocessor_config.json'])"

FROM python:3.12-slim
COPY --from=build /install /usr/local
COPY --from=build /model /model
COPY transcribe.py /transcribe.py
ENV HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
USER 65532
ENTRYPOINT ["python", "/transcribe.py"]
