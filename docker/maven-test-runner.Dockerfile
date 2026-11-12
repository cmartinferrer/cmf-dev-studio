FROM maven:3.9-eclipse-temurin-21
RUN groupadd --gid 10001 runner && useradd --uid 10001 --gid runner --create-home runner
USER runner
WORKDIR /workspace
