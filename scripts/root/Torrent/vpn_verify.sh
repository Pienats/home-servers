#!/bin/bash

START_SERVICE="rc"
#START_SERVICE="systemd"

LOGGING_ENABLED=1
LOG_FILE="/dev/shm/vpntest.log"

TESTING=0

VPN_PROVIDER=$1

WAIT_TIME_SECONDS=1

TRANSMISSION_SERVICE="transmission-daemon"
#TRANSMISSION_SERVICE="transmission"

STATIC_VPN_DEV="tun0" # "Hardcoded" in config
VPN_PROVIDERS_PING_ONE="vpnarea"

VPN_MAX_RESTART_ATTEMPTS=5
VPN_MAX_START_ATTEMPTS=5
VPN_MAX_ROUTE_ATTEMPTS=5
VPN_MAX_DEV_ATTEMPTS=10

VPN_START_WAIT_TIME_SECONDS=5
VPN_PING_ONE=0

TRANSMISSION_MAX_STATUS_ATTEMPTS=5

if [ "$START_SERVICE" == "rc" ]; then
	VPN_START_CMD="/etc/init.d/openvpn.$VPN_PROVIDER start"
	VPN_STOP_CMD="/etc/init.d/openvpn.$VPN_PROVIDER stop"
	VPN_STATUS_CMD="/etc/init.d/openvpn.$VPN_PROVIDER status"

	TRANSMISSION_START_CMD="/etc/init.d/$TRANSMISSION_SERVICE start"
	TRANSMISSION_STOP_CMD="/etc/init.d/$TRANSMISSION_SERVICE stop"
	TRANSMISSION_STATUS_CMD="/etc/init.d/$TRANSMISSION_SERVICE status"

	SERVICE_OK_STRING="status: started" # Systemd
elif [ "$START_SERVICE" == "systemd" ]; then 
	VPN_START_CMD="systemctl start openvpn-client@$VPN_PROVIDER.service" # Systemd
	VPN_STOP_CMD="systemctl stop openvpn-client@$VPN_PROVIDER.service" # Systemd
	VPN_STATUS_CMD="systemctl status openvpn-client@$VPN_PROVIDER.service" # Systemd

	TRANSMISSION_START_CMD="systemctl start $TRANSMISSION_SERVICE" # Systemd
	TRANSMISSION_STOP_CMD="systemctl stop $TRANSMISSION_SERVICE" # Systemd
	TRANSMISSION_STATUS_CMD="systemctl status $TRANSMISSION_SERVICE" # Systemd

	SERVICE_OK_STRING="Active: active (running)" # Systemd
else
	# Logging function not yet defined here, so can't use log functionality
	# However, since this is a deal breaker, we need automatically log here
	# anyway, regardless of log config even
	echo "Unknown system start service: $START_SERVICE" >> $LOG_FILE
	exit 1
fi

if [ $TESTING -eq 1 ]; then
	echo "Testing mode"
	TRANSMISSION_SETTINGS_DIR="/root" # Testing
fi

VPN_LOG_FILE="/dev/shm/openvpn.log"
TRANSMISSION_SETTINGS_DIR="/var/lib/transmission/config/"
TRANSMISSION_SETTINGS_FILE="$TRANSMISSION_SETTINGS_DIR/settings.json"
RES=0
VPN_UP=0 # Start by assuming the VPN is not up

function log_text {
	if [ $LOGGING_ENABLED -eq 1 ]; then
		if [ "$1" == "0" ]; then
			echo "" >> $LOG_FILE
		else
			DATE=`date +"%Y-%m-%d - %H:%M:%S: "`
			echo "$DATE $1" >> $LOG_FILE
		fi
	fi
}

function vpn_get_status {
	# Test if the VPN is up by calling $VPN_STATUS_CMD once
	# If the VPN is up, the 'grep' will succeed
	STATUS=`$VPN_STATUS_CMD | grep "$SERVICE_OK_STRING"`
		
	if [ -z "$STATUS" ]; then
		log_text "VPN not up; STATUS=$STATUS"
		VPN_UP=0
	else
		log_text "VPN is up; STATUS=$STATUS"
		VPN_UP=1
	fi
}

