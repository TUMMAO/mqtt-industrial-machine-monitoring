import json
import time
import threading
from collections import deque
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

import paho.mqtt.client as mqtt

from experiment_config import (
    BROKER,
    PORT,
    RUN_ID,
    QOS_LEVEL,
    MONITOR_TOPIC,
    EXPECTED_MACHINES,
)

# ==============================
# DASHBOARD SETTINGS
# ==============================
WEB_HOST = "127.0.0.1"
WEB_PORT = 5000
FAULT_THRESHOLD = 80.0
OFFLINE_TIMEOUT = 6.0
MAX_RECENT_MESSAGES = 20
MAX_LATENCY_POINTS = 60

lock = threading.Lock()
start_time = time.monotonic()
total_deliveries = 0
latency_values = deque(maxlen=MAX_LATENCY_POINTS)
recent_messages = deque(maxlen=MAX_RECENT_MESSAGES)

machines = {
    machine_id: {
        "machine_id": machine_id,
        "last_seen_monotonic": None,
        "temperature": None,
        "status": "WAITING",
        "last_sequence": None,
        "messages_received": 0,
        "unique_sequences": set(),
        "duplicates": 0,
        "fault": False,
    }
    for machine_id in EXPECTED_MACHINES
}


def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code.is_failure:
        print("MQTT connection failed:", reason_code)
        return

    client.subscribe(MONITOR_TOPIC, qos=2)
    print("Dashboard connected to Mosquitto.")
    print("Subscribed to:", MONITOR_TOPIC)
    print("Experiment ID:", RUN_ID)
    print("Configured QoS:", QOS_LEVEL)


def on_message(client, userdata, message):
    global total_deliveries

    try:
        data = json.loads(message.payload.decode("utf-8"))

        # Keep the dashboard focused on the selected experiment.
        if data.get("run_id") != RUN_ID:
            return

        machine_id = data.get("machine_id")
        if machine_id not in machines:
            return

        temperature = float(data["temperature"])
        status = str(data.get("status", "UNKNOWN"))
        sequence = data.get("sequence")
        send_timestamp = float(data["timestamp"])
        received_at = time.time()
        latency_ms = (received_at - send_timestamp) * 1000.0

        with lock:
            item = machines[machine_id]
            item["last_seen_monotonic"] = time.monotonic()
            item["temperature"] = temperature
            item["status"] = status
            item["last_sequence"] = sequence
            item["messages_received"] += 1
            item["fault"] = (
                temperature >= FAULT_THRESHOLD or status != "RUNNING"
            )

            duplicate = False
            if sequence is not None:
                seq = int(sequence)
                if seq in item["unique_sequences"]:
                    item["duplicates"] += 1
                    duplicate = True
                else:
                    item["unique_sequences"].add(seq)

            total_deliveries += 1
            latency_values.append({
                "time": datetime.fromtimestamp(received_at).strftime("%H:%M:%S"),
                "latency_ms": round(latency_ms, 3),
            })

            recent_messages.appendleft({
                "time": datetime.fromtimestamp(received_at).strftime("%H:%M:%S"),
                "machine_id": machine_id,
                "sequence": sequence,
                "temperature": round(temperature, 1),
                "status": status,
                "latency_ms": round(latency_ms, 3),
                "qos": message.qos,
                "duplicate": duplicate,
            })

    except (ValueError, TypeError, KeyError, json.JSONDecodeError) as error:
        print("Ignored invalid MQTT message:", error)


