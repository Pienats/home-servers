#! /bin/bash

# Modified from: https://www.niftiestsoftware.com/2011/08/28/making-all-network-traffic-for-a-linux-user-use-a-specific-network-interface/

# System type:
SYSTEM_TYPE=$1

VPN_PROVIDER="vpnarea"
VPN_IF="tun0"
VPN_TABLE="vpn"
VPN_MARK="0x2"

if [ "$SYSTEM_TYPE" == "rc" ]; then
	VPN_CONF="/etc/openvpn/$VPN_PROVIDER.conf"
elif [ "$SYSTEM_TYPE" == "systemd" ]; then
	VPN_CONF="/etc/openvpn/client/$VPN_PROVIDER.conf"
else
	echo "Unsupported system type: $SYSTEM_TYPE"
	exit 1;
fi

LAN_IF="eth0"
LAN_GW="10.1.1.1"
LAN_NW="10.1.1.0/24"

if [[ `ip rule list | grep -c $VPN_MARK` == 0 ]]; then
	ip rule add from all fwmark $VPN_MARK lookup $VPN_TABLE
fi

VPN_IP=`ifconfig $VPN_IF | egrep -o '([0-9]{1,3}\.){3}[0-9]{1,3}' | egrep -v '255|(127\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3})' | head -n1`
VPN_GW=`ifconfig $VPN_IF | egrep -o '([0-9]{1,3}\.){3}[0-9]{1,3}' | egrep -v '255|(127\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3})' | tail -n1`
VPN_ONE=`echo $VPN_GW | cut -d"." -f1-3`.1
VPN_SERVER_IP=`cat $VPN_CONF | grep remote | awk '{print $2}'`

ip route flush table vpn
ip route add 0.0.0.0/1 via $VPN_GW dev $VPN_IF table $VPN_TABLE
ip route add default via $VPN_GW dev $VPN_IF table $VPN_TABLE
ip route append default via 127.0.0.1 dev lo table $VPN_TABLE
ip route add $VPN_ONE via $VPN_GW dev $VPN_IF table $VPN_TABLE
ip route add $VPN_GW dev $VPN_IF proto kernel scope link src $VPN_IP table $VPN_TABLE
ip route add $VPN_SERVER_IP via $LAN_GW dev $LAN_IF table $VPN_TABLE
ip route add $LAN_NW dev $LAN_IF table $VPN_TABLE

ip route show table $VPN_TABLE
ip route flush cache
