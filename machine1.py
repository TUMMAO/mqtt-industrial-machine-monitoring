
import json
import time
import paho.mqtt.client as mqtt

BROKER = "127.0.0.1"
PORT = 1883
MACHINE_ID = "M1"
TOPIC = "factory/machine1/status"

FAULT_THRESHOLD = 80.0
PUBLISH_INTERVAL = 2

client = mqtt.Client(
    mqtt.CallbackAPIVersion.VERSION2,
    client_id="industrial_machine_1"
)

print("Machine 1: Connecting to MQTT broker...")
client.connect(BROKER, PORT, 60)
client.loop_start()

counter = 0

try:
    while True:
        # Simulate a rising temperature
        temperature = 68.0 + (counter % 9) * 2.0

        if temperature >= FAULT_THRESHOLD:
            status = "FAULT"
        else:
            status = "RUNNING"

        machine_data = {
            "machine_id": MACHINE_ID,
            "sequence": counter + 1,
            "temperature": temperature,
            "status": status,
            "timestamp": time.time()
        }

        payload = json.dumps(machine_data)

        info = client.publish(TOPIC, payload, qos=1)
        info.wait_for_publish()

        print("Published:", payload)

        counter += 1
        time.sleep(PUBLISH_INTERVAL)

except KeyboardInterrupt:
    print("\nMachine 1: Stopping publisher...")

finally:
    client.disconnect()
    client.loop_stop()
    print("Machine 1: Disconnected.")
