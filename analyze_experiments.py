import csv
import os
import math
import matplotlib.pyplot as plt

# ---------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------
EXPERIMENT_FILE = "experiment_results.csv"
PUBLISHER_COUNTS_FILE = "publisher_counts.csv"
TEST_DURATION_SECONDS = 60
OUTPUT_DIR = "experiment_analysis"

os.makedirs(OUTPUT_DIR, exist_ok=True)


def read_csv(path):
    with open(path, "r", newline="", encoding="utf-8-sig") as file:
        return list(csv.DictReader(file))


def to_float(value):
    try:
        if value is None or str(value).strip() == "":
            return None
        return float(value)
    except (ValueError, TypeError):
        return None


def mean(values):
    return sum(values) / len(values) if values else None


def fmt(value, digits=3):
    return "" if value is None or (isinstance(value, float) and math.isnan(value)) else round(value, digits)


def main():
    if not os.path.exists(EXPERIMENT_FILE):
        raise FileNotFoundError(
            f"Cannot find {EXPERIMENT_FILE}. Put this script in the same folder."
        )

    rows = read_csv(EXPERIMENT_FILE)
    required = {"Run_ID", "QoS", "Machine_ID", "Sequence", "Latency_ms"}
    if not rows:
        raise ValueError(f"{EXPERIMENT_FILE} is empty.")
    missing = required - set(rows[0].keys())
    if missing:
        raise ValueError(
            "Experiment CSV is missing columns: " + ", ".join(sorted(missing))
        )

    # Keep only well-formed rows with the required values.
    clean_rows = []
    for row in rows:
        qos = to_float(row.get("QoS"))
        sequence = to_float(row.get("Sequence"))
        latency = to_float(row.get("Latency_ms"))
        if (
            row.get("Run_ID", "").strip()
            and row.get("Machine_ID", "").strip()
            and qos is not None
            and sequence is not None
            and latency is not None
        ):
            row["_qos"] = int(qos)
            row["_sequence"] = int(sequence)
            row["_latency"] = latency
            clean_rows.append(row)

    if not clean_rows:
        raise ValueError("No valid experiment rows were found in the CSV.")

    # Group rows by run, QoS, and machine.
    groups = {}
    for row in clean_rows:
        key = (row["Run_ID"], row["_qos"], row["Machine_ID"])
        groups.setdefault(key, []).append(row)

    per_machine = []
    for (run_id, qos, machine_id), part in sorted(groups.items()):
        unique_sequences = {
            row["_sequence"] for row in part
        }
        latencies = [row["_latency"] for row in part]
        unique_received = len(unique_sequences)
        raw_received = len(part)

        per_machine.append({
            "Run_ID": run_id,
            "QoS": qos,
            "Machine_ID": machine_id,
            "Raw_Deliveries_Received": raw_received,
            "Unique_Messages_Received": unique_received,
            "Duplicate_Deliveries": raw_received - unique_received,
            "Average_Latency_ms": fmt(mean(latencies)),
            "Maximum_Latency_ms": fmt(max(latencies) if latencies else None),
            "Minimum_Latency_ms": fmt(min(latencies) if latencies else None),
            "Test_Duration_s": TEST_DURATION_SECONDS,
            "Unique_Throughput_msg_per_s": fmt(unique_received / TEST_DURATION_SECONDS),
            "Raw_Throughput_msg_per_s": fmt(raw_received / TEST_DURATION_SECONDS),
            "Messages_Published": "",
            "Delivery_Rate_percent": "",
        })

    # Load actual publisher counts, if the file has been filled in.
    count_lookup = {}
    if os.path.exists(PUBLISHER_COUNTS_FILE):
        for row in read_csv(PUBLISHER_COUNTS_FILE):
            run_id = row.get("Run_ID", "").strip()
            qos = to_float(row.get("QoS"))
            machine_id = row.get("Machine_ID", "").strip()
            sent = to_float(row.get("Messages_Published"))
            if run_id and qos is not None and machine_id and sent is not None and sent > 0:
                count_lookup[(run_id, int(qos), machine_id)] = sent

    for result in per_machine:
        key = (result["Run_ID"], result["QoS"], result["Machine_ID"])
        sent = count_lookup.get(key)
        if sent is not None:
            result["Messages_Published"] = int(sent)
            result["Delivery_Rate_percent"] = fmt(
                result["Unique_Messages_Received"] / sent * 100
            )

    # Save per-machine CSV.
    per_machine_path = os.path.join(OUTPUT_DIR, "per_machine_results.csv")
    with open(per_machine_path, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(per_machine[0].keys()))
        writer.writeheader()
        writer.writerows(per_machine)

    # Aggregate by experiment run and QoS.
    summary = []
    for run_id, qos in sorted({(r["Run_ID"], r["QoS"]) for r in per_machine}):
        machine_results = [
            r for r in per_machine if r["Run_ID"] == run_id and r["QoS"] == qos
        ]
        source_rows = [
            r for r in clean_rows if r["Run_ID"] == run_id and r["_qos"] == qos
        ]
        raw_received = sum(r["Raw_Deliveries_Received"] for r in machine_results)
        unique_received = sum(r["Unique_Messages_Received"] for r in machine_results)
        duplicate_count = sum(r["Duplicate_Deliveries"] for r in machine_results)
        sent_values = [to_float(r["Messages_Published"]) for r in machine_results]
        sent_values = [v for v in sent_values if v is not None]
        total_sent = sum(sent_values) if sent_values else None
        delivery_rate = (
            unique_received / total_sent * 100
            if total_sent is not None and total_sent > 0
            else None
        )
        all_latencies = [r["_latency"] for r in source_rows]

        summary.append({
            "Run_ID": run_id,
            "QoS": qos,
            "Machines_Recorded": len({r["Machine_ID"] for r in machine_results}),
            "Raw_Deliveries_Received": raw_received,
            "Unique_Messages_Received": unique_received,
            "Duplicate_Deliveries": duplicate_count,
            "Messages_Published": "" if total_sent is None else int(total_sent),
            "Delivery_Rate_percent": fmt(delivery_rate),
            "Average_Latency_ms": fmt(mean(all_latencies)),
            "Maximum_Latency_ms": fmt(max(all_latencies) if all_latencies else None),
            "Minimum_Latency_ms": fmt(min(all_latencies) if all_latencies else None),
            "Test_Duration_s": TEST_DURATION_SECONDS,
            "Unique_Throughput_msg_per_s": fmt(unique_received / TEST_DURATION_SECONDS),
            "Raw_Throughput_msg_per_s": fmt(raw_received / TEST_DURATION_SECONDS),
        })

    summary_path = os.path.join(OUTPUT_DIR, "qos_comparison_summary.csv")
    with open(summary_path, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(summary[0].keys()))
        writer.writeheader()
        writer.writerows(summary)

    # Create graphs only if Matplotlib can be imported.
    def save_bar(column, title, ylabel, filename):
        values = []
        for result in summary:
            value = to_float(result.get(column))
            if value is not None:
                values.append((result["Run_ID"], result["QoS"], value))
        if not values:
            print(f"Skipped {filename}: no values available for {column}.")
            return
        labels = [f"QoS {qos}\n{run_id}" for run_id, qos, _ in values]
        heights = [value for _, _, value in values]
        plt.figure(figsize=(max(8, len(labels) * 1.2), 5))
        plt.bar(labels, heights)
        plt.title(title)
        plt.xlabel("Experiment")
        plt.ylabel(ylabel)
        plt.xticks(rotation=25, ha="right")
        plt.tight_layout()
        output_path = os.path.join(OUTPUT_DIR, filename)
        plt.savefig(output_path, dpi=200)
        plt.close()
        print("Saved graph:", output_path)

    save_bar(
        "Average_Latency_ms",
        "Average MQTT Message Latency by QoS",
        "Average latency (ms)",
        "average_latency_by_qos.png",
    )
    save_bar(
        "Maximum_Latency_ms",
        "Maximum MQTT Message Latency by QoS",
        "Maximum latency (ms)",
        "maximum_latency_by_qos.png",
    )
    save_bar(
        "Unique_Throughput_msg_per_s",
        "Unique Message Throughput by QoS",
        "Unique messages per second",
        "unique_throughput_by_qos.png",
    )
    save_bar(
        "Delivery_Rate_percent",
        "Message Delivery Success Rate by QoS",
        "Delivery rate (%)",
        "delivery_rate_by_qos.png",
    )

    print("\n===== ANALYSIS COMPLETE =====")
    print("Summary:", os.path.abspath(summary_path))
    print("Per-machine results:", os.path.abspath(per_machine_path))
    print("\nQoS comparison summary:")
    for row in summary:
        print(row)

    if not count_lookup:
        print(
            "\nNOTE: Delivery rates are blank because publisher_counts.csv is "
            "missing or has no valid sent counts. Enter actual publisher summary "
            "counts and run this script again."
        )


if __name__ == "__main__":
    main()