from mininet.topo import Topo
from mininet.node import Node
import termcolor as T
from mininet.net import Mininet
from mininet.cli import CLI
from mininet.nodelib import LinuxBridge
from mininet.log import setLogLevel
from mininet.link import TCLink

setLogLevel('info')


class LinuxRouter(Node):
    def config(self, **params):
        super(LinuxRouter, self).config(**params)
        if 'routes' in params:
            for (ip, gateway) in params['routes']:
                self.cmd('ip route add {} via {}'.format(ip, gateway))
        self.cmd('sysctl net.ipv4.ip_forward=1')

    def terminate(self):
        self.cmd('sysctl net.ipv4.ip_forward=0')
        super(LinuxRouter, self).terminate()


class DNSServer(Node):
    """ A class to model a DNS server in a Mininet topology. """

    def __init__(self, name, **kwargs):
        # Ensure the DNS server runs in its own network namespace
        kwargs['inNamespace'] = True
        Node.__init__(self, name, **kwargs)

    def log(self, s, col="magenta"):
        print(T.colored(s, col))

    def config(self, mac=None, ip=None, defaultRoute=None, lo='up', **params):
        r = super(DNSServer, self).config(mac=mac, ip=ip,
                                          defaultRoute=defaultRoute, lo=lo, **params)
        self.cmd('sysctl net.ipv4.ip_forward=1')
        self.log("Starting DNS server %s" % self.name)
        # self.cmd("chown -R frr:frr /var/run/frr/%s" % (self.name))
        self.log("named -4 -f -g -c testbed/named.conf.%s -L testbed/logs/named-%s.log" %
                 (self.name, self.name))
        self.cmd("named -4 -c testbed/named.conf.%s -L testbed/logs/named-%s.log" %
                 (self.name, self.name), shell=False)
        # self.waitOutput()
        return r

    def terminate(self):
        self.cmd('sysctl net.ipv4.ip_forward=0')
        self.cmd("kill -9 $(cat testbed/logs/%s.pid)" % self.name)
        super(DNSServer, self).terminate()

# Starter topology: the client host and the root DNS server on one switch.
# Extend it to the full Task 1 topology described in the README.


class DNSTopology(Topo):

    def build(self):
        # add the client host, with the address and default route from the README
        host = self.addHost('host', ip='192.168.0.2/24',
                            defaultRoute='via 192.168.0.1')
        # switches
        s1, s2, s3, s4, s5 = [self.addSwitch(
            s) for s in ('s1', 's2', 's3', 's4', 's5')]

        router1 = self.addNode('router1', cls=LinuxRouter, ip=None,
                               routes=[('10.0.0.0/24', '172.16.32.2'),
                                       ('10.0.1.0/24', '172.16.32.2'),
                                       ('10.0.2.0/24', '172.16.32.2'),
                                       ('10.0.3.0/24', '172.16.32.2')])

        router2 = self.addNode('router2', cls=LinuxRouter, ip=None,
                               routes=[('192.168.0.0/24', '172.16.32.1')])

        root = self.addHost('root', cls=DNSServer,
                            ip='10.0.0.2/24', defaultRoute='via 10.0.0.1')
        tld = self.addHost('tld', cls=DNSServer,
                           ip='10.0.1.2/24', defaultRoute='via 10.0.1.1')
        auth = self.addHost('auth', cls=DNSServer,
                            ip='10.0.2.2/24', defaultRoute='via 10.0.2.1')
        lossy = self.addHost('lossy', cls=DNSServer,
                             ip='10.0.3.2/24', defaultRoute='via 10.0.3.1')

        # link between host and switch 1
        self.addLink(host, s1)

        # link between switch 1 and router 1
        self.addLink(s1, router1, intfName2='router1-eth0',
                     params2={'ip': '192.168.0.1/24'})

        # link between router 1 and 2
        self.addLink(router1, router2,
                     intfName1='router1-eth1', params1={'ip': '172.16.32.1/16'},
                     intfName2='router2-eth0', params2={'ip': '172.16.32.2/16'})

        # links between router 2 and switches
        self.addLink(router2, s2, intfName1='router2-eth1',
                     params1={'ip': '10.0.0.1/24'})
        self.addLink(router2, s3, intfName1='router2-eth2',
                     params1={'ip': '10.0.1.1/24'})
        self.addLink(router2, s4, intfName1='router2-eth3',
                     params1={'ip': '10.0.2.1/24'})

        # explicitly showing link parameters for bandwidth to make it more clear
        self.addLink(router2, s5, bw=None, delay='100ms', loss=10, intfName1='router2-eth4',
                     params1={'ip': '10.0.3.1/24'})

        # links between switches and DNS servers
        self.addLink(s2, root)
        self.addLink(s3, tld)
        self.addLink(s4, auth)
        self.addLink(s5, lossy)
        self.addLink(root, s1)


# the topologies accessible to the mn tool's `--topo` flag
# note: if using the Dockerfile, this must be the same as in the Dockerfile
topos = {'dnsTopology': (lambda: DNSTopology())}


def main():
    net = Mininet(topo=DNSTopology(), switch=LinuxBridge,
                  controller=None, link=TCLink)
    net.start()
    CLI(net)
    net.stop()


if __name__ == "__main__":
    main()
