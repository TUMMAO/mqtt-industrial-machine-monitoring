
import json
import time
import csv
import os
from datetime import datetime
import paho.mqtt.client as mqtt

# MQTT configuration
BROKER = "127.0.0.1"
PORT = 1883
TOPIC = "factory/+/status"

# Monitoring configuration
FAULT_THRESHOLD = 80.0
OFFLINE_TIMEOUT = 6.0
CHECK_INTERVAL = 1.0
EXPECTED_MACHINES = ["M1", "M2"]

# CSV file for latency measurements
CSV_FILE = "latency_results.csv"

csv_file = open(CSV_FILE, "a", newline="", encoding="utf-8")
csv_writer = csv.writer(csv_file)

if os.path.getsize(CSV_FILE) == 0:
    csv_writer.writerow([
        "Receive_Time",
        "Machine_ID",
        "Temperature_C",
        "Status",
        "Latency_ms",
        "MQTT_Topic"
    ])
    csv_file.flush()

# Machine communication tracking
last_seen = {}
offline = {}

# Throughput tracking
total_messages = 0
machine_message_counts = {"M1": 0, "M2": 0}

# Unique message tracking using sequence numbers
received_sequences = {
    "M1": set(),
    "M2": set()
}

monitor_start_time = time.monotonic()


def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code.is_failure:
        print("Connection failed:", reason_code)
    else:
        client.subscribe(TOPIC, qos=1)
        print("Monitor connected to Mosquitto!")
        print("Monitoring topic:", TOPIC)
        print("Temperature threshold:", FAULT_THRESHOLD, "C")
        print("Offline timeout:", OFFLINE_TIMEOUT, "seconds")
        print("Latency measurement: ENABLED")
        print("Throughput measurement: ENABLED")
        print("Unique message counting: ENABLED")
        print("CSV file:", os.path.abspath(CSV_FILE))


def on_message(client, userdata, message):
    global total_messages

    try:
        payload = message.payload.decode("utf-8")
        data = json.loads(payload)

        machine_id = data["machine_id"]
        temperature = float(data["temperature"])
        status = data["status"]
        send_timestamp = float(data["timestamp"])

        if machine_id not in EXPECTED_MACHINES:
            print("Unknown machine:", machine_id)
            return

        # Read sequence number if supplied by the publisher
        sequence = data.get("sequence")

        # Count every valid message received for throughput
        total_messages += 1
        machine_message_counts[machine_id] += 1

        # Count unique sequence numbers when available
        if sequence is not None:
            received_sequences[machine_id].add(int(sequence))

        # Calculate approximate one-way latency
        receive_timestamp = time.time()
        latency_ms = (receive_timestamp - send_timestamp) * 1000

        # Update communication time
        last_seen[machine_id] = time.monotonic()

        # Report recovery after an offline alert
        if offline.get(machine_id, False):
            print(
                "\nRECOVERY: Machine",
                machine_id,
                "is communicating again!"
            )

        offline[machine_id] = False

        # Log measurements to CSV
        receive_time_text = datetime.fromtimestamp(
            receive_timestamp
        ).strftime("%Y-%m-%d %H:%M:%S.%f")

        csv_writer.writerow([
            receive_time_text,
            machine_id,
            temperature,
            status,
            round(latency_ms, 3),
            message.topic
        ])
        csv_file.flush()

        print("\n------------------------------")
        print("Machine ID:", machine_id)
        print("Sequence number:", sequence)
        print("Temperature:", temperature, "C")
        print("Reported status:", status)
        print("Message latency:", round(latency_ms, 3), "ms")

        # Temperature and status fault detection
        if temperature >= FAULT_THRESHOLD or status != "RUNNING":
            print("!!! FAULT ALERT !!!")
            print("Machine", machine_id, "requires attention.")
        else:
            print("Machine condition: NORMAL")

    except (ValueError, KeyError, TypeError) as error:
        print("Could not process message:", error)


client = mqtt.Client(
    mqtt.CallbackAPIVersion.VERSION2,
    client_id="industrial_machine_monitor"
)

client.on_connect = on_connect
client.on_message = on_message

print("Starting machine monitor...")

try:
    client.connect(BROKER, PORT, 60)
    client.loop_start()

    while True:
        now = time.monotonic()

        # Detect machines that stop communicating
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
                        round(elapsed, 1), "seconds."
                    )

        time.sleep(CHECK_INTERVAL)

except KeyboardInterrupt:
    print("\nStopping monitor...")

finally:
    client.disconnect()
    client.loop_stop()

    elapsed_time = time.monotonic() - monitor_start_time

    # Calculate throughput
    throughput = (
        total_messages / elapsed_time
        if elapsed_time > 0 else 0
    )

    print("\n===== MQTT PERFORMANCE RESULTS =====")
    print("Monitoring duration:", round(elapsed_time, 2), "seconds")
    print("Total messages received:", total_messages)
    print("Machine 1 messages received:", machine_message_counts["M1"])
    print("Machine 2 messages received:", machine_message_counts["M2"])
    print("Overall throughput:", round(throughput, 3), "messages/second")

    print("\n===== UNIQUE MESSAGES RECEIVED =====")
    print("Machine 1 unique messages:", len(received_sequences["M1"]))
    print("Machine 2 unique messages:", len(received_sequences["M2"]))

    unique_total = sum(
        len(received_sequences[machine_id])
        for machine_id in EXPECTED_MACHINES
    )

    print("Total unique messages:", unique_total)

    # Close the CSV file
    csv_file.close()
    print("CSV file saved and closed.")
    print("Monitor stopped.")
