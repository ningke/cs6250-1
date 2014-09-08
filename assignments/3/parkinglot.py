#!/usr/bin/python

"Assignment 3 - Creates a parking lot topology, \
    generates flows from senders to the receiver, \
    measures throughput of each flow"

from mininet.topo import Topo
from mininet.net import Mininet
from mininet.log import lg, output
from mininet.node import CPULimitedHost
from mininet.link import TCLink
from mininet.util import custom, quietRun, dumpNetConnections
from mininet.cli import CLI

from time import sleep, time
from multiprocessing import Process
from subprocess import Popen
import termcolor as T
import argparse

import sys
import os
from util.monitor import monitor_devs_ng

import mininet
from mininet.node import CPULimitedHost
import pygraphviz as pgv
import tempfile
import os

def graph_network(topo):
    # naiive implementation -- don't care
    host = custom(CPULimitedHost, cpu=.15)
    link = custom(TCLink, max_queue_size=200)
    net = Mininet(topo=topo, host=host, link=link)
    mininet.util.dumpNetConnections(net)
    nodes = net.controllers + net.switches + net.hosts

    dot = pgv.AGraph()

    edges = []

    for node in nodes:
        if 'c0' == node.name: continue
        dot.add_node(node.name)
        
        for intf in node.intfList():
            if not intf.link: continue
            (a, ai,) = intf.link.intf1.name.split('-')
            (b, bi,) = intf.link.intf2.name.split('-')
            ai = ai.replace('eth', 'p')
            bi = bi.replace('eth', 'p')
            s = [a, b]
            s.sort()
            if s not in edges:
                edges.append(s)
                dot.add_edge(a, b,
                             taillabel=ai+(' '*5),
                             headlabel=bi+(' '*5))

    dot.layout()
    dot.draw('topology.png', prog='dot')

def cprint(s, color, cr=True):
    """Print in color
       s: string to print
       color: color to use"""
    if cr:
        print T.colored(s, color)
    else:
        print T.colored(s, color),

parser = argparse.ArgumentParser(description="Parking lot tests")
parser.add_argument('--bw', '-b',
                    type=float,
                    help="Bandwidth of network links",
                    required=False)

parser.add_argument('--dir', '-d',
                    help="Directory to store outputs",
                    default="results")

parser.add_argument('-n',
                    type=int,
                    help=("Number of senders in the parking lot topo."
                    "Must be >= 1"),
                    required=False)

parser.add_argument('--cli', '-c',
                    action='store_true',
                    help='Run CLI for topology debugging purposes')

parser.add_argument('--time', '-t',
                    dest="time",
                    type=int,
                    help="Duration of the experiment.",
                    default=60)

parser.add_argument('--topo', '-T',
                    action='store_true',
                    dest="show_topo",
                    help="Just produce a PDF of the topology and exit")

# Expt parameters
args = parser.parse_args()

if not os.path.exists(args.dir):
    os.makedirs(args.dir)

lg.setLogLevel('info')

# Topology to be instantiated in Mininet
class ParkingLotTopo(Topo):
    "Parking Lot Topology"

    def __init__(self, n=1, cpu=.1, bw=10, delay=None,
                 max_queue_size=None, **params):
        """Parking lot topology with one receiver
           and n clients.
           n: number of clients
           cpu: system fraction for each host
           bw: link bandwidth in Mb/s
           delay: link delay (e.g. 10ms)"""

        # Initialize topo
        Topo.__init__(self, **params)

        # Host and link configuration
        hconfig = {'cpu': cpu}
        lconfig = {'bw': bw,
                   'delay': delay,
                   'max_queue_size': max_queue_size }

        # Create the actual topology
        receiver = self.addHost('receiver')

        # Switch ports 1:uplink 2:hostlink 3:downlink
        uplink, hostlink, downlink = 1, 2, 3

        hosts = []
        switches = []
        for i in range(n):

            switch_name = 's%d'%(i+1)
            s = self.addSwitch(switch_name)
            switches.append(s)

            host_name = 'h%d'%(i+1)
            h = self.addHost(host_name, **hconfig)
            hosts.append(h)

            # Wire the backbone
            if 0 == i:
                self.addLink(receiver, s, port1=0, port2=uplink, **lconfig)
            else:
                self.addLink(switches[-2], s, port1=downlink, port2=uplink, **lconfig)

            # Wire up the host
            self.addLink(h, s, port1=0, port2=hostlink, **lconfig)

