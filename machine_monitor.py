
import json
import time
import csv
import os
from datetime import datetime

import paho.mqtt.client as mqtt

from experiment_config import (
    BROKER,
    PORT,
    RUN_ID,
    QOS_LEVEL,
    EXPECTED_MACHINES,
    MONITOR_TOPIC,
)

# ==============================
# MONITORING CONFIGURATION
# ==============================

FAULT_THRESHOLD = 80.0
OFFLINE_TIMEOUT = 6.0
CHECK_INTERVAL = 1.0

# New file dedicated to experiment data.
CSV_FILE = "experiment_results.csv"

CSV_COLUMNS = [
    "Run_ID",
    "QoS",
    "Receive_Time",
    "Machine_ID",
    "Sequence",
    "Temperature_C",
    "Status",
    "Latency_ms",
    "MQTT_Topic",
    "Delivered_QoS",
]

# ==============================
# CSV SETUP
# ==============================

file_exists = (
    os.path.exists(CSV_FILE)
    and os.path.getsize(CSV_FILE) > 0
)

csv_file = open(
    CSV_FILE,
    "a",
    newline="",
    encoding="utf-8"
)

csv_writer = csv.DictWriter(
    csv_file,
    fieldnames=CSV_COLUMNS
)

if not file_exists:
    csv_writer.writeheader()
    csv_file.flush()

# ==============================
# TRACKING VARIABLES
# ==============================

last_seen = {}
offline = {}

total_messages = 0
machine_message_counts = {
    machine_id: 0
    for machine_id in EXPECTED_MACHINES
}

received_sequences = {
    machine_id: set()
    for machine_id in EXPECTED_MACHINES
}

duplicate_messages = {
    machine_id: 0
    for machine_id in EXPECTED_MACHINES
}

latencies = []

monitor_start_time = time.monotonic()
experiment_start_time = None


# ==============================
# MQTT CONNECTION CALLBACK
# ==============================

def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code.is_failure:
        print("Connection failed:", reason_code)
        return

    # Subscribe at QoS 2 for all experiment levels.
    # The broker still delivers according to the
    # publisher's QoS and subscription QoS.
    client.subscribe(MONITOR_TOPIC, qos=2)

    print("\n===================================")
    print(" MQTT INDUSTRIAL MACHINE MONITOR")
    print("===================================")
    print("Connected to Mosquitto.")
    print("Experiment ID:", RUN_ID)
    print("Configured QoS:", QOS_LEVEL)
    print("Monitoring topic:", MONITOR_TOPIC)
    print("Fault threshold:", FAULT_THRESHOLD, "C")
    print("Offline timeout:", OFFLINE_TIMEOUT, "seconds")
    print("Experiment CSV:", os.path.abspath(CSV_FILE))
    print("Waiting for experiment messages...")


# ==============================
# MESSAGE CALLBACK
# ==============================

def on_message(client, userdata, message):
    global total_messages, experiment_start_time

    try:
        payload = message.payload.decode("utf-8")
        data = json.loads(payload)

        # Ignore messages belonging to another experiment.
        message_run_id = data.get("run_id")

        if message_run_id != RUN_ID:
            return

        machine_id = data["machine_id"]
        temperature = float(data["temperature"])
        status = data["status"]
        send_timestamp = float(data["timestamp"])
        sequence = data.get("sequence")
        message_qos = data.get("qos", message.qos)

        if machine_id not in EXPECTED_MACHINES:
            print("Unknown machine:", machine_id)
            return

        if experiment_start_time is None:
            experiment_start_time = time.monotonic()

        # Count every valid delivery.
        total_messages += 1
        machine_message_counts[machine_id] += 1

        # Count unique sequence numbers separately.
        is_duplicate = False

        if sequence is not None:
            sequence = int(sequence)

            if sequence in received_sequences[machine_id]:
                duplicate_messages[machine_id] += 1
                is_duplicate = True
            else:
                received_sequences[machine_id].add(sequence)

        # Approximate one-way latency.
        receive_timestamp = time.time()
        latency_ms = (
            receive_timestamp - send_timestamp
        ) * 1000

        latencies.append(latency_ms)

        # Update machine communication state.
        last_seen[machine_id] = time.monotonic()

        if offline.get(machine_id, False):
            print(
                "\nRECOVERY ALERT:",
                machine_id,
                "is communicating again."
            )

        offline[machine_id] = False

        receive_time_text = datetime.fromtimestamp(
            receive_timestamp
        ).strftime("%Y-%m-%d %H:%M:%S.%f")

        # Save experiment data.
        csv_writer.writerow({
            "Run_ID": RUN_ID,
            "QoS": QOS_LEVEL,
            "Receive_Time": receive_time_text,
            "Machine_ID": machine_id,
            "Sequence": sequence,
            "Temperature_C": temperature,
            "Status": status,
            "Latency_ms": round(latency_ms, 3),
            "MQTT_Topic": message.topic,
            "Delivered_QoS": message.qos,
        })

        csv_file.flush()

        print("\n------------------------------")
        print("Run ID:", RUN_ID)
        print("Machine:", machine_id)
        print("Sequence:", sequence)
        print("Published QoS:", message_qos)
        print("Delivered QoS:", message.qos)
        print("Temperature:", temperature, "C")
        print("Status:", status)
        print("Latency:", round(latency_ms, 3), "ms")

        if is_duplicate:
            print("Duplicate delivery detected.")

        # Fault detection.
        if temperature >= FAULT_THRESHOLD or status != "RUNNING":
            print("!!! FAULT ALERT !!!")
            print("Machine", machine_id, "requires attention.")
        else:
            print("Machine condition: NORMAL")

    except (ValueError, KeyError, TypeError) as error:
        print("Could not process message:", error)

    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        print("Invalid message payload:", error)


