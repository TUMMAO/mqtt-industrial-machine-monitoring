# MQTT-Based Industrial Machine Monitoring Middleware

## Overview

This project implements a simulated industrial machine-monitoring system using **MQTT (Message Queuing Telemetry Transport)**. It demonstrates message-based communication between multiple machine publishers and a central monitoring application.

Two Python programs simulate industrial machines that periodically publish temperature, machine status, timestamps, and sequence numbers. A central monitoring application subscribes to their MQTT messages and monitors machine conditions.

The project also evaluates communication performance using metrics such as message latency, throughput, and unique messages received.

## Objectives

- Implement MQTT-based machine-to-machine communication.
- Simulate multiple industrial machines using Python.
- Monitor machine temperatures and operating status.
- Detect temperature faults and communication interruptions.
- Measure message latency and throughput.
- Record communication data for performance analysis.

## System Architecture

```text
 Machine 1 Publisher                 Machine 2 Publisher
     machine1.py                         machine2.py
          |                                   |
          |          MQTT Messages            |
          +---------------+-------------------+
                          |
                          v
                 Mosquitto MQTT Broker
                          |
                          v
                 Machine Monitor
                 machine_monitor.py
                          |
             +------------+------------+
             |            |            |
             v            v            v
          Faults       Latency      Throughput
                       Logging      Measurement
                          |
                          v
                   CSV Data Analysis
```

## Technologies Used

- **Python** — machine simulation and monitoring logic
- **MQTT** — publish/subscribe communication protocol
- **Eclipse Mosquitto** — MQTT message broker
- **Paho MQTT** — Python MQTT client library
- **JSON** — message payload format
- **CSV** — performance data logging
- **Pandas and Matplotlib** — data analysis and visualization

## Project Structure

```text
mqtt-industrial-machine-monitoring/
├── machine1.py
├── machine2.py
├── machine_monitor.py
├── analyze_latency.py
├── plot_latency.py
├── latency_results.csv
├── latency_summary.csv
├── average_latency_comparison.png
├── requirements.txt
└── README.md
```

*Note: Include only the files that actually exist in your repository. Generated result files may be added after completing the experiments.*

## How It Works

1. Machine 1 simulates a rising temperature and reports a fault when the configured threshold is reached.
2. Machine 2 simulates normal temperature variations.
3. Both machines publish JSON messages to separate MQTT topics.
4. The Mosquitto broker receives and forwards messages to subscribed clients.
5. The monitoring application subscribes to `factory/+/status` to receive messages from both machines.
6. The monitor checks temperature and machine status, detects communication timeouts, calculates approximate message latency, and counts received messages.
7. Measurements are stored in a CSV file for further analysis.

### MQTT Topics

| Machine | Topic |
|---|---|
| Machine 1 | `factory/machine1/status` |
| Machine 2 | `factory/machine2/status` |
| Monitor subscription | `factory/+/status` |

### Example Message

```json
{
  "machine_id": "M1",
  "sequence": 1,
  "temperature": 68.0,
  "status": "RUNNING",
  "timestamp": 1793036676.83
}
```

## Installation and Setup

### Prerequisites

- Python 3
- Eclipse Mosquitto MQTT broker
- Git
- Required Python libraries

### 1. Clone the Repository

```bash
git clone https://github.com/YOUR-USERNAME/mqtt-industrial-machine-monitoring.git
cd mqtt-industrial-machine-monitoring
```

Replace `YOUR-USERNAME` with your GitHub username.

### 2. Install Dependencies

```bash
pip install paho-mqtt pandas matplotlib
```

### 3. Start the MQTT Broker

Install Mosquitto and ensure the broker is running locally on port `1883`.

The Python scripts are configured to connect to `127.0.0.1`.

### 4. Run the Programs

Open separate terminals in the project directory.

Terminal 1:

```bash
python machine_monitor.py
```

Terminal 2:

```bash
python machine1.py
```

Terminal 3:

```bash
python machine2.py
```

Keep the broker and all three programs running during the experiment.

## Performance Evaluation

The system can be evaluated using the following metrics:

- **Message latency:** Approximate time between message creation and reception.
- **Throughput:** Number of valid messages received per second.
- **Unique messages received:** Number of distinct sequence numbers observed for each machine.
- **Communication availability:** Detection of machines that stop sending messages.
- **Fault detection:** Identification of temperature threshold violations or abnormal reported status.

The current setup runs locally on one computer. Therefore, latency measurements represent local software communication and should not be interpreted as industrial network latency.

Unique message counts alone do not establish delivery success rate. A delivery success rate requires comparing sent and received messages over the same controlled experiment.

## Limitations

- Machines are simulated in software; no physical industrial hardware is connected.
- The MQTT broker and clients run locally by default.
- The temperature threshold is a demonstration setting, not a validated industrial safety limit.
- Performance results may vary with the test duration and system workload.

## Future Improvements

- Evaluate message delivery success rate under controlled test conditions.
- Compare MQTT QoS levels.
- Test multiple simulated machines.
- Analyze performance under increased message rates.
- Generate latency and throughput graphs.
- Explore operation across multiple computers or a real industrial network.

## Academic Project

This project demonstrates the design and performance evaluation of an MQTT-based middleware system for simulated industrial machine-to-machine communication.

