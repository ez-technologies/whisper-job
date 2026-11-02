# One candidate model in the job's image, for timing and sizes. Build context: the model's directory plus transcribe.py.
FROM whisper-bench:libs
COPY transcribe.py /transcribe.py
COPY model /model/general
ENV HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
USER 65532
ENTRYPOINT ["python", "/transcribe.py"]
