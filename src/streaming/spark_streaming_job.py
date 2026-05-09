"""
Spark Structured Streaming Job - OTTO Recommender Pipeline.
- Consumes from Kafka
- Aggregates stats by 1-minute window: PostgreSQL (stats_hourly)
- Real-time Funnel Analysis
- Detects anomalies (Bot traffic)
- Streaming Metrics Listener: PostgreSQL (spark_metrics)
"""

import os
import logging
import json
import psycopg2
from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json, col, window, count, when, expr, lit, struct, to_json, approx_count_distinct
from pyspark.sql.types import StructType, StructField, LongType, StringType, TimestampType
from pyspark.sql.streaming import StreamingQueryListener

# --- Configuration ---
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:29092")
KAFKA_TOPIC = "user-events"
CHECKPOINT_LOCATION = "/tmp/spark-checkpoints/otto-streaming"

PG_URL = "jdbc:postgresql://localhost:5432/otto_recommender"
PG_PROPERTIES = {
    "user": "otto",
    "password": "otto123",
    "driver": "org.postgresql.Driver"
}

# Define Schema for OTTO events
schema = StructType([
    StructField("session_id", LongType(), True),
    StructField("aid", LongType(), True),
    StructField("type", StringType(), True),
    StructField("ts", LongType(), True)
])

# --- Metrics Listener ---
class MetricsListener(StreamingQueryListener):
    def onQueryStarted(self, event):
        print(f"Query started: {event.id}")

    def onQueryProgress(self, event):
        """Called whenever a batch completes."""
        progress = event.progress
        try:
            # Extract metrics from the progress object
            conn = psycopg2.connect(
                host="localhost", port=5432, dbname="otto_recommender", 
                user="otto", password="otto123"
            )
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO spark_metrics (
                        query_id, query_name, batch_id, 
                        input_rows_per_second, process_rows_per_second, batch_duration_ms
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        str(progress.id),
                        progress.name or "Unnamed Query",
                        progress.batchId,
                        progress.inputRowsPerSecond,
                        progress.processedRowsPerSecond,
                        progress.durationMs.get("triggerExecution", 0)
                    )
                )
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error logging metrics: {e}")

    def onQueryTerminated(self, event):
        print(f"Query terminated: {event.id}")

def main():
    # 1. Initialize Spark Session
    spark = SparkSession.builder \
        .appName("OTTO-Streaming-Processor") \
        .config("spark.sql.streaming.checkpointLocation", CHECKPOINT_LOCATION) \
        .config("spark.jars.packages", "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0,org.postgresql:postgresql:42.7.1") \
        .getOrCreate()

    spark.sparkContext.setLogLevel("WARN")

    # 2. Add Metrics Listener
    spark.streams.addListener(MetricsListener())

    # Debug: Print Versions
    print("=" * 40)
    print(f"DEBUG: Spark Version: {spark.version}")
    print("=" * 40)

    # 3. Read from Kafka
    raw_df = spark.readStream \
        .format("kafka") \
        .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP_SERVERS) \
        .option("subscribe", KAFKA_TOPIC) \
        .option("startingOffsets", "latest") \
        .load()

    # 4. Parse JSON and Convert Timestamp
    events_df = raw_df.selectExpr("CAST(value AS STRING)") \
        .select(from_json(col("value"), schema).alias("data")) \
        .select("data.*") \
        .withColumn("timestamp", (col("ts") / 1000).cast(TimestampType())) \
        .withWatermark("timestamp", "2 minutes")

    # --- PIPELINE A: Global Stats Aggregation (Real-time Funnel) ---
    stats_df = events_df \
        .groupBy(window(col("timestamp"), "1 minute")) \
        .agg(
            count("*").alias("total_events"),
            approx_count_distinct("session_id").alias("total_sessions"),
            approx_count_distinct(when(col("type") == "clicks", col("session_id"))).alias("sessions_with_clicks"),
            approx_count_distinct(when(col("type") == "carts", col("session_id"))).alias("sessions_with_carts"),
            approx_count_distinct(when(col("type") == "orders", col("session_id"))).alias("sessions_with_orders"),
            approx_count_distinct("aid").alias("unique_items")
        ) \
        .select(
            col("window.start").alias("window_start"),
            col("window.end").alias("window_end"),
            "total_events",
            "total_sessions",
            "sessions_with_clicks",
            "sessions_with_carts",
            "sessions_with_orders",
            "unique_items"
        )

    # --- PIPELINE B: Anomaly Detection (Bot Traffic) ---
    anomalies_df = events_df \
        .groupBy(window(col("timestamp"), "1 minute"), "session_id") \
        .count() \
        .filter("count > 50") \
        .select(
            col("session_id"),
            lit("BOT_TRAFFIC").alias("anomaly_type"),
            to_json(struct(col("count").alias("event_count_per_min"))).alias("details"),
            col("window.start").alias("detected_at")
        )

    # 5. Write to PostgreSQL using foreachBatch
    def write_all_to_postgres(batch_df, batch_id, table_name):
        if table_name == "stats_hourly":
            batch_df = batch_df.withColumnRenamed("total_sessions", "unique_sessions") \
                               .withColumnRenamed("sessions_with_clicks", "total_clicks") \
                               .withColumnRenamed("sessions_with_carts", "total_carts") \
                               .withColumnRenamed("sessions_with_orders", "total_orders")
        
        batch_df.write \
            .jdbc(url=PG_URL, table=table_name, mode="append", properties=PG_PROPERTIES)

    # Start Streams
    query_stats = stats_df.writeStream \
        .outputMode("update") \
        .queryName("Global-Stats-Query") \
        .foreachBatch(lambda df, epoch_id: write_all_to_postgres(df, epoch_id, "stats_hourly")) \
        .start()

    query_anomalies = anomalies_df.writeStream \
        .outputMode("update") \
        .queryName("Anomaly-Detection-Query") \
        .foreachBatch(lambda df, epoch_id: write_all_to_postgres(df, epoch_id, "anomaly_logs")) \
        .start()

    print(f"Spark Streaming Job with Metrics Listener started.")
    spark.streams.awaitAnyTermination()

if __name__ == "__main__":
    main()
