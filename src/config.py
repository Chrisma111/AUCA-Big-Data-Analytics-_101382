"""
Shared configuration and helpers used by every notebook.

Every notebook starts with:
    import sys; sys.path.append("../src")
    from config import *
"""
import os
import sys
import time
from contextlib import contextmanager
from pathlib import Path

# ----------------------------------------------------------------------------
# Paths (all relative to the project root, so the repo works on any machine)
# ----------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"              # JSON produced by the generator
PROCESSED = ROOT / "data" / "processed"  # NDJSON + Parquet produced by Spark
FIG = ROOT / "outputs" / "figures"       # PNG charts for the report
TAB = ROOT / "outputs" / "tables"        # CSV result tables (feed the charts)
for _p in (RAW, PROCESSED, FIG, TAB):
    _p.mkdir(parents=True, exist_ok=True)

# ----------------------------------------------------------------------------
# Connection settings (override with environment variables if needed)
# ----------------------------------------------------------------------------
SCALE = os.environ.get("SCALE", "medium")          # small | medium | full
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.environ.get("MONGO_DB", "ecommerce")
HBASE_HOST = os.environ.get("HBASE_HOST", "localhost")
HBASE_PORT = int(os.environ.get("HBASE_PORT", 9090))


@contextmanager
def timer(label: str):
    """Tiny stopwatch used to document performance in the report."""
    t0 = time.perf_counter()
    yield
    print(f"[timer] {label}: {time.perf_counter() - t0:,.2f}s")


def get_spark(app_name: str = "ecommerce-analytics", driver_memory: str = None,
              shuffle_partitions: int = 16):
    """
    One place to build the local SparkSession.
    - local[*]            : use every CPU core on this machine
    - shuffle partitions  : the default (200) is far too many for one laptop
    - AQE                 : adaptive query execution coalesces small shuffles
    - UTC session timezone: makes timestamps reproducible on any machine
    """
    from pyspark.sql import SparkSession
    # Windows only: Spark needs Hadoop's winutils.exe + hadoop.dll to write files (Parquet).
    # They are shipped in tools/hadoop/bin; point HADOOP_HOME there and put bin/ on PATH.
    hadoop_home = ROOT / "tools" / "hadoop"
    if os.name == "nt" and (hadoop_home / "bin" / "winutils.exe").exists():
        os.environ["HADOOP_HOME"] = str(hadoop_home)
        os.environ["hadoop.home.dir"] = str(hadoop_home)
        if str(hadoop_home / "bin") not in os.environ.get("PATH", ""):
            os.environ["PATH"] = str(hadoop_home / "bin") + os.pathsep + os.environ.get("PATH", "")
    # Isolate this project from any system-wide Spark/Hadoop install:
    #  - SPARK_HOME pointing to another Spark version -> Py4JJavaError (version mismatch)
    #  - HADOOP_CONF_DIR / SPARK_CONF_DIR with fs.defaultFS=hdfs://localhost:9000 -> "Connection refused"
    for var in ("SPARK_HOME", "SPARK_CONF_DIR", "HADOOP_CONF_DIR", "YARN_CONF_DIR"):
        os.environ.pop(var, None)
    os.environ["PYSPARK_PYTHON"] = sys.executable
    os.environ["PYSPARK_DRIVER_PYTHON"] = sys.executable
    os.environ.setdefault("PYSPARK_DRIVER_PYTHON", sys.executable)
    spark = (
        SparkSession.builder.master("local[*]").appName(app_name)
        .config("spark.driver.memory", driver_memory or os.environ.get("SPARK_DRIVER_MEMORY", "4g"))
        .config("spark.sql.shuffle.partitions", shuffle_partitions)
        .config("spark.hadoop.fs.defaultFS", "file:///")   # paths = local disk, never HDFS
        .config("spark.sql.adaptive.enabled", "true")
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.sql.ansi.enabled", "false")      # same null-on-bad-cast behaviour in Spark 3.5 and 4.x
        .config("spark.ui.showConsoleProgress", "false")
        .config("spark.driver.extraJavaOptions",
                f"-Dhadoop.home.dir={hadoop_home}" if os.name == "nt" else "")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("ERROR")
    if not spark.version.startswith("4.0"):
        print(f"WARNING: running Spark {spark.version}, expected the venv's PySpark - restart the kernel")
    return spark


def mongo_available(timeout_ms: int = 1500) -> bool:
    """True if a MongoDB server answers on MONGO_URI."""
    try:
        from pymongo import MongoClient
        MongoClient(MONGO_URI, serverSelectionTimeoutMS=timeout_ms).admin.command("ping")
        return True
    except Exception:
        return False


def hbase_available(timeout_ms: int = 3000) -> bool:
    """True if the HBase Thrift server answers on HBASE_HOST:HBASE_PORT."""
    try:
        import happybase
        conn = happybase.Connection(HBASE_HOST, HBASE_PORT, timeout=timeout_ms)
        conn.tables()
        conn.close()
        return True
    except Exception:
        return False
