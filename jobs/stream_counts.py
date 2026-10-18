"""Read HDFS log messages from Kafka and count them in 10-minute windows.

Run with: bash scripts/run_spark.sh                 Stage 3: print window counts to the console
          bash scripts/run_spark.sh --sink files    Stage 4: write Parquet files for Hive
Add --follow to keep running and wait for new messages (default: process what's in Kafka, then stop).

Tables (using the original 2008 log time):
  window_counts     one row per window: total_lines, warn_lines, blocks, anomalous_blocks
  component_counts  one row per window + component + level: lines
"""
import sys

from pyspark.sql import SparkSession, functions as F, types as T

KAFKA = "kafka:9092"
TOPIC = "hdfs-logs"
LABELS = "/data/input/anomaly_label.csv"
WAREHOUSE = "/data/warehouse"
WINDOW = "10 minutes"

sink = sys.argv[sys.argv.index("--sink") + 1] if "--sink" in sys.argv else "console"
follow = "--follow" in sys.argv

spark = (SparkSession.builder.appName(f"logsense-{sink}")
         .config("spark.sql.shuffle.partitions", "4")   # small data, few partitions
         .config("spark.sql.session.timeZone", "UTC")   # same clock as Hive
         .getOrCreate())
spark.sparkContext.setLogLevel("WARN")

schema = T.StructType([
    T.StructField("ts", T.StringType()),
    T.StructField("pid", T.IntegerType()),
    T.StructField("level", T.StringType()),
    T.StructField("component", T.StringType()),
    T.StructField("content", T.StringType()),
    T.StructField("block_ids", T.ArrayType(T.StringType())),
])


def read_logs():
    """Messages from Kafka, with the JSON text turned into columns."""
    return (spark.readStream.format("kafka")
            .option("kafka.bootstrap.servers", KAFKA)
            .option("subscribe", TOPIC)
            .option("startingOffsets", "earliest")
            .option("maxOffsetsPerTrigger", 50000)      # ~8 batches for the full replay
            .load()
            .select(F.from_json(F.col("value").cast("string"), schema).alias("m"))
            .select("m.*")
            .withColumn("event_time", F.to_timestamp("ts", "yyyy-MM-dd HH:mm:ss"))
            .withWatermark("event_time", "2 minutes"))  # logs arrive in time order


def window_counts(logs):
    # One row per (line, block). pos == 0 marks the line's first block, so each
    # line is still counted once even if it mentions several blocks.
    rows = logs.select("*", F.posexplode_outer("block_ids").alias("pos", "block_id"))

    # Add the Normal/Anomaly label for each block (a small, fixed table).
    labels = spark.read.option("header", True).csv(LABELS).withColumnRenamed("BlockId", "block_id")
    rows = rows.join(F.broadcast(labels), "block_id", "left")

    # First count per (window, block), then roll those up per window.
    # Doing it in two steps gives an exact number of distinct blocks.
    first = F.col("pos").isNull() | (F.col("pos") == 0)
    per_block = (rows.groupBy(F.window("event_time", WINDOW), "block_id")
                 .agg(F.sum(F.when(first, 1).otherwise(0)).alias("lines"),
                      F.sum(F.when(first & (F.col("level") == "WARN"), 1).otherwise(0)).alias("warns"),
                      F.max(F.col("Label") == "Anomaly").alias("is_anomaly")))

    return (per_block.groupBy(F.window(F.window_time("window"), WINDOW).alias("w"))
            .agg(F.sum("lines").alias("total_lines"),
                 F.sum("warns").alias("warn_lines"),
                 F.count("block_id").alias("blocks"),
                 F.sum(F.col("is_anomaly").cast("int")).alias("anomalous_blocks"))
            .select(F.col("w.start").alias("window_start"),
                    F.col("w.end").alias("window_end"),
                    "total_lines", "warn_lines", "blocks", "anomalous_blocks"))


def component_counts(logs):
    return (logs.groupBy(F.window("event_time", WINDOW).alias("w"), "component", "level")
            .agg(F.count("*").alias("lines"))
            .select(F.col("w.start").alias("window_start"),
                    F.col("w.end").alias("window_end"),
                    "component", "level", "lines"))


def start(writer):
    # outputMode append: a window is written once, after it is complete
    writer = writer.outputMode("append")
    return writer.start() if follow else writer.trigger(availableNow=True).start()


if sink == "console":
    queries = [start(window_counts(read_logs()).writeStream.format("console")
                     .option("truncate", False).option("numRows", 100))]
elif sink == "files":
    queries = []
    for name, df in [("window_counts", window_counts(read_logs())),
                     ("component_counts", component_counts(read_logs()))]:
        queries.append(start(
            df.coalesce(1).writeStream.format("parquet")       # one file per batch
            .option("path", f"{WAREHOUSE}/{name}")
            # the checkpoint remembers how far we've read, so a rerun only adds new data
            .option("checkpointLocation", f"{WAREHOUSE}/_checkpoints/{name}")))
else:
    sys.exit(f"unknown --sink {sink} (use console or files)")

for q in queries:
    q.awaitTermination()
    print(f"query {q.name or q.id} finished")
