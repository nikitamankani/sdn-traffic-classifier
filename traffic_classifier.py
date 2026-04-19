"""
traffic_classifier.py - SDN Traffic Classification System

A POX controller application that:
  1. Receives PacketIn events from the OpenFlow switch
  2. Classifies each packet by protocol (ICMP / TCP / UDP / Other)
  3. Maintains per-protocol statistics (counters + byte totals)
  4. Installs match-action flow rules so the switch handles subsequent
     packets of the same flow directly (offloading from controller)
  5. Displays classification results and traffic distribution periodically

This implements the core SDN pattern: controller handles the first packet,
switch handles the rest via installed flow rules.

Author: Nikita
Course: UE24CS252B - Computer Networks
"""

from pox.core import core
import pox.openflow.libopenflow_01 as of
from pox.lib.packet import ipv4, tcp, udp, icmp, ethernet
from pox.lib.addresses import EthAddr
from pox.lib.recoco import Timer

# Logger - POX's built-in logging, shows up in controller terminal
log = core.getLogger()


class TrafficClassifier(object):
    """
    Main classifier object. One instance is created when POX launches
    this module. It registers itself to receive OpenFlow events.
    """

    def __init__(self):
        # Per-protocol packet counters
        self.stats = {
            'ICMP': {'packets': 0, 'bytes': 0},
            'TCP':  {'packets': 0, 'bytes': 0},
            'UDP':  {'packets': 0, 'bytes': 0},
            'OTHER': {'packets': 0, 'bytes': 0},
        }

        # MAC learning table: maps MAC address -> switch port.
        # Needed so we know where to forward packets (basic L2 learning).
        # Structure: {dpid: {mac: port}}
        self.mac_to_port = {}

        # Listen for OpenFlow events from any switch that connects
        core.openflow.addListeners(self)

        # Print stats every 10 seconds so we can see distribution evolve
        Timer(10, self._print_stats, recurring=True)

        log.info("Traffic Classifier initialized. Waiting for switches...")

    def _handle_ConnectionUp(self, event):
        """Called whenever a switch connects to this controller."""
        log.info("Switch connected: dpid=%s", event.dpid)
        self.mac_to_port[event.dpid] = {}

    def _handle_PacketIn(self, event):
        """
        Called whenever a switch forwards an unknown packet to the controller.
        This is where classification happens.
        """
        packet = event.parsed
        if not packet:
            log.warning("Ignoring empty packet")
            return

        # --- Step 1: L2 learning (so we know where MACs live) ---
        dpid = event.dpid
        in_port = event.port
        src_mac = packet.src
        dst_mac = packet.dst

        # Remember: "source MAC was seen on this port"
        self.mac_to_port[dpid][src_mac] = in_port

        # --- Step 2: Classify the packet ---
        protocol, protocol_num = self._classify(packet)
        packet_len = len(packet.raw) if packet.raw else 0

        # Increment stats for this protocol
        self.stats[protocol]['packets'] += 1
        self.stats[protocol]['bytes'] += packet_len

        # Log the classification (this is what examiners see during demo)
        log.info("[CLASSIFIED] %s | src=%s dst=%s | size=%d bytes | total %s packets=%d",
                 protocol, src_mac, dst_mac, packet_len,
                 protocol, self.stats[protocol]['packets'])

        # --- Step 3: Decide output port ---
        # If we know which port the destination MAC lives on, send there.
        # Otherwise, flood (send to all ports except input).
        if dst_mac in self.mac_to_port[dpid]:
            out_port = self.mac_to_port[dpid][dst_mac]
        else:
            out_port = of.OFPP_FLOOD

        # --- Step 4: Install a flow rule (so next packet skips controller) ---
        # Only install rules for classified IP traffic, not floods.
        # Rules speed up future packets AND let us see protocol-specific
        # entries in the flow table during demo.
        if out_port != of.OFPP_FLOOD and protocol != 'OTHER':
            self._install_flow(event, packet, out_port, protocol_num)

        # --- Step 5: Forward the current packet ---
        msg = of.ofp_packet_out()
        msg.data = event.ofp
        msg.actions.append(of.ofp_action_output(port=out_port))
        msg.in_port = in_port
        event.connection.send(msg)

    def _classify(self, packet):
        """
        Inspect packet headers and return (protocol_name, ip_protocol_number).
        Returns ('OTHER', None) for non-IP or unclassified traffic.
        """
        ip_pkt = packet.find('ipv4')
        if ip_pkt is None:
            # Not an IP packet (could be ARP, LLDP, etc.)
            return ('OTHER', None)

        # IP protocol field: 1=ICMP, 6=TCP, 17=UDP (these are IANA standard)
        proto = ip_pkt.protocol
        if proto == ipv4.ICMP_PROTOCOL:
            return ('ICMP', 1)
        elif proto == ipv4.TCP_PROTOCOL:
            return ('TCP', 6)
        elif proto == ipv4.UDP_PROTOCOL:
            return ('UDP', 17)
        else:
            return ('OTHER', proto)

    def _install_flow(self, event, packet, out_port, protocol_num):
        """
        Install an OpenFlow match-action rule so future packets of this
        flow are forwarded directly by the switch.

        Match: (in_port, src MAC, dst MAC, ethertype=IP, ip_proto)
        Action: output to out_port
        Priority: 10 (above default miss rule which has priority 0)
        Idle timeout: 30s (rule removed if unused for 30s)
        Hard timeout: 120s (rule removed after 2 min regardless)
        """
        ip_pkt = packet.find('ipv4')
        if ip_pkt is None:
            return

        msg = of.ofp_flow_mod()
        msg.match = of.ofp_match()
        msg.match.in_port = event.port
        msg.match.dl_src = packet.src
        msg.match.dl_dst = packet.dst
        msg.match.dl_type = ethernet.IP_TYPE      # 0x0800
        msg.match.nw_src = ip_pkt.srcip
        msg.match.nw_dst = ip_pkt.dstip
        msg.match.nw_proto = protocol_num         # 1/6/17

        msg.priority = 10
        msg.idle_timeout = 30
        msg.hard_timeout = 120
        msg.actions.append(of.ofp_action_output(port=out_port))

        event.connection.send(msg)
        log.debug("Flow rule installed: proto=%d out_port=%d", protocol_num, out_port)

    def _print_stats(self):
        """Periodically print traffic distribution statistics."""
        total_packets = sum(v['packets'] for v in self.stats.values())
        total_bytes = sum(v['bytes'] for v in self.stats.values())

        if total_packets == 0:
            log.info("[STATS] No traffic yet.")
            return

        log.info("=" * 60)
        log.info("[STATS] Traffic Classification Summary")
        log.info("-" * 60)
        for proto in ['ICMP', 'TCP', 'UDP', 'OTHER']:
            pkts = self.stats[proto]['packets']
            byts = self.stats[proto]['bytes']
            pct = (pkts / total_packets * 100) if total_packets else 0
            log.info("  %-6s | packets: %6d (%5.1f%%) | bytes: %8d",
                     proto, pkts, pct, byts)
        log.info("-" * 60)
        log.info("  TOTAL  | packets: %6d           | bytes: %8d",
                 total_packets, total_bytes)
        log.info("=" * 60)


def launch():
    """
    POX calls this function when loading the module.
    It registers our classifier as a component under the name 'traffic_classifier'.
    """
    core.registerNew(TrafficClassifier)