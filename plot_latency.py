
import pandas as pd
import matplotlib.pyplot as plt

# Read the machine-wise summary
df = pd.read_csv("latency_summary.csv")

# Create a bar graph comparing average latency
plt.figure(figsize=(8, 5))

plt.bar(df["Machine_ID"], df["Average"])

plt.xlabel("Machine ID")
plt.ylabel("Average Latency (ms)")
plt.title("Average MQTT Message Latency Comparison")

plt.tight_layout()

# Save the graph for the report
plt.savefig("average_latency_comparison.png", dpi=300)

# Display the graph
plt.show()