function vpn_start {
	$VPN_START_CMD

	# Test if the VPN has started successfully by testing the
	# status $VPN_MAX_START_ATTEMPTS times with $WAIT_TIME_SECONDS
	# seconds between attempts

	for I in `seq 1 $VPN_MAX_START_ATTEMPTS`; do
		vpn_get_status

		if [ "$VPN_UP" -eq "0" ]; then
			log_text "VPN not up; STATUS=$STATUS [$I/$VPN_MAX_START_ATTEMPTS]"
			sleep $VPN_START_WAIT_TIME_SECONDS
		else
			log_text "Service is OK; STATUS=$STATUS"
			return
		fi
	done
	
	log_text "vpn_start: VPN still down after testing $VPN_MAX_START_ATTEMPTS times"
	log_text 0
	exit 1
}

function vpn_stop {
	$VPN_STOP_CMD

	# Test if the VPN has stopped successfully by testing the
	# status $VPN_MAX_START_ATTEMPTS times with $WAIT_TIME_SECONDS
	# seconds between attempts

	for I in `seq 1 $VPN_MAX_START_ATTEMPTS`; do
		vpn_get_status

		if [ "$VPN_UP" -eq "1" ]; then
			log_text "VPN still up; STATUS=$STATUS [$I/$VPN_MAX_START_ATTEMPTS]"
			sleep $VPN_START_WAIT_TIME_SECONDS
		else
			log_text "Service stopped; STATUS=$STATUS"
			return
		fi
	done
	
	log_text "vpn_stop: VPN still up after testing $VPN_MAX_START_ATTEMPTS times"
	log_text 0
	exit 1
}

function vpn_get_info {
	# Attempt to determine the VPN device by testing the output of the
	# log file $VPN_MAX_DEV_ATTEMPTS times with $WAIT_TIME_SECONDS seconds
	# between attempts
	
	for I in `seq 1 $VPN_MAX_DEV_ATTEMPTS`; do
		VPN_DEV=$STATIC_VPN_DEV
		VPN_IP=`ifconfig tun0 | grep inet | awk '{print $2}'`

		if [ -z $VPN_DEV ]; then
			log_text "Unable to determine VPN device ID"
			exit 1
		fi
		
		if [ -z $VPN_IP ]; then
			log_text "Unable to determine VPN IP [$I/$VPN_MAX_DEV_ATTEMPTS]"
			sleep $WAIT_TIME_SECONDS
			continue
		fi
		
		log_text "VPN Device: $VPN_DEV"
		log_text "VPN IP: $VPN_IP"
		return
	done

	log_text "Unable to determine VPN device after $VPN_MAX_DEV_ATTEMPTS attempts"
	log_text 0
	exit 1
}

function vpn_test_link {
	# Find the route for the VPN device that is Up, Gateway and Host, (UGH)
	# and assume that the destination IP is sufficient as a test IP
	# Do this $VPN_MAX_ROUTE_ATTEMPTS times at $WAIT_TIME_SECONDS intervals to
	# make sure routes are set properly after a tunnel start
	
	for I in `seq 1 $VPN_MAX_RESTART_ATTEMPTS`; do
		log_text "Attempting to find remote host for $VPN_DEV"
		for J in `seq 1 $VPN_MAX_ROUTE_ATTEMPTS`; do
			VPN_REMOTE_HOST=`route -v | grep "$VPN_DEV" | grep -m 1 UG | awk '{print $2}'`
			if [ -z "$VPN_REMOTE_HOST" ]; then
				sleep $WAIT_TIME_SECONDS
			fi
		done

		if [ -z "$VPN_REMOTE_HOST" ]; then
			log_text "Unable to determine the remote host IP for $VPN_DEV after $VPN_MAX_ROUTE_ATTEMPTS attempts"
			log_text "Restarting VPN"
			vpn_stop
			vpn_start
			continue
		fi

		if [ $VPN_PING_ONE -eq 1 ]; then
			VPN_REMOTE_HOST=`echo $VPN_REMOTE_HOST | cut -d"." -f1-3`.1
		fi

		log_text "Attempting to ping $VPN_REMOTE_HOST"
		ping -c 1 -W 3 $VPN_REMOTE_HOST > /dev/null 2>&1
		RES=$?

		if [ "$RES" -ne "0" ]; then
			log_text "No ping response from $VPN_REMOTE_HOST [$RES]"
			# TODO: Attempt restart
			log_text "Restarting VPN"
			vpn_stop
			vpn_start
			continue
		fi
		
		log_text "Successfully pinged $VPN_REMOTE_HOST"
		return
	done
	
	log_text "Unable to successfully verify VPN link after $VPN_MAX_RESTART_ATTEMPTS attempts"
	log_text 0
	exit 1
}

