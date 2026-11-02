# Whisper as a one-shot job: starts, transcribes one file, prints JSON, exits.
# The models are converted from their source weights to int8 here, which halves their size. Torch stays in this stage.
FROM python:3.12-slim AS models
ARG GENERAL_REPO=openai/whisper-large-v3-turbo
ARG GENERAL_REV=41f01f3fe87f28c78e2fbf8b568835947dd65ed9
ARG HEBREW_REPO=ivrit-ai/whisper-large-v3-turbo
ARG HEBREW_REV=f33172a8c3c6efbc040a7200e00835257cac0447
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch==2.8.0 \
 && pip install --no-cache-dir transformers==4.57.1 ctranslate2==4.8.4 numpy==2.3.5 huggingface_hub==0.36.2 \
 && convert() { python -c "from huggingface_hub import snapshot_download as s; s('$1', revision='$2', allow_patterns=['*.json', '*.txt', 'model.safetensors'])" \
      && ct2-transformers-converter --model "$1" --revision "$2" --output_dir "$3" --quantization int8 --copy_files tokenizer.json preprocessor_config.json \
      && rm -rf /root/.cache/huggingface; } \
 && convert "$GENERAL_REPO" "$GENERAL_REV" /model/general \
 && if [ -n "$HEBREW_REPO" ]; then convert "$HEBREW_REPO" "$HEBREW_REV" /model/he; fi

FROM python:3.12-slim AS libs
RUN pip install --no-cache-dir --prefix=/install \
      faster-whisper==1.2.1 av==19.0.2 ctranslate2==4.8.4 onnxruntime==1.31.1 \
      requests==2.34.2 tokenizers==0.23.3 huggingface_hub==2.4.0 numpy==2.5.4

FROM python:3.12-slim
COPY --from=libs /install /usr/local
COPY --from=models /model /model
COPY transcribe.py /transcribe.py
ENV HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
USER 65532
ENTRYPOINT ["python", "/transcribe.py"]
