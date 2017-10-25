#! /bin/bash

# Modified from: https://www.niftiestsoftware.com/2011/08/28/making-all-network-traffic-for-a-linux-user-use-a-specific-network-interface/

# Fixed values
PORT_DNS=53
PORT_TRANSMISSION_WEB=9091
PORT_SSH=22

VPN_DNS_SERVER_1=45.76.95.185
VPN_DNS_SERVER_2=45.76.76.54

# Blank values to enable validating that values are properly set later
SYSTEM_TYPE=""

LAN_IF=""
LAN_NW=""
LAN_GW=""

VPN_PROVIDER=""
VPN_IF=""
VPN_MARK=""
VPN_TABLE=""
VPN_USER=""

echo "Num arguments: $#"
echo "Program name: $0"
echo "First arg: $1"
echo "second arg: $2"

function help {
    echo "Usage:"
    echo $0 "[options]"
    echo "  -g  --lan_gw        <arg>   LAN gateway IP"
    echo "  -l  --lan_if        <arg>   LAN interface ID (eg. eth0)"
    echo "  -m  --mark          <arg>   Mark to use for packets matching the routin rule"
    echo "  -n  --lan_nw        <arg>   LAN network (form of <ip>/<prefix length>)"
    echo "  -p  --provider      <arg>   VPN provider"
    echo "  -s  --system        <arg>   Init system (eg. OpenRC, systemd)"
    echo "  -t  --table         <arg>   Routing table to use"
    echo "  -u  --user          <arg>   VPN user (eg. transmission)"
    echo "  -v  --vpn_if        <arg>   VPN interface ID (eg. tun0)"
    exit 1;
}

# Options may be followed by one colon to indicate they have a required argument
if ! OPTIONS=$(getopt -o g:hl:m:n:p:s:t:u:v: -l lan_gw:,help,lan_if:,mark:,lan_nw:,provider:,system:,table:,user:,vpn_if: -- "$@"); then
    # Something went wrong, getopt will put out an error message for us
    exit 1
fi

set -- $OPTIONS

while [ $# -gt 0 ]; do
    case $1 in
        # For options with required arguments, an additional shift is required
        -g|--lan_gw) LAN_GW=`echo $2 | tr -d \'` ; shift;;
        -h|--help) help ;;
        -l|--lan_if) LAN_IF=`echo $2 | tr -d \'` ; shift;;
        -m|--mark) VPN_MARK=`echo $2 | tr -d \'` ; shift;;
        -n|--lan_nw) LAN_NW=`echo $2 | tr -d \'` ; shift;;
        -p|--provider) VPN_PROVIDER=`echo $2 | tr -d \'` ; shift;;
        -s|--system) SYSTEM_TYPE=`echo $2 | tr -d \'` ; shift;;
        -t|--table) VPN_TABLE=`echo $2 | tr -d \'` ; shift;;
        -u|--user) VPN_USER=`echo $2 | tr -d \'` ; shift;;
        -v|--vpn_if) VPN_IF=`echo $2 | tr -d \'` ; shift;;
        (--) shift; break;;
        (-*) echo "$0: error - unrecognized option $1" 1>&2; help;;
        (*) break;;
    esac
    shift
done

#############################################################################
# Make sure all necessary info has been provided
#############################################################################
if [ -z $SYSTEM_TYPE ]; then
	echo "Please specify a valid init system type"
	help
fi

if [ -z $LAN_IF ]; then
	echo "Please specify a valid LAN interface ID"
	help
fi

if [ -z $LAN_NW ]; then
	echo "Please specify a valid LAN network"
	help
fi

if [ -z $LAN_GW ]; then
	echo "Please specify a valid LAN gateway"
	help
fi

if [ -z $VPN_PROVIDER ]; then
	echo "Please specify a valid VPN provider"
	help
fi

if [ -z $VPN_IF ]; then
	echo "Please specify a valid VPN interface ID"
	help
fi

if [ -z $VPN_MARK ]; then
	echo "Please specify a valid VPN rule mark"
	help
fi

if [ -z $VPN_TABLE ]; then
	echo "Please specify a valid VPN routing table"
	help
fi

if [ -z $VPN_USER ]; then
	echo "Please specify a valid VPN service user"
	help
fi