function transmission_stop {
	$TRANSMISSION_STOP_CMD
	
	for I in `seq 1 $TRANSMISSION_MAX_STATUS_ATTEMPTS`; do
		STS=`$TRANSMISSION_STATUS_CMD | grep "$SERVICE_OK_STRING"`
		
		if [ -z "$STS" ]; then
			# $TRANSMISSION_STATUS_CMD
			log_text "Transmission shutdown complete"
			return
		else
			log_text "Transmission daemon shutdown not done yet [$I]"
			sleep $WAIT_TIME_SECONDS
		fi
	done
	
	log_text "Transmission daemon shutdown did not complete after $TRANSMISSION_MAX_STATUS_ATTEMPTS cycles"
	log_text 0
	exit 1
}

function transmission_start {
	$TRANSMISSION_START_CMD
	
	for I in `seq 1 $TRANSMISSION_MAX_STATUS_ATTEMPTS`; do
		STS=`$TRANSMISSION_STATUS_CMD | grep "$SERVICE_OK_STRING"`
		
		if [ -z "$STS" ]; then
			log_text "Transmission daemon startup not done yet [$I]"
			sleep $WAIT_TIME_SECONDS
		else
			# $TRANSMISSION_STATUS_CMD
			log_text "Transmission startup complete"
			return
		fi
	done
	
	log_text "Transmission daemon startup did not complete after $TRANSMISSION_MAX_STATUS_ATTEMPTS cycles"
	log_text 0
	exit 1
}

function set_ping_one {
# For certain VPN providers, the gate is our address with a .1 at the end
# Regardless of the routing table default gateway
	for PROVIDER in $VPN_PROVIDERS_PING_ONE; do
		if [ "$VPN_PROVIDER" == "$PROVIDER" ]; then
			log_text "Need to ping gateway with IP 1"
			VPN_PING_ONE=1;
			break;
		fi
	done
}

log_text "=================================================="
# Determine if we need to ping the gateway with IP 1
set_ping_one

# Determine if the tunnel exists
vpn_get_status

if [ "$VPN_UP" -eq "0" ]; then
	log_text "VPN tunnel does not appear to be up, attempting to start"
	vpn_start
fi

# Get the VPN info (device ID and IP)
vpn_get_info

# Test the VPN link
vpn_test_link

if [ ! -f $TRANSMISSION_SETTINGS_FILE ]; then
	log_text "ERROR: Settings file $TRANSMISSION_SETTINGS_FILE does not exist; Exiting"
	log_text 0
	exit 1
else
	log_text "Comparing current IP with stored value"
	TRANSMISSION_BIND_IP=`cat $TRANSMISSION_SETTINGS_FILE | grep bind-address-ipv4 | awk '{print $2}' | sed 's/[",]//g'`
	
	if [ ! "$VPN_IP" = "$TRANSMISSION_BIND_IP" ]; then
		log_text "Current and stored IPs do not match, updating required"
		log_text "Stored IP: $TRANSMISSION_BIND_IP"
		log_text "Current IP: $VPN_IP"
		log_text "Stopping transmission"
		# Stop the transmission daemon before we can update the config file
		transmission_stop
		
		# Update the transmission config file
		log_text "Update $TRANSMISSION_SETTINGS_FILE"
		sed -i "/bind-address-ipv4/c\   \"bind-address-ipv4\": \"${VPN_IP}\"," $TRANSMISSION_SETTINGS_FILE

		# Start the transmission daemon again
		log_text "Starting transmission daemon again"
		transmission_start
	else
		log_text "No Transmission bind IP update required"
	fi
	
fi

log_text 0

