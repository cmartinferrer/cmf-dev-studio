FROM gradle:8.14-jdk21
USER root
RUN groupadd --gid 10001 runner && useradd --uid 10001 --gid runner --create-home runner
COPY --chown=10001:10001 examples/kotlin-gradle /opt/studio-example
USER runner
ENV HOME=/home/runner GRADLE_USER_HOME=/home/runner/.gradle
WORKDIR /opt/studio-example
RUN gradle --no-daemon test && gradle --offline --no-daemon clean test
WORKDIR /workspace
