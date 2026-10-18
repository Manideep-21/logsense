"""Make a smaller HDFS log by keeping every line of ~1 in N blocks.

Usage: python scripts/make_subset.py <HDFS.log> <anomaly_label.csv> <out_dir> [N]

Writes <out_dir>/hdfs_subset.log and <out_dir>/anomaly_label.csv (labels for
the kept blocks only). Lines stay in their original (time) order.
"""
import re
import sys
import zlib

BLOCK_RE = re.compile(r"blk_-?\d+")


def keep(block_id, n):
    # crc32 gives the same answer on every run, so the subset is repeatable
    return zlib.crc32(block_id.encode()) % n == 0


def main():
    log_path, label_path, out_dir = sys.argv[1:4]
    n = int(sys.argv[4]) if len(sys.argv) > 4 else 28

    kept_lines = 0
    kept_blocks = set()
    with open(log_path, encoding="utf-8", errors="replace") as src, \
            open(f"{out_dir}/hdfs_subset.log", "w", encoding="utf-8") as dst:
        for line in src:
            chosen = [b for b in BLOCK_RE.findall(line) if keep(b, n)]
            if chosen:
                dst.write(line)
                kept_lines += 1
                kept_blocks.update(chosen)

    anomalies = 0
    with open(label_path, encoding="utf-8") as src, \
            open(f"{out_dir}/anomaly_label.csv", "w", encoding="utf-8") as dst:
        dst.write(src.readline())  # header
        for row in src:
            if row.split(",", 1)[0] in kept_blocks:
                dst.write(row)
                anomalies += row.strip().endswith("Anomaly")

    print(f"kept {kept_lines} lines, {len(kept_blocks)} blocks, {anomalies} anomalous blocks")


if __name__ == "__main__":
    main()
