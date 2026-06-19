# Hadoop Maven Environment

## Purpose

Milestone 3 establishes the Java and Maven foundation for future Hadoop MapReduce recommender jobs. It adds a reproducible Maven project, a minimal Hadoop local-mode smoke job, Java tests, run scripts, and an optional Docker validation path.

The smoke job is only an environment check. It is not part of the recommender algorithm.

## Requirements

- Java 17 for compiling and running the Maven project.
- Maven for dependency resolution, compilation, tests, packaging, and local smoke execution.
- Apache Hadoop `3.5.0` as the project Hadoop dependency version.
- Docker is optional and is used only for a lightweight Linux Maven validation environment.

## Maven Project Structure

```text
pom.xml
src/main/java/com/movierecommender/smoke/LineCountJob.java
src/test/java/com/movierecommender/smoke/LineCountJobTest.java
tests/fixtures/hadoop-smoke/input.txt
```

The Maven build produces a normal JAR under `target/`. No fat JAR is required for this milestone.

## Local Mode

Hadoop local mode runs MapReduce in the current JVM using the local filesystem:

```text
mapreduce.framework.name=local
fs.defaultFS=file:///
```

Local mode is useful for smoke tests and small development fixtures. It is not pseudo-distributed mode, and it is not a real cluster.

Pseudo-distributed mode runs Hadoop daemons on one machine. A real cluster uses distributed HDFS and YARN services across machines. This milestone does not start HDFS or YARN because the goal is only to confirm that the Java build and MapReduce APIs work locally.

## Smoke Job

`LineCountJob` reads text input and emits:

```text
lineCount<TAB>N
```

where `N` is the number of input text records. The fixture `tests/fixtures/hadoop-smoke/input.txt` contains exactly five records, including one empty line. Hadoop `TextInputFormat` still creates a record for the empty line.

## Host Validation Commands

```powershell
java -version
javac -version
mvn -version
python --version
python -m unittest discover -s tests -p "test_*.py" -v
mvn clean test
mvn package
powershell -ExecutionPolicy Bypass -File scripts/run_hadoop_smoke.ps1
```

After a successful smoke run, inspect:

```powershell
Get-Content target/hadoop-smoke-output/part-r-00000
```

Expected logical content:

```text
lineCount	5
```

## Docker Validation

Docker validation uses a Maven image with Eclipse Temurin Java 17. It does not start Hadoop daemons and does not create a Docker Compose cluster.

```powershell
powershell -ExecutionPolicy Bypass -File scripts/test_hadoop_maven_docker.ps1
```

## Windows Notes

Do not download `winutils.exe`, do not add unofficial Hadoop binaries, and do not hard-code `HADOOP_HOME`. A harmless Hadoop native-library warning is different from a failed job or failed test. If local Hadoop execution fails on Windows because of platform-native behavior, preserve the real integration test and validate in the Docker Linux environment when available.

## Troubleshooting

- If `mvn` is missing, install or activate Maven outside this repository before running host validation.
- If `java -version` is not Java 17, use a Java 17 environment outside this repository.
- If the smoke output path already exists, the Java job fails by design. The provided scripts remove only the configured smoke output directory before running.
- If Docker cannot read local Docker configuration, fix local Docker permissions outside this repository.
- If dependency resolution fails, check network access and Maven Central availability outside this repository.

## Generated Files

Generated Maven and Hadoop smoke outputs are written under `target/`, which is ignored by Git. Generated result files remain ignored.

## Dataset Policy

The smoke job does not use Netflix data. No raw dataset is downloaded or committed in this milestone.

## Limitations

- No recommender-specific Hadoop job is implemented.
- No HDFS or YARN daemons are started.
- No pseudo-distributed, multi-node, or Docker Compose Hadoop cluster is configured.
- No train/test split or evaluation metric is implemented.
- No web interface or database is added.

The next milestone is Milestone 4: the user-history MapReduce job.
