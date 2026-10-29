
# Shared configuration for MQTT performance experiments

BROKER = "127.0.0.1"
PORT = 1883

# Change this ID for every new experiment
RUN_ID = "qos2_run1"

# MQTT Quality of Service: 0, 1, or 2
QOS_LEVEL = 2

# Duration of each experiment, in seconds
TEST_DURATION = 60

# Time between published messages, in seconds
PUBLISH_INTERVAL = 2

# Allow pending messages to arrive before final analysis
GRACE_PERIOD = 5

# Expected machine IDs
EXPECTED_MACHINES = ["M1", "M2"]

# Topics
TOPIC_M1 = "factory/machine1/status"
TOPIC_M2 = "factory/machine2/status"
MONITOR_TOPIC = "factory/+/status"
