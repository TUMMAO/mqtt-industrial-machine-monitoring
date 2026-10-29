

import json
import time

import paho.mqtt.client as mqtt

from experiment_config import (
    BROKER,
    PORT,
    RUN_ID,
    QOS_LEVEL,
    TEST_DURATION,
    PUBLISH_INTERVAL,
    TOPIC_M1,
)

MACHINE_ID = "M1"
FAULT_THRESHOLD = 80.0


def main():
    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"industrial_machine_1_{RUN_ID}"
    )

    counter = 0
    published_count = 0
    start_time = None

    print(f"Machine {MACHINE_ID}: Connecting to broker...")

    try:
        client.connect(BROKER, PORT, 60)
        client.loop_start()

        # Allow the MQTT connection to establish.
        deadline = time.monotonic() + 10
        while not client.is_connected():
            if time.monotonic() >= deadline:
                raise TimeoutError("Could not connect to MQTT broker.")
            time.sleep(0.1)

        print("Connected to Mosquitto.")
        print("Experiment ID:", RUN_ID)
        print("QoS level:", QOS_LEVEL)
        print("Test duration:", TEST_DURATION, "seconds")

        start_time = time.monotonic()

        while time.monotonic() - start_time < TEST_DURATION:
            temperature = 68.0 + (counter % 9) * 2.0

            status = (
                "FAULT"
                if temperature >= FAULT_THRESHOLD
                else "RUNNING"
            )

            machine_data = {
                "run_id": RUN_ID,
                "machine_id": MACHINE_ID,
                "sequence": counter + 1,
                "qos": QOS_LEVEL,
                "temperature": temperature,
                "status": status,
                "timestamp": time.time()
            }

            payload = json.dumps(machine_data)

            info = client.publish(
                TOPIC_M1,
                payload,
                qos=QOS_LEVEL
            )

            if info.rc == mqtt.MQTT_ERR_SUCCESS:
                try:
                    info.wait_for_publish(timeout=10)

                    if info.is_published():
                        published_count += 1
                        print(
                            f"Published seq={counter + 1}, "
                            f"temp={temperature} C, status={status}"
                        )
                    else:
                        print(
                            "Publish did not complete for sequence",
                            counter + 1
                        )

                except (ValueError, RuntimeError) as error:
                    print("Publish confirmation issue:", error)
            else:
                print("Publish request failed:", info.rc)

            counter += 1
            time.sleep(PUBLISH_INTERVAL)

    except KeyboardInterrupt:
        print("\nMachine 1 stopped by user.")

    except (OSError, TimeoutError) as error:
        print("Machine 1 connection error:", error)

    finally:
        try:
            client.disconnect()
            client.loop_stop()
        except Exception:
            pass

        elapsed = (
            time.monotonic() - start_time
            if start_time is not None
            else 0
        )

        print("\n===== MACHINE 1 SUMMARY =====")
        print("Experiment ID:", RUN_ID)
        print("Publish requests attempted:", counter)
        print("Publish operations completed:", published_count)
        print("Elapsed time:", round(elapsed, 2), "seconds")
        print("Machine 1 disconnected.")


if __name__ == "__main__":
    main()

