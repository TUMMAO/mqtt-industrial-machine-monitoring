
import pandas as pd

# Read the measurements collected by machine_monitor.py
df = pd.read_csv("latency_results.csv")

# Convert latency values to numeric data
df["Latency_ms"] = pd.to_numeric(
    df["Latency_ms"], errors="coerce"
)
df = df.dropna(subset=["Latency_ms"])

# Overall performance statistics
print("\n===== OVERALL MQTT LATENCY =====")
print("Total messages:", len(df))
print("Average latency:", round(df["Latency_ms"].mean(), 3), "ms")
print("Minimum latency:", round(df["Latency_ms"].min(), 3), "ms")
print("Maximum latency:", round(df["Latency_ms"].max(), 3), "ms")

# Calculate statistics separately for each machine
print("\n===== MACHINE-WISE LATENCY =====")

summary = df.groupby("Machine_ID")["Latency_ms"].agg(
    Message_Count="count",
    Average="mean",
    Minimum="min",
    Maximum="max"
).round(3)

print(summary)

# Save summary results for the project report
summary.to_csv("latency_summary.csv")

print("\nSummary saved to latency_summary.csv")
