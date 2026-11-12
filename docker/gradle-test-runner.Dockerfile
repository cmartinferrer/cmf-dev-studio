FROM gradle:8.14-jdk21
USER root
RUN groupadd --gid 10001 runner && useradd --uid 10001 --gid runner --create-home runner
USER runner
WORKDIR /workspace