def snapshot():
    now = time.monotonic()

    with lock:
        machine_output = []
        unique_total = 0
        for machine_id, item in machines.items():
            last_seen = item["last_seen_monotonic"]
            seconds_since_message = (
                round(now - last_seen, 1) if last_seen is not None else None
            )
            is_offline = (
                seconds_since_message is None
                or seconds_since_message >= OFFLINE_TIMEOUT
            )
            unique_count = len(item["unique_sequences"])
            unique_total += unique_count

            if is_offline:
                display_status = "OFFLINE"
            elif item["fault"]:
                display_status = "FAULT"
            else:
                display_status = "RUNNING"

            machine_output.append({
                "machine_id": machine_id,
                "temperature": item["temperature"],
                "reported_status": item["status"],
                "display_status": display_status,
                "last_sequence": item["last_sequence"],
                "messages_received": item["messages_received"],
                "unique_messages": unique_count,
                "duplicates": item["duplicates"],
                "seconds_since_message": seconds_since_message,
            })

        elapsed = max(time.monotonic() - start_time, 0.001)
        recent = list(recent_messages)
        latency_history = list(latency_values)
        deliveries = total_deliveries

    latencies = [point["latency_ms"] for point in latency_history]

    return {
        "run_id": RUN_ID,
        "qos": QOS_LEVEL,
        "broker": f"{BROKER}:{PORT}",
        "topic": MONITOR_TOPIC,
        "uptime_seconds": round(elapsed, 1),
        "total_deliveries": deliveries,
        "unique_messages": unique_total,
        "throughput_msg_s": round(deliveries / elapsed, 3),
        "average_latency_ms": round(sum(latencies) / len(latencies), 3) if latencies else None,
        "maximum_latency_ms": round(max(latencies), 3) if latencies else None,
        "machines": machine_output,
        "recent_messages": recent,
        "latency_history": latency_history,
    }


HTML_PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Industrial MQTT Monitoring Dashboard</title>
<style>
:root{font-family:Segoe UI,Arial,sans-serif;color:#172033;background:#f3f6fb}
*{box-sizing:border-box}body{margin:0}
header{background:#13243a;color:white;padding:22px 28px}
header h1{margin:0 0 7px;font-size:25px}header p{margin:0;color:#d3deeb}
main{max-width:1400px;margin:auto;padding:22px}
.topline{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:18px}
.pill{background:white;border:1px solid #dce3ed;border-radius:10px;padding:10px 14px;font-size:13px}
.kpis{display:grid;grid-template-columns:repeat(4,minmax(150px,1fr));gap:14px;margin-bottom:18px}
.card{background:white;border:1px solid #e0e6ef;border-radius:14px;padding:18px;box-shadow:0 2px 8px #1d35570a}
.kpi-label{font-size:13px;color:#627087;margin-bottom:10px}.kpi-value{font-size:28px;font-weight:700}.unit{font-size:13px;color:#627087;font-weight:400}
.section-title{font-size:18px;margin:0 0 14px}
.machine-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;margin-bottom:18px}
.machine-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:14px}
.machine-name{font-size:19px;font-weight:700}
.status{padding:5px 10px;border-radius:999px;font-size:12px;font-weight:700}
.RUNNING{background:#d9f7e8;color:#12633d}.FAULT{background:#ffe1df;color:#9b211b}.OFFLINE{background:#e7eaf0;color:#4d5665}.WAITING{background:#fff0c2;color:#765400}
.readings{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}
.reading{background:#f6f8fc;border-radius:10px;padding:12px}.reading small{display:block;color:#68758a;margin-bottom:6px}.reading strong{font-size:20px}
.lower-grid{display:grid;grid-template-columns:1.1fr 1.4fr;gap:14px;margin-bottom:18px}
canvas{width:100%;height:260px;display:block}
.table-wrap{overflow-x:auto}table{width:100%;border-collapse:collapse;font-size:13px}
th,td{text-align:left;padding:10px 9px;border-bottom:1px solid #edf0f5;white-space:nowrap}
th{color:#68758a;font-weight:600;background:#fafbfe}
.note{font-size:12px;color:#68758a;margin-top:12px}
footer{text-align:center;color:#778398;padding:8px 10px 24px;font-size:12px}
@media(max-width:900px){.kpis{grid-template-columns:repeat(2,minmax(0,1fr))}.lower-grid{grid-template-columns:1fr}}
@media(max-width:560px){main{padding:12px}.machine-grid{grid-template-columns:1fr}.kpis{gap:8px}.kpi-value{font-size:23px}header{padding:18px}}
</style>
</head>
<body>
<header>
  <h1>Industrial Machine Monitoring</h1>
  <p>MQTT-based machine-to-machine communication · Live performance dashboard</p>
</header>
<main>
  <div class="topline">
    <div class="pill">Experiment: <strong id="runId">loading</strong></div>
    <div class="pill">Configured QoS: <strong id="qos">-</strong></div>
    <div class="pill">Broker: <strong id="broker">-</strong></div>
    <div class="pill">Topic: <strong id="topic">-</strong></div>
    <div class="pill">Refresh: every 1 second</div>
  </div>
  <section class="kpis">
    <div class="card"><div class="kpi-label">Total deliveries received</div><div class="kpi-value" id="deliveries">0</div></div>
    <div class="card"><div class="kpi-label">Unique messages received</div><div class="kpi-value" id="unique">0</div></div>
    <div class="card"><div class="kpi-label">Observed throughput</div><div class="kpi-value"><span id="throughput">0</span> <span class="unit">msg/s</span></div></div>
    <div class="card"><div class="kpi-label">Average latency (recent 60)</div><div class="kpi-value"><span id="avgLatency">—</span> <span class="unit">ms</span></div></div>
  </section>
  <h2 class="section-title">Machine status</h2>
  <section class="machine-grid" id="machineCards"></section>
  <section class="lower-grid">
    <div class="card">
      <h2 class="section-title">Latency trend</h2>
      <canvas id="latencyChart" width="700" height="280"></canvas>
      <div class="note">Approximate sender-to-receiver timestamp difference on this computer.</div>
    </div>
    <div class="card">
      <h2 class="section-title">Recent messages</h2>
      <div class="table-wrap">
        <table>
          <thead><tr><th>Time</th><th>Machine</th><th>Seq.</th><th>Temp °C</th><th>Status</th><th>Latency ms</th><th>QoS</th></tr></thead>
          <tbody id="messagesBody"><tr><td colspan="7">Waiting for MQTT messages…</td></tr></tbody>
        </table>
      </div>
    </div>
  </section>
  <div class="card">
    <h2 class="section-title">Monitoring notes</h2>
    <div>Fault rule: temperature ≥ 80 °C or reported status is not RUNNING.</div>
    <div>Offline rule: no matching message received for 6 seconds.</div>
    <div class="note">This dashboard displays live observations for the configured RUN_ID. It does not calculate delivery success rate because publisher-side sent counts are not transmitted to the dashboard.</div>
  </div>
</main>
<footer>Local prototype · Python HTTP server + Paho MQTT · No cloud service required</footer>
<script>
function esc(value){return String(value===null||value===undefined?"—":value).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));}
function fmt(value,digits=3){return value===null||value===undefined?"—":Number(value).toFixed(digits);}
function renderMachines(machines){
  const root=document.getElementById("machineCards");
  root.innerHTML=machines.map(m=>{
    const temp=m.temperature===null?"—":fmt(m.temperature,1)+" °C";
    return `<div class="card">
      <div class="machine-head"><div class="machine-name">${esc(m.machine_id)}</div>
      <span class="status ${esc(m.display_status)}">${esc(m.display_status)}</span></div>
      <div class="readings">
        <div class="reading"><small>Temperature</small><strong>${esc(temp)}</strong></div>
        <div class="reading"><small>Last sequence</small><strong>${esc(m.last_sequence)}</strong></div>
        <div class="reading"><small>Last message</small><strong>${m.seconds_since_message===null?"—":esc(m.seconds_since_message)+" s ago"}</strong></div>
        <div class="reading"><small>Deliveries</small><strong>${esc(m.messages_received)}</strong></div>
        <div class="reading"><small>Unique messages</small><strong>${esc(m.unique_messages)}</strong></div>
        <div class="reading"><small>Duplicates</small><strong>${esc(m.duplicates)}</strong></div>
      </div>
    </div>`;
  }).join("");
}
function renderMessages(messages){
  const body=document.getElementById("messagesBody");
  if(!messages.length){body.innerHTML='<tr><td colspan="7">Waiting for MQTT messages…</td></tr>';return;}
  body.innerHTML=messages.map(m=>`<tr>
    <td>${esc(m.time)}</td><td>${esc(m.machine_id)}</td><td>${esc(m.sequence)}</td>
    <td>${esc(m.temperature)}</td><td>${esc(m.status)}${m.duplicate?" (duplicate)":""}</td>
    <td>${esc(m.latency_ms)}</td><td>${esc(m.qos)}</td></tr>`).join("");
}
function drawLatency(points){
  const canvas=document.getElementById("latencyChart");
  const ctx=canvas.getContext("2d");
  const w=canvas.width,h=canvas.height;
  ctx.clearRect(0,0,w,h);
  const pad={l:55,r:15,t:18,b:35};
  const plotW=w-pad.l-pad.r, plotH=h-pad.t-pad.b;
  ctx.font="12px Segoe UI, Arial";
  const vals=points.map(p=>Number(p.latency_ms)).filter(v=>Number.isFinite(v));
  if(!vals.length){ctx.fillStyle="#68758a";ctx.fillText("Waiting for latency samples…",pad.l+20,pad.t+35);return;}
  const maxVal=Math.max(5,...vals)*1.1;
  ctx.strokeStyle="#e2e8f0";ctx.fillStyle="#65738a";ctx.lineWidth=1;
  for(let i=0;i<=4;i++){
    const y=pad.t+plotH*i/4;
    ctx.beginPath();ctx.moveTo(pad.l,y);ctx.lineTo(w-pad.r,y);ctx.stroke();
    ctx.fillText((maxVal*(1-i/4)).toFixed(1),5,y+4);
  }
  ctx.strokeStyle="#3276b7";ctx.lineWidth=2;ctx.beginPath();
  vals.forEach((v,i)=>{
    const x=pad.l+(vals.length===1?0:i/(vals.length-1))*plotW;
    const y=pad.t+plotH-(v/maxVal)*plotH;
    if(i===0)ctx.moveTo(x,y);else ctx.lineTo(x,y);
  });
  ctx.stroke();
  ctx.fillStyle="#65738a";ctx.fillText("Older",pad.l,h-8);ctx.fillText("Latest",w-pad.r-35,h-8);
}
async function refresh(){
  try{
    const response=await fetch("/api/data",{cache:"no-store"});
    const d=await response.json();
    document.getElementById("runId").textContent=d.run_id;
    document.getElementById("qos").textContent=d.qos;
    document.getElementById("broker").textContent=d.broker;
    document.getElementById("topic").textContent=d.topic;
    document.getElementById("deliveries").textContent=d.total_deliveries;
    document.getElementById("unique").textContent=d.unique_messages;
    document.getElementById("throughput").textContent=fmt(d.throughput_msg_s);
    document.getElementById("avgLatency").textContent=fmt(d.average_latency_ms);
    renderMachines(d.machines);
    renderMessages(d.recent_messages);
    drawLatency(d.latency_history);
  }catch(e){console.error("Dashboard refresh failed:",e);}
}
refresh();setInterval(refresh,1000);
</script>
</body>
</html>
"""


class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlparse(self.path).path

        if path == "/":
            content = HTML_PAGE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
            return

        if path == "/api/data":
            content = json.dumps(snapshot()).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
            return

        self.send_error(404, "Not found")

    def log_message(self, format_string, *args):
        # Keep the terminal output focused on MQTT events.
        return


def main():
    mqtt_client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"industrial_dashboard_{RUN_ID}",
    )
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message

    print("Connecting dashboard to MQTT broker...")
    mqtt_client.connect(BROKER, PORT, 60)
    mqtt_client.loop_start()

    server = ThreadingHTTPServer((WEB_HOST, WEB_PORT), DashboardHandler)
    print(f"Dashboard available at http://{WEB_HOST}:{WEB_PORT}")
    print("Keep this terminal running while using the dashboard.")
    print("Press Ctrl+C to stop.")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping dashboard...")
    finally:
        server.shutdown()
        server.server_close()
        mqtt_client.disconnect()
        mqtt_client.loop_stop()
        print("Dashboard stopped.")


if __name__ == "__main__":
    main()
