#!/usr/bin/env python3

import datetime
import os
#import Network.interface as net
import Network.vpn as vpnet

# Define some "constants"
ERROR = -1
SUCCESS = 0

TRANSMISSION_USER="werner"
TRANSMISSION_ADDED_DIR="/var/lib/werner-test/added/"
TRANSMISSION_ACTIVE_DIR="/var/lib/werner-test/config/torrents/"

localtime = datetime.datetime.now().time()

class GlobalState():
	flexget_needed = False
	transmision_needed = False

# file lists to manipulate later
added_torrents = []
pending_torrents =[]
active_torrents=[]

def torrents_check():
	for f in os.listdir(TRANSMISSION_ADDED_DIR):
		if f.endswith(".added"):
			added_torrents.append(f)
		elif f.endswith(".torrent"):
			pending_torrents.append(f)

	if (len(added_torrents) > 0):
		print("The following added torrents will now be deleted:")
		print(added_torrents)
		for f in added_torrents:
			full_path = TRANSMISSION_ADDED_DIR+f
			os.remove(full_path)
	else:
		print("No added torrents to delete")

	if (len(pending_torrents) > 0):
		print("Pending torrents (we need to start transmission for these)")
		print(pending_torrents)
		GlobalState.transmision_needed = True
	else:
		print("No pending torrents (don't need to start transmission")

	for f in os.listdir(TRANSMISSION_ACTIVE_DIR):
		if f.endswith(".torrent"):
			active_torrents.append(f)

	if (len(active_torrents) > 0):
		print("Active torrents exist (we need to start transmission for thses)")
		GlobalState.transmision_needed = True

	return

def vpnCheck(vpn, maxAttempts = 1):
	retVal = ERROR

	for attempt in range(0, maxAttempts):
		vpnStatus = vpn.getStatus()

		if (vpnStatus != vpnet.UP):
			print("VPN is down, starting it...")
			vpnStatus = vpn.start()

			if (vpnStatus != vpnet.UP):
				print("No active VPN connection, aborting")
				retVal = ERROR
				break

		# Here the VPN service should be up with the tunnel interface configured
		print("VPN appears up, getting info and pinging peer")
		vpn.getInfo()
		vpnStatus = vpn.pingPeer()

		if (vpnStatus != vpnet.UP):
			print("Unable to ping VPN peer")
			retVal = ERROR
			vpn.stop() # Restart VPN to get a better connection
			continue

		retVal = SUCCESS
		break # Reaching this point means the VPN is up and connected

	if (retVal == ERROR):
		vpn.stop()
	return retVal



print("The current time is %d:%d" % (localtime.hour, localtime.minute))

if (((localtime.hour % 2) == 0) and (localtime.minute < 5)):
	print ("Check flexget")
	GlobalState.flexget_needed = True
	# TODO: expand to run flexget (or at least set flag that it should be run)

torrents_check()

print("\n")

if (GlobalState.flexget_needed or GlobalState.transmision_needed):
	print("We need to check/start the VPN interface")

	#vpn = vpnet.VPN("vpnarea", "tun0", "openRC", True)
	vpn = vpnet.VPN("ctwduvel", "tun25", "openRC", True)

	r = vpnCheck(vpn, 2)
	if (r == SUCCESS):
		print("VPN is good to go")
	else:
		print("VPN error, aborting")
		sys.exit(1);


else:
	print("Nothing needs the VPN, stop it if it is up")
	print("(but not yet actually doing so)")
#vpn.stop()
