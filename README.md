# SDN Traffic Classification System

An SDN-based traffic classification application built using **Mininet** and the **POX OpenFlow controller**. The controller classifies incoming network traffic by protocol (TCP, UDP, ICMP), maintains per-protocol statistics, installs match-action flow rules on the switch, and displays the real-time traffic distribution.

> Submitted for **UE24CS252B – Computer Networks**, PES University.

---

## Problem Statement

**Problem #9: Traffic Classification System**

Design and implement an SDN application that:
- Classifies network traffic based on protocol type (TCP, UDP, ICMP)
- Identifies TCP, UDP, and ICMP packets as they arrive at the switch
- Maintains per-protocol packet and byte statistics
- Displays the classification results
- Analyzes traffic distribution across protocols

This is implemented as a POX controller application that handles OpenFlow `PacketIn` events, inspects IP headers to determine protocol type, increments counters, and installs flow rules so that subsequent packets of the same flow are forwarded directly by the switch without controller intervention.

---

## Architecture

```
     [h1: 10.0.0.1]    [h2: 10.0.0.2]    [h3: 10.0.0.3]
           \                 |                 /
            \                |                /
             \               |               /
              \              |              /
               \             |             /
                [ OpenFlow Switch s1 (OVS) ]
                             |
                             |  OpenFlow (TCP port 6633)
                             |
                 [ POX Controller (localhost) ]
                 Running traffic_classifier.py
```

### Components

| Component | Role |
|---|---|
| **Mininet** | Network emulator creating the virtual topology |
| **Open vSwitch (OVS)** | OpenFlow-capable switch connecting the hosts |
| **POX** | OpenFlow 1.0 controller framework running the classifier app |
| **traffic_classifier.py** | Custom POX module performing classification and flow rule installation |

### Topology Justification

A single-switch topology with 3 hosts was chosen because:
- It is the minimum viable topology to demonstrate protocol classification across multiple flows
- 3 hosts allow simultaneous ICMP, TCP, and UDP flows from different source/destination pairs
- Focus stays on controller logic rather than topology complexity, matching the problem statement's emphasis on classification

---

## Features

- **Protocol classification:** Identifies TCP (IP proto 6), UDP (proto 17), ICMP (proto 1), and OTHER (non-IP like ARP/IPv6)
- **Statistics tracking:** Per-protocol packet count and byte count, with percentage distribution
- **Match-action flow rules:** Installs OpenFlow rules on the switch so subsequent packets of the same flow bypass the controller
- **Flow rule priorities and timeouts:** Priority 10, idle timeout 30s, hard timeout 120s
- **Periodic stats dashboard:** Prints a classification summary every 10 seconds
- **L2 learning:** Basic MAC-to-port learning so the switch knows where to forward packets

---

## Repository Structure

```
sdn-traffic-classifier/
├── topology.py               # Mininet topology script
├── traffic_classifier.py     # POX controller application
├── README.md                 # This file
└── screenshots/              # Proof of execution
    ├── 01_pox_startup.png
    ├── 02_topology_up.png
    ├── 03_pingall_icmp.png
    ├── 04_iperf_tcp.png
    ├── 05_iperf_udp.png
    ├── 06_stats_summary.png
    ├── 07_flow_table.png
    ├── 08_latency.png
    ├── 09_throughput.png
    └── 10_flow_table_final.png
```

---

## Prerequisites

- Ubuntu 22.04 (or compatible Linux distribution)
- Mininet 2.3.0+
- Open vSwitch
- POX (cloned from the noxrepo/pox repository)
- Python 3.10+
- `iperf`, `iputils-ping`, `net-tools`

### Installation Commands

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Mininet + Open vSwitch
sudo apt install mininet openvswitch-switch -y

# Install network utilities
sudo apt install iputils-ping iperf iperf3 net-tools -y

# Clone POX
cd ~
git clone https://github.com/noxrepo/pox.git
```

---

## Setup and Execution

### Step 1: Place the classifier inside POX's extensions folder

```bash
cp traffic_classifier.py ~/pox/ext/
```

### Step 2: Start the POX controller (Terminal A)

```bash
cd ~/pox
./pox.py traffic_classifier
```

Expected output:
```
POX 0.7.0 (gar) is up.
Traffic Classifier initialized. Waiting for switches...
```

### Step 3: Start the Mininet topology (Terminal B)

```bash
sudo python3 topology.py
```

Expected output ends with:
```
*** Network is up. Controller should now be receiving PacketIn events.
mininet>
```

In Terminal A, you should see:
```
Switch connected: dpid=1
```

### Step 4: Generate and classify traffic

Inside the `mininet>` CLI, run:

```
# ICMP traffic
pingall

# TCP traffic
h1 iperf -s &
h2 iperf -c h1 -t 5

# UDP traffic
h1 iperf -s -u &
h3 iperf -c h1 -u -b 5M -t 5
```

Observe `[CLASSIFIED]` log lines in Terminal A for each protocol, and watch the stats summary printed every 10 seconds.

### Step 5: Inspect flow rules (Terminal C)

```bash
sudo ovs-ofctl dump-flows s1
```

---

## Expected Output

### Classifier log (Terminal A)

```
[CLASSIFIED] ICMP | src=00:00:00:00:00:01 dst=00:00:00:00:00:02 | size=98 bytes | total ICMP packets=1
[CLASSIFIED] TCP  | src=00:00:00:00:00:02 dst=00:00:00:00:00:01 | size=74 bytes | total TCP packets=1
[CLASSIFIED] UDP  | src=00:00:00:00:00:03 dst=00:00:00:00:00:01 | size=1512 bytes | total UDP packets=1
```

### Stats summary

```
============================================================
[STATS] Traffic Classification Summary
------------------------------------------------------------
  ICMP   | packets:      6 ( 10.2%) | bytes:      588
  TCP    | packets:      2 (  3.4%) | bytes:      148
  UDP    | packets:      5 (  8.5%) | bytes:     4876
  OTHER  | packets:     46 ( 78.0%) | bytes:     3060
