#!/usr/bin/env python3
"""
topology.py - Mininet topology for SDN Traffic Classification System

Creates a simple network:
  - 1 OpenFlow switch (s1)
  - 3 hosts (h1, h2, h3) connected to s1
  - Points the switch to a remote POX controller running on 127.0.0.1:6633

This topology is intentionally minimal so the focus stays on the classifier
logic. 3 hosts are enough to demonstrate:
  - Pairwise communication (h1 <-> h2 for ICMP ping)
  - Client-server traffic (h1 as iperf server, h2/h3 as clients for TCP/UDP)

Author: Nikita
Course: UE24CS252B - Computer Networks
"""

from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch
from mininet.cli import CLI
from mininet.link import TCLink
from mininet.log import setLogLevel, info


def build_topology():
    """Build and start the Mininet network."""
    
    # Create Mininet instance with:
    # - OVSSwitch: Open vSwitch, which speaks OpenFlow
    # - TCLink: link type that supports traffic control (bandwidth, delay)
    # - build=False: we'll add components manually before starting
    net = Mininet(
        controller=None,      # we'll add a remote controller manually
        switch=OVSSwitch,
        link=TCLink,
        autoSetMacs=True,     # assign predictable MAC addresses (easier to read in logs)
        build=False
    )

    # Add a remote controller. POX will run separately on localhost:6633.
    # 'c0' is just a label - Mininet uses it internally.
    info('*** Adding POX controller\n')
    c0 = net.addController(
        name='c0',
        controller=RemoteController,
        ip='127.0.0.1',
        port=6633
    )

    # Add the switch. dpid='1' gives it a predictable datapath ID in logs.
    info('*** Adding switch\n')
    s1 = net.addSwitch('s1', dpid='1')

    # Add 3 hosts with static IPs in the 10.0.0.0/24 subnet.
    info('*** Adding hosts\n')
    h1 = net.addHost('h1', ip='10.0.0.1/24')
    h2 = net.addHost('h2', ip='10.0.0.2/24')
    h3 = net.addHost('h3', ip='10.0.0.3/24')

    # Connect each host to the switch with a 10 Mbps link.
    # Bandwidth cap helps make iperf results visually meaningful.
    info('*** Creating links\n')
    net.addLink(h1, s1, bw=10)
    net.addLink(h2, s1, bw=10)
    net.addLink(h3, s1, bw=10)

    # Start the network (this triggers the switch to connect to the controller)
    info('*** Starting network\n')
    net.build()
    c0.start()
    s1.start([c0])

    info('*** Network is up. Controller should now be receiving PacketIn events.\n')
    info('*** Try: pingall, or h1 iperf -s & then h2 iperf -c h1\n')

    # Drop into the Mininet CLI so we can issue commands interactively.
    CLI(net)

    # Clean shutdown when user exits CLI.
    info('*** Stopping network\n')
    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    build_topology()