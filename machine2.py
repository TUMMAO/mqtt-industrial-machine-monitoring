
import json
import time
import random
import paho.mqtt.client as mqtt

BROKER = "127.0.0.1"
PORT = 1883
MACHINE_ID = "M2"
TOPIC = "factory/machine2/status"

PUBLISH_INTERVAL = 2


client = mqtt.Client(
    mqtt.CallbackAPIVersion.VERSION2,
    client_id="industrial_machine_2"
)

print("Machine 2: Connecting to MQTT broker...")
client.connect(BROKER, PORT, 60)
client.loop_start()
counter = 0

try:
    while True:
        # Simulate normal temperature fluctuations
        temperature = round(random.uniform(58.0, 62.0), 1)

        machine_data = {
            "machine_id": MACHINE_ID,
            "sequence": counter + 1,
            "temperature": temperature,
            "status": "RUNNING",
            "timestamp": time.time()
        }

        payload = json.dumps(machine_data)

        info = client.publish(TOPIC, payload, qos=1)
        info.wait_for_publish()

        print("Published:", payload)
        counter += 1  # Increment sequence number
        time.sleep(PUBLISH_INTERVAL)

except KeyboardInterrupt:
    print("\nMachine 2: Stopping publisher...")

finally:
    client.disconnect()
    client.loop_stop()
    print("Machine 2: Disconnected.")