# ==============================
# MQTT CLIENT
# ==============================

client = mqtt.Client(
    mqtt.CallbackAPIVersion.VERSION2,
    client_id=f"industrial_monitor_{RUN_ID}"
)

client.on_connect = on_connect
client.on_message = on_message

print("Starting machine monitor...")

try:
    client.connect(BROKER, PORT, 60)
    client.loop_start()

    # Detect machines that stop communicating.
    while True:
        now = time.monotonic()

        for machine_id in EXPECTED_MACHINES:
            if machine_id in last_seen:
                elapsed = now - last_seen[machine_id]
            else:
                elapsed = now - monitor_start_time

            if elapsed >= OFFLINE_TIMEOUT:
                if not offline.get(machine_id, False):
                    offline[machine_id] = True

                    print(
                        "\n!!! OFFLINE ALERT !!!",
                        "Machine", machine_id,
                        "has not sent a message for",
                        round(elapsed, 1),
                        "seconds."
                    )

        time.sleep(CHECK_INTERVAL)

except KeyboardInterrupt:
    print("\nStopping monitor...")

except (OSError, ValueError) as error:
    print("Monitor error:", error)

finally:
    client.disconnect()
    client.loop_stop()

    elapsed_time = time.monotonic() - monitor_start_time

    raw_throughput = (
        total_messages / elapsed_time
        if elapsed_time > 0 else 0
    )

    unique_total = sum(
        len(received_sequences[machine_id])
        for machine_id in EXPECTED_MACHINES
    )

    unique_throughput = (
        unique_total / elapsed_time
        if elapsed_time > 0 else 0
    )

    print("\n===== MQTT EXPERIMENT SUMMARY =====")
    print("Experiment ID:", RUN_ID)
    print("Configured QoS:", QOS_LEVEL)
    print("Monitor duration:", round(elapsed_time, 2), "seconds")
    print("Total deliveries received:", total_messages)
    print("Unique messages received:", unique_total)
    print("Raw throughput:", round(raw_throughput, 3), "messages/sec")
    print("Unique throughput:", round(unique_throughput, 3), "messages/sec")

    if latencies:
        print("Average latency:", round(sum(latencies) / len(latencies), 3), "ms")
        print("Minimum latency:", round(min(latencies), 3), "ms")
        print("Maximum latency:", round(max(latencies), 3), "ms")

    print("\n===== PER-MACHINE RESULTS =====")

    for machine_id in EXPECTED_MACHINES:
        print("\nMachine:", machine_id)
        print("All deliveries:", machine_message_counts[machine_id])
        print("Unique sequences:", len(received_sequences[machine_id]))
        print("Duplicate deliveries:", duplicate_messages[machine_id])

    print("\nDelivery success rate: NOT CALCULATED YET")
    print("Reason: publisher sent counts must be recorded")
    print("and matched to this experiment's run ID.")

    csv_file.close()

    print("\nExperiment data saved to:", os.path.abspath(CSV_FILE))
    print("Monitor stopped.")