#############################################################################
# Validate the init system
#############################################################################
if [ "$SYSTEM_TYPE" == "openRC" ]; then
	VPN_CONF="/etc/openvpn/$VPN_PROVIDER.conf"
elif [ "$SYSTEM_TYPE" == "systemd" ]; then
	VPN_CONF="/etc/openvpn/$VPN_PROVIDER.conf"
else
	echo "Unsupported system type: \"$SYSTEM_TYPE\""
	exit 1;
fi

#############################################################################
# Set up the IP rule (if necessary)
#############################################################################
if [[ `ip rule list | grep -c $VPN_MARK` == 0 ]]; then
	ip rule add from all fwmark $VPN_MARK lookup $VPN_TABLE
fi

#############################################################################
# Set up the alternate routing table
#############################################################################
VPN_IP=`ifconfig $VPN_IF | egrep -o '([0-9]{1,3}\.){3}[0-9]{1,3}' | egrep -v '255|(127\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3})' | head -n1`
VPN_GW=`ifconfig $VPN_IF | egrep -o '([0-9]{1,3}\.){3}[0-9]{1,3}' | egrep -v '255|(127\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3})' | tail -n1`
VPN_ONE=`echo $VPN_GW | cut -d"." -f1-3`.1
VPN_SERVER_IP=`cat $VPN_CONF | grep remote | head -1 | awk '{print $2}'`

echo "VPN Server IP: $VPN_SERVER_IP"
echo "ip route add $VPN_SERVER_IP via $LAN_GW dev $LAN_IF table $VPN_TABLE"

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

#############################################################################
# Set up the firewall (iptables) rules
#############################################################################
# Clear current IP tables
iptables -F -t nat
iptables -F -t mangle
iptables -F -t filter

# Mark packets from the $VPN_USER not destined for the LAN
iptables -t mangle -A OUTPUT ! --dest $LAN_NW -m owner --uid-owner $VPN_USER -j MARK --set-mark $VPN_MARK
iptables -t mangle -A OUTPUT --dest $LAN_NW -p udp --dport $PORT_DNS -m owner --uid-owner $VPN_USER -j MARK --set-mark $VPN_MARK
iptables -t mangle -A OUTPUT --dest $LAN_NW -p tcp --dport $PORT_DNS -m owner --uid-owner $VPN_USER -j MARK --set-mark $VPN_MARK
iptables -t mangle -A OUTPUT ! --src $LAN_NW -j MARK --set-mark $VPN_MARK # WHD: not sure what purpose this serves

# Allow root to send ping requests
iptables -t mangle -A OUTPUT ! --dest $LAN_NW -p icmp --icmp-type 8 -m owner --uid-owner root -j MARK --set-mark $VPN_MARK

# Don't allow SSH or transmission web UI over the tunel
iptables -A INPUT -i $VPN_IF -p tcp -m tcp --dport $PORT_TRANSMISSION_WEB -j DROP
iptables -A INPUT -i $VPN_IF -p tcp -m tcp --dport $PORT_SSH -j DROP

# Allow responses but block everything else on $VPN_IF
iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT
iptables -A INPUT -i $VPN_IF -j DROP

# Send DNS to VPNArea for $VPN_USER
iptables -t nat -A OUTPUT --dest $LAN_NW -p udp --dport $PORT_DNS -m owner --uid-owner $VPN_USER -j DNAT --to-destination $VPN_DNS_SERVER_1
iptables -t nat -A OUTPUT --dest $LAN_NW -p tcp --dport $PORT_DNS -m owner --uid-owner $VPN_USER -j DNAT --to-destination $VPN_DNS_SERVER_2

# Let $VPN_USER access lo and $VPN_IF
iptables -A OUTPUT -o lo -m owner --uid-owner $VPN_USER -j ACCEPT
iptables -A OUTPUT -o $VPN_IF -m owner --uid-owner $VPN_USER -j ACCEPT

# Allow traffic to and from LAN and loopback
iptables -A INPUT -i $LAN_IF -j ACCEPT
iptables -A INPUT -i lo -j ACCEPT
iptables -A OUTPUT -o $LAN_IF -j ACCEPT
iptables -A OUTPUT -o lo -j ACCEPT

# All packets on $VPN_IF needs to be masqueraded (otherwise it uses the local LAN IP)
iptables -t nat -A POSTROUTING -o $VPN_IF -j MASQUERADE

