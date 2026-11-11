FROM python:3.12-slim
RUN pip install --no-cache-dir pytest==8.4.2 fastapi==0.115.12 httpx==0.28.1 pydantic==2.11.7
RUN groupadd --gid 10001 runner && useradd --uid 10001 --gid runner --create-home runner
USER runner
WORKDIR /workspace
CMD ["python", "-m", "pytest", "-q", "-p", "no:cacheprovider"]
