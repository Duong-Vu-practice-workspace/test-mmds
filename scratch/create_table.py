import psycopg2

def create_missing_table():
    try:
        conn = psycopg2.connect(
            host="localhost", port=5432, dbname="otto_recommender", 
            user="otto", password="otto123"
        )
        conn.autocommit = True
        with conn.cursor() as cur:
            print("Creating spark_metrics table...")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS spark_metrics (
                    id SERIAL PRIMARY KEY,
                    query_name VARCHAR(50),
                    input_rows_per_second FLOAT,
                    processed_rows_per_second FLOAT,
                    batch_duration_ms BIGINT,
                    num_input_rows BIGINT,
                    timestamp TIMESTAMP DEFAULT NOW()
                );
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_spark_metrics_time ON spark_metrics(timestamp DESC);")
            print("Table created successfully.")
        conn.close()
    except Exception as e:
        print(f"Error creating table: {e}")

if __name__ == "__main__":
    create_missing_table()
