#!/bin/bash

# IP tables setup

# Flush all current chains
iptables -F
iptables -t nat -F
iptables -t mangle -F
iptables -X

# Allow traffic to and from LAN and loopback
iptables -A INPUT -i eth0 -j ACCEPT
iptables -A INPUT -i lo -j ACCEPT
iptables -A OUTPUT -o eth0 -j ACCEPT
iptables -A OUTPUT -o lo -j ACCEPT

# Allow outward traffic to be sent to the tunnel interface
# Only allow established and related connections from the tunnel interface
iptables -A OUTPUT -o tun0 -j ACCEPT
iptables -A INPUT -i tun0 -m state --state ESTABLISHED,RELATED -j ACCEPT
iptables -A INPUT -i tun0 -j DROP 

# Do not allow traffic between tunnel and LAN
iptables -A FORWARD -i eth0 -o tun0 -j REJECT
iptables -A FORWARD -i tun0 -o eth0 -j DROP

# Enable forwarded traffic from the WAN
#ip route add default table portfw via 10.1.1.1
#ip rule add fwmark 1 table portfw
iptables -t mangle -A OUTPUT ! -d 10.1.1.0/24 -p tcp -m tcp --sport 22 -j MARK --set-mark 1	# SSH traffic
iptables -t mangle -A OUTPUT ! -d 10.1.1.0/24 -p tcp -m tcp --sport 32400 -j MARK --set-mark 1	# Plex traffic


# To be activated to route between multiple interfaces and VPN tunnle
# Allow traffic to pass between LAN interfaces
#iptables -A FORWARD -i eth1 -o eth0 -j ACCEPT
#iptables -A FORWARD -i eth0 -o eth1 -j ACCEPT

# Allow traffic from the media subnet to be sent to the tunnel interface
# Reject traffic from the main LAN interface
#iptables -A FORWARD -i eth1 -o tun0 -j ACCEPT
#iptables -A FORWARD -i eth0 -o tun0 -j REJECT

# Only allow tunnel traffic destined for the media subnet on established connections
# Reject any traffic from the tunnel interface destined for the main LAN
#iptables -A FORWARD -i tun0 -o eth1 -m state --state ESTABLISHED,RELATED -j ACCEPT
#iptables -A FORWARD -i tun0 -o eth0 -j REJECT

# Apply NAT to traffic going out via the tunnel interface
#iptables -t nat -A POSTROUTING -o tun0 -j MASQUERADE

# Enable packet forwarding
#echo 1 > /proc/sys/net/ipv4/ip_forward
