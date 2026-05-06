from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json, col, expr, window, to_json, struct
from pyspark.sql.types import StructType, StructField, StringType, IntegerType, LongType
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_spark_session(app_name: str = "OTTO_Streaming") -> SparkSession:
    """Create Spark session with Kafka support."""
    return (
        SparkSession.builder
        .appName(app_name)
        .config("spark.jars.packages", "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0")
        .config("spark.sql.adaptive.enabled", "true")
        .config("spark.sql.adaptive.coalescePartitions.enabled", "true")
        .getOrCreate()
    )


def define_schema():
    """Define schema for user-events topic."""
    return StructType([
        StructField("session", StringType(), True),
        StructField("aid", IntegerType(), True),
        StructField("ts", LongType(), True),
        StructField("type", StringType(), True),
    ])


def main():
    spark = create_spark_session()

    logger.info("Starting Spark Structured Streaming job")
    logger.info(f"Spark version: {spark.version}")

    schema = define_schema()

    # Read from Kafka
    df = (
        spark.readStream
        .format("kafka")
        .option("kafka.bootstrap.servers", "kafka:9092")
        .option("subscribe", "user-events")
        .option("startingOffsets", "latest")
        .load()
    )

    # Parse Kafka messages
    parsed_df = (
        df.select(
            from_json(col("value").cast("string"), schema).alias("data"),
            col("timestamp").alias("kafka_timestamp")
        )
        .select("data.*", "kafka_timestamp")
    )

    # Add derived columns
    processed_df = (
        parsed_df
        .withColumn("event_time", expr("from_unixtime(ts/1000)"))
        .withColumn("hour_of_day", expr("hour(from_unixtime(ts/1000))"))
        .withColumn("day_of_week", expr("dayofweek(from_unixtime(ts/1000))"))
    )

    # Windowed aggregations
    windowed_counts = (
        processed_df
        .withWatermark("kafka_timestamp", "10 minutes")
        .groupBy(
            window(col("kafka_timestamp"), "1 minute"),
            col("type")
        )
        .count()
        .select(
            col("window.start").alias("window_start"),
            col("window.end").alias("window_end"),
            col("type"),
            col("count").alias("events_per_minute")
        )
    )

    # Write processed events to processed-events topic
    query1 = (
        processed_df
        .select(to_json(struct("*")).alias("value"))
        .writeStream
        .format("kafka")
        .option("kafka.bootstrap.servers", "kafka:9092")
        .option("topic", "processed-events")
        .option("checkpointLocation", "/tmp/checkpoint/processed-events")
        .start()
    )

    # Write windowed aggregations to console (or another sink)
    query2 = (
        windowed_counts
        .writeStream
        .outputMode("update")
        .format("console")
        .option("numRows", 20)
        .start()
    )

    logger.info("Streaming queries started. Waiting for termination...")

    try:
        query1.awaitAnyTermination()
    except KeyboardInterrupt:
        logger.info("Stopping streaming queries...")
        query1.stop()
        query2.stop()
        spark.stop()


if __name__ == "__main__":
    main()
