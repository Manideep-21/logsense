# Official Spark image + a user with id 1000 (same as your WSL user),
# so files Spark writes to ./warehouse belong to you, and Hadoop's login works.
FROM apache/spark:3.5.6
USER root
RUN groupadd -g 1000 logsense && useradd -u 1000 -g 1000 -m -d /home/logsense logsense
USER logsense
