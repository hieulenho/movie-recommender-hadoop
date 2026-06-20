FROM maven:3.9.9-eclipse-temurin-17

WORKDIR /workspace

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 \
    && rm -rf /var/lib/apt/lists/*

COPY pom.xml ./
COPY src ./src
COPY scripts ./scripts
COPY tests/fixtures ./tests/fixtures

RUN mvn -B clean test package
RUN bash scripts/run_hadoop_smoke.sh
