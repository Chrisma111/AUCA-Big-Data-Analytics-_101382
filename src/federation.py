"""
Bring data that lives in MongoDB / HBase into Spark DataFrames.

Each loader tries the LIVE store first; if it is not running it falls back to the
equivalent data derived from the Parquet files (clearly labelled "simulated"), so the
Spark notebooks always run. The label returned with the DataFrame is printed by the
notebooks and should be quoted honestly in the report.
"""
from pyspark.sql import functions as F, types as T
from config import (PROCESSED, MONGO_URI, MONGO_DB, HBASE_HOST, HBASE_PORT,
                    mongo_available, hbase_available)

PARQUET = PROCESSED / "parquet"

MONGO_USERS_SCHEMA = T.StructType([
    T.StructField("user_id", T.StringType()), T.StructField("country", T.StringType()),
    T.StructField("registration_ts", T.TimestampType()),
    T.StructField("orders", T.IntegerType()), T.StructField("total_spent", T.DoubleType()),
    T.StructField("avg_order_value", T.DoubleType()),
    T.StructField("first_purchase", T.TimestampType()), T.StructField("last_purchase", T.TimestampType())])

HBASE_ENGAGEMENT_SCHEMA = T.StructType([
    T.StructField("user_id", T.StringType()), T.StructField("sessions", T.IntegerType()),
    T.StructField("total_seconds", T.LongType()), T.StructField("total_page_views", T.LongType()),
    T.StructField("last_session_ts", T.TimestampType())])


def mongo_users_df(spark, force_simulated=False):
    """User profiles + embedded purchase_summary (MongoDB `users` collection)."""
    if not force_simulated and mongo_available():
        from pymongo import MongoClient
        db = MongoClient(MONGO_URI)[MONGO_DB]
        rows = []
        for d in db.users.find({}, {"user_id": 1, "geo_data.country": 1, "registration_date": 1, "purchase_summary": 1}):
            ps = d.get("purchase_summary") or {}
            rows.append((d["user_id"], (d.get("geo_data") or {}).get("country"), d.get("registration_date"),
                         int(ps.get("orders", 0)), float(ps.get("total_spent", 0.0)), float(ps.get("avg_order_value", 0.0)),
                         ps.get("first_purchase"), ps.get("last_purchase")))
        return spark.createDataFrame(rows, MONGO_USERS_SCHEMA), "MongoDB (LIVE: users collection)"
    users = spark.read.parquet(str(PARQUET / "users"))
    t = (spark.read.parquet(str(PARQUET / "transactions")).filter("is_valid").groupBy("user_id")
         .agg(F.count("*").cast("int").alias("orders"), F.round(F.sum("total"), 2).alias("total_spent"),
              F.min("txn_ts").alias("first_purchase"), F.max("txn_ts").alias("last_purchase"))
         .withColumn("avg_order_value", F.round(F.col("total_spent") / F.col("orders"), 2)))
    df = (users.join(t, "user_id", "left")
          .select("user_id", "country", "registration_ts",
                  F.coalesce("orders", F.lit(0)).alias("orders"), F.coalesce("total_spent", F.lit(0.0)).alias("total_spent"),
                  F.coalesce("avg_order_value", F.lit(0.0)).alias("avg_order_value"), "first_purchase", "last_purchase"))
    return spark.createDataFrame(df.rdd, MONGO_USERS_SCHEMA), "Parquet (SIMULATED MongoDB users)"


def hbase_engagement_df(spark, force_simulated=False):
    """Per-user engagement aggregated from the HBase `user_sessions` table.
    Only the small `meta` family is scanned (column pruning) - never the heavy `pv` family."""
    if not force_simulated and hbase_available():
        import happybase
        from datetime import datetime
        conn = happybase.Connection(HBASE_HOST, HBASE_PORT, timeout=120000)
        table = conn.table("user_sessions")
        agg = {}
        cols = [b"meta:duration", b"meta:n_views", b"meta:start"]
        for key, data in table.scan(columns=cols, batch_size=5000):
            uid = key.split(b"#", 1)[0].decode()
            a = agg.setdefault(uid, [0, 0, 0, None])
            a[0] += 1
            a[1] += int(data.get(b"meta:duration", b"0") or 0)
            a[2] += int(data.get(b"meta:n_views", b"0") or 0)
            ts = datetime.fromisoformat(data[b"meta:start"].decode()) if data.get(b"meta:start") else None
            if ts and (a[3] is None or ts > a[3]):
                a[3] = ts
        conn.close()
        rows = [(u, v[0], v[1], v[2], v[3]) for u, v in agg.items()]
        return spark.createDataFrame(rows, HBASE_ENGAGEMENT_SCHEMA), "HBase (LIVE: user_sessions scan, meta family)"
    s = spark.read.parquet(str(PARQUET / "sessions"))
    df = (s.groupBy("user_id").agg(F.count("*").cast("int").alias("sessions"), F.sum("duration_seconds").cast("long").alias("total_seconds"),
                                   F.sum("n_page_views").cast("long").alias("total_page_views"), F.max("start_ts").alias("last_session_ts")))
    return spark.createDataFrame(df.rdd, HBASE_ENGAGEMENT_SCHEMA), "Parquet (SIMULATED HBase engagement)"