------------------------------------------------------------
  TOTAL  | packets:     59          | bytes:     8672
============================================================
```

### Flow table (`ovs-ofctl dump-flows s1`)

```
cookie=0x0, duration=34.2s, table=0, n_packets=4459, n_bytes=6742008,
idle_timeout=30, hard_timeout=120, priority=10, udp, in_port="s1-eth3",
dl_src=00:00:00:00:00:03, dl_dst=00:00:00:00:00:01,
nw_src=10.0.0.3, nw_dst=10.0.0.1 actions=output:"s1-eth1"
```

Note the high `n_packets` value — this proves the SDN offloading pattern is working correctly. The controller saw only the first PacketIn, and the switch handled the subsequent thousands of packets directly via the installed flow rule.

---

## Test Scenarios

### Scenario 1: Normal Operation – All Protocols Classified

Verifies that each protocol type is correctly identified and counted.

1. Run `pingall` → ICMP packets classified (see `screenshots/03_pingall_icmp.png`)
2. Run iperf TCP → TCP packets classified (see `screenshots/04_iperf_tcp.png`)
3. Run iperf UDP → UDP packets classified (see `screenshots/05_iperf_udp.png`)

**Result:** Non-zero counters for all three protocols, classification labels match expected IP protocol numbers.

### Scenario 2: Traffic Distribution Analysis and Flow Rule Validation

Verifies that the controller correctly analyzes traffic distribution and that match-action rules are installed on the switch.

1. Generate mixed traffic using ping + iperf TCP + iperf UDP
2. Inspect stats summary → percentages sum to 100%, reflect the generated traffic mix (see `screenshots/06_stats_summary.png`)
3. Dump flow table → multiple entries visible with `nw_proto=1` (ICMP), `nw_proto=6` (TCP), `nw_proto=17` (UDP), each with priority 10 and correct timeouts (see `screenshots/07_flow_table.png`)

**Result:** Distribution percentages displayed correctly; flow table shows per-protocol match-action rules with high packet counts, confirming offload.

---

## Performance Observations

### Latency (ICMP ping, 10 packets, h1 → h2)

Measured using `h1 ping -c 10 h2` inside Mininet. See `screenshots/08_latency.png`.

### Throughput (TCP iperf over a 10 Mbps link)

Achieved approximately **9.40 Mbps** on a link capped at 10 Mbps (~94% utilization), confirming the switch forwards classified flows at near line rate without controller involvement. See `screenshots/09_throughput.png`.

### Flow Table Hit Counts

After sustained iperf UDP traffic, the installed UDP flow rule recorded thousands of packet hits while the controller received only the initial PacketIn. See `screenshots/10_flow_table_final.png`. This demonstrates the fundamental SDN efficiency pattern: the controller makes the classification decision once; the switch enforces it at line rate.

---

## Proof of Execution

Full set of screenshots captured during demo is available in the [`screenshots/`](./screenshots) folder.

| # | Screenshot | Description |
|---|---|---|
| 1 | `01_pox_startup.png` | POX controller initialization |
| 2 | `02_topology_up.png` | Mininet topology up; switch connected to controller |
| 3 | `03_pingall_icmp.png` | `pingall` succeeds and ICMP packets classified |
| 4 | `04_iperf_tcp.png` | TCP iperf test and TCP classification |
| 5 | `05_iperf_udp.png` | UDP iperf test and UDP classification |
| 6 | `06_stats_summary.png` | Per-protocol stats and distribution percentages |
| 7 | `07_flow_table.png` | OpenFlow match-action rules installed on the switch |
| 8 | `08_latency.png` | Ping latency statistics |
| 9 | `09_throughput.png` | iperf throughput trace |
| 10 | `10_flow_table_final.png` | Flow table after sustained traffic, showing packet counts |

---

## Key SDN Concepts Demonstrated

- **Separation of control and data plane:** Controller (logic) and switch (forwarding) are decoupled and communicate over OpenFlow
- **PacketIn / FlowMod interaction:** First packet of a flow is punted to the controller; subsequent packets are handled by the switch via installed flow rules
- **Match-action paradigm:** Flow rules match on a packet header tuple (in_port, src MAC, dst MAC, IP protocol, src IP, dst IP) and take an action (output to port)
- **Priorities and timeouts:** Rules have explicit priority (10, above the default miss rule at 0), idle timeout (30s), and hard timeout (120s) — enabling automatic cleanup of stale rules
- **Controller-driven classification:** The controller uses its global view of traffic to classify and collect statistics, an ability a plain Layer 2 switch does not have

---

## References

1. Mininet Documentation – https://mininet.org/
2. POX Wiki – https://openflow.stanford.edu/display/ONL/POX+Wiki
3. OpenFlow 1.0 Specification – https://opennetworking.org/wp-content/uploads/2013/04/openflow-spec-v1.0.0.pdf
4. POX Source Code (noxrepo) – https://github.com/noxrepo/pox
5. Mininet Installation Manual – provided in course materials (UE24CS252B, PES University)

---

## Author

**Nikita Mankani**
UE24CS252B – Computer Networks
PES University