def waitListening(client, server, port):
    "Wait until server is listening on port"
    if not 'telnet' in client.cmd('which telnet'):
        raise Exception('Could not find telnet')
    cmd = ('sh -c "echo A | telnet -e A %s %s"' %
           (server.IP(), port))
    while 'Connected' not in client.cmd(cmd):
        output('waiting for', server,
               'to listen on port', port, '\n')
        sleep(.5)

def progress(t):
    while t > 0:
        cprint('  %3d seconds left  \r' % (t), 'cyan', cr=False)
        t -= 1
        sys.stdout.flush()
        sleep(1)
    print

def start_tcpprobe():
    os.system("rmmod tcp_probe 1>/dev/null 2>&1; modprobe tcp_probe")
    Popen("cat /proc/net/tcpprobe > %s/tcp_probe.txt" % args.dir, shell=True)

def stop_tcpprobe():
    os.system("killall -9 cat; rmmod tcp_probe")

def run_parkinglot_expt(net, n):
    "Run experiment"

    seconds = args.time

    # Start the bandwidth and cwnd monitors in the background
    monitor = Process(target=monitor_devs_ng,
            args=('%s/bwm.txt' % args.dir, 1.0))
    monitor.start()
    start_tcpprobe()

    # Get receiver and clients
    recvr = net.getNodeByName('receiver')
    sender1 = net.getNodeByName('h1')

    # Start the receiver
    port = 5001
    recvr.cmd('iperf -s -p', port,
              '> %s/iperf_server.txt' % args.dir, '&')

    waitListening(sender1, recvr, port)

    # TODO: start the sender iperf processes and wait for the flows to finish
    # Hint: Use getNodeByName() to get a handle on each sender.
    # Hint: Use sendCmd() and waitOutput() to start iperf and wait for them to finish
    # Hint: waitOutput waits for the command to finish allowing you to wait on a particular process on the host
    # iperf command to start flow: 'iperf -c %s -p %s -t %d -i 1 -yc > %s/iperf_%s.txt' % (recvr.IP(), 5001, seconds, args.dir, node_name)
    # Hint (not important): You may use progress(t) to track your experiment progress

    recvr.cmd('kill %iperf')

    # Shut down monitors
    monitor.terminate()
    stop_tcpprobe()

def check_prereqs():
    "Check for necessary programs"
    prereqs = ['telnet', 'bwm-ng', 'iperf', 'ping']
    for p in prereqs:
        if not quietRun('which ' + p):
            raise Exception((
                'Could not find %s - make sure that it is '
                'installed and in your $PATH') % p)

def main():
    "Create and run experiment"
    start = time()

    topo = ParkingLotTopo(n=args.n)
    if args.show_topo:
        graph_network(topo)
        return

    host = custom(CPULimitedHost, cpu=.15)  # 15% of system bandwidth
    link = custom(TCLink, bw=args.bw, delay='1ms',
                  max_queue_size=200)

    net = Mininet(topo=topo, host=host, link=link)

    net.start()

    cprint("*** Dumping network connections:", "green")
    dumpNetConnections(net)

    cprint("*** Testing connectivity", "blue")

    net.pingAll()

    if args.cli:
        # Run CLI instead of experiment
        CLI(net)
    else:
        cprint("*** Running experiment", "magenta")
        run_parkinglot_expt(net, n=args.n)

    net.stop()
    end = time()
    os.system("killall -9 bwm-ng")
    cprint("Experiment took %.3f seconds" % (end - start), "yellow")

if __name__ == '__main__':
    check_prereqs()
    main()
