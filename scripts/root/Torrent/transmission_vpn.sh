#! /bin/bash

# Modified from: https://www.niftiestsoftware.com/2011/08/28/making-all-network-traffic-for-a-linux-user-use-a-specific-network-interface/

#VPN_USER="transmission"
VPN_USER=$1

VPN_IF="tun0"
VPN_MARK="0x2"
VPN_PROVIDER="vpnarea"

LAN_NW="10.1.1.0/24"
LAN_IF="eth0"

# Clear current IP tables
iptables -F -t nat
iptables -F -t mangle
iptables -F -t filter

# Mark packets from the $VPN_USER not destined for the LAN
iptables -t mangle -A OUTPUT ! --dest $LAN_NW -m owner --uid-owner $VPN_USER -j MARK --set-mark $VPN_MARK
iptables -t mangle -A OUTPUT --dest $LAN_NW -p udp --dport 53 -m owner --uid-owner $VPN_USER -j MARK --set-mark $VPN_MARK 
iptables -t mangle -A OUTPUT --dest $LAN_NW -p tcp --dport 53 -m owner --uid-owner $VPN_USER -j MARK --set-mark $VPN_MARK
iptables -t mangle -A OUTPUT ! --src $LAN_NW -j MARK --set-mark $VPN_MARK # WHD: not sure what purpose this serves

# Allow root to send ping requests
iptables -t mangle -A OUTPUT ! --dest $LAN_NW -p icmp --icmp-type 8 -m owner --uid-owner root -j MARK --set-mark $VPN_MARK

# Don't allow SSH or transmission web UI over the tunel
iptables -A INPUT -i $VPN_IF -p tcp -m tcp --dport 9091 -j DROP
iptables -A INPUT -i $VPN_IF -p tcp -m tcp --dport 22 -j DROP

# Allow responses but block everything else on $VPN_IF
iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT
iptables -A INPUT -i $VPN_IF -j DROP

# Send DNS to VPNArea for $VPN_USER
iptables -t nat -A OUTPUT --dest $LAN_NW -p udp --dport 53 -m owner --uid-owner $VPN_USER -j DNAT --to-destination 45.76.95.185
iptables -t nat -A OUTPUT --dest $LAN_NW -p tcp --dport 53 -m owner --uid-owner $VPN_USER -j DNAT --to-destination 45.76.76.54

# Let $VPN_USER access lo and $VPN_IF
iptables -A OUTPUT -o lo -m owner --uid-owner $VPN_USER -j ACCEPT
iptables -A OUTPUT -o $VPN_IF -m owner --uid-owner $VPN_USER -j ACCEPT

# Allow traffic to and from LAN and loopback
iptables -A INPUT -i eth0 -j ACCEPT
iptables -A INPUT -i lo -j ACCEPT
iptables -A OUTPUT -o eth0 -j ACCEPT
iptables -A OUTPUT -o lo -j ACCEPT


# All packets on $VPN_IF needs to be masqueraded (otherwise it uses the local LAN IP)
iptables -t nat -A POSTROUTING -o $VPN_IF -j MASQUERADE

# Reject connections from predator ip going over $LAN_IF (WHD: This breaks VPN Area)
#iptables -A OUTPUT ! --src $LAN_NW -o $LAN_IF -j REJECT
