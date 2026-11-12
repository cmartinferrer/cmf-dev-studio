FROM maven:3.9-eclipse-temurin-21
RUN groupadd --gid 10001 runner && useradd --uid 10001 --gid runner --create-home runner
COPY --chown=10001:10001 examples/java-maven /opt/studio-example
USER runner
ENV HOME=/home/runner MAVEN_CONFIG=/home/runner/.m2
WORKDIR /opt/studio-example
RUN mvn -B -Dmaven.repo.local=/home/runner/.m2/repository test && mvn -o -B -Dmaven.repo.local=/home/runner/.m2/repository test
WORKDIR /workspace
