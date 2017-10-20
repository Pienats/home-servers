#!/usr/bin/env python3

import datetime
import os
import sys
import getopt
import configparser
import subprocess

import Network.interface as interface
import Network.vpn as vpnet

# Define some "constants"
ERROR = -1
SUCCESS = 0

localtime = datetime.datetime.now().time()

class GlobalState():
	basePath = os.curdir
	configFile = ""
	flexget_needed = False
	transmision_needed = False

	# Shared config
	initSystem = ""

	# VPN config
	vpnProvider = ""
	vpnInterface = ""
	vpnRoutingTable = ""
	vpnUser = ""
	vpnPingOne = False
	vpnMark = 0

	# Torrent config
	torrentAddedPath = ""
	torrentActivePath = ""
	# LAN config
	lanInterface = None
	lanGw=""


# file lists to manipulate later
added_torrents = []
pending_torrents = []
active_torrents = []

def routeGetInfo():
	'Get the system route info from the main routing table. Returns a list of routes'
	# Build route command
	cmd = ["route", "-n"]
	try:
		output = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
		outString = output.decode("utf-8")
		print("Route output:\n%s" % outString)

		outList = outString.split("\n")
		# The first 2 lines is text
		outList.remove(outList[0])
		outList.remove(outList[0])
		return outList
	except subprocess.CalledProcessError as cpe:
		outString = cpe.output.decode("utf-8")
		print("Route error: %d" % cpe.returncode)
		print("Exception Command output:\n%s" % outString)
	return None

def setGlobalLanInfo():
	'Find the default route in a list of routes'
	# Assume the default route is the one to 0.0.0.0
	routeList = routeGetInfo()
	if routeList is not None:
		for route in routeList:
			if (len(route) > 0):
				entry = route.split()
				if ((len(entry) > 0) and (entry[0] == "0.0.0.0")):
					GlobalState.lanInterface = interface.Interface(entry[7])
					GlobalState.lanGw = entry[1]
					print("\n\n\tLAN IF info: %s" % GlobalState.lanInterface.getNetworkParams())

def torrents_check():
	for f in os.listdir(GlobalState.torrentAddedPath):
		if f.endswith(".added"):
			added_torrents.append(f)
		elif f.endswith(".torrent"):
			pending_torrents.append(f)

	if (len(added_torrents) > 0):
		print("The following added torrents will now be deleted:")
		print(added_torrents)
		for f in added_torrents:
			full_path = GlobalState.torrentAddedPath+f
			os.remove(full_path)
	else:
		print("No added torrents to delete")

	if (len(pending_torrents) > 0):
		print("Pending torrents (we need to start transmission for these)")
		print(pending_torrents)
		GlobalState.transmision_needed = True
	else:
		print("No pending torrents (don't need to start transmission")

	for f in os.listdir(GlobalState.torrentActivePath):
		if f.endswith(".torrent"):
			active_torrents.append(f)

	if (len(active_torrents) > 0):
		print("Active torrents exist (we need to start transmission for thses)")
		GlobalState.transmision_needed = True

	return

def vpnSetRoutesAndRules():
	cmd = [GlobalState.basePath + "Network/vpn_route.sh",
			"-s", GlobalState.initSystem,
			"-l", GlobalState.lanInterface.getId(),
			"-g", GlobalState.lanGw,
			"-n", str(GlobalState.lanInterface.getNetworkParams()),
			"-p", GlobalState.vpnProvider,
			"-v", GlobalState.vpnInterface,
			"-m", GlobalState.vpnMark,
			"-t", GlobalState.vpnRoutingTable,
			"-u", GlobalState.vpnUser]

	#cmd = "Network/vpn_route.sh -s " + GlobalState.initSystem + " -l " + GlobalState.lanInterface.getId() + " -g " + GlobalState.lanGw + " -n " + str(GlobalState.lanInterface.getNetworkParams()) + " -p " + GlobalState.vpnProvider + " -v " + GlobalState.vpnInterface + " -m " + GlobalState.vpnMark + " -t " + GlobalState.vpnRoutingTable + " -u " + GlobalState.vpnUser

	print("Command to execute: %s" % cmd)

	try:
		output = subprocess.check_output(cmd)
		#output = subprocess.check_output(cmd, shell = True)
		outString = output.decode("utf-8")
		print(outString)
		return SUCCESS
	except subprocess.CalledProcessError as cpe:
		outString = cpe.output.decode("utf-8")
		print("Route error: %d" % cpe.returncode)
		print("Exception Command output:\n%s" % outString)
	return ERROR

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

			# Set routes and rules
			retVal = vpnSetRoutesAndRules()
			if (retVal == ERROR):
				print("Unable to set rules and route, aborting")
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

def printUsage(appName):
	print("\nUsage: %s [options]" % appName)
	print("Available Options:")
	print("  -b | --base-path     <base path>       Base path from where all scripts are accessible")
	print("  -c | --config        <config file>     Path to the configuration file to use for parameters")
	print("  -h | --help                            This help message")
	sys.exit()

def optionParsing(argv):
	print("Number of arguments: %d" % len(argv))
	print("Arguments: %s" % str(argv))
	try:
		opts, args = getopt.getopt(argv[1:], "b:c:h", ["base-path=","config=","help"])
	except getopt.GetoptError as goe:
		print(goe)
		printUsage(argv[0])

	for opt, arg in opts:
		print("opt: %s" % opt)
		if opt in ("-b", "--base-path"):
			print("Using base path %s" % arg)
			GlobalState.basePath = arg
		elif opt in ("-c", "--config"):
			print("Config file to use: %s" % arg)
			GlobalState.configFile = arg
		elif opt in ("-h", "--help"):
			printUsage(argv[0])

def configParseShared(sharedConfig):
	if 'InitSystem' in sharedConfig:
		GlobalState.initSystem = sharedConfig['InitSystem']
	else:
		print("Error: Provided config does not specify the init system")
		sys.exit(1)
	return

def configParseVpn(vpnConfig):
	print("VPN config:")
	if 'Provider' in vpnConfig:
		GlobalState.vpnProvider = vpnConfig['Provider']
	else:
		print("Error: Provided config does not specify the VPN provider")
		sys.exit(1)

	if 'Interface' in vpnConfig:
		GlobalState.vpnInterface = vpnConfig['Interface']
	else:
		print("Error: Provided config does not specify the VPN provider")
		sys.exit(1)

	if 'RoutingTable' in vpnConfig:
		GlobalState.vpnRoutingTable = vpnConfig['RoutingTable']
	else:
		print("Error: Provided config does not specify the VPN routing table")
		sys.exit(1)

	if 'User' in vpnConfig:
		GlobalState.vpnUser = vpnConfig['User']
	else:
		print("Error: Provided config does not specify the VPN user")
		sys.exit(1)

	if 'Mark' in vpnConfig:
		GlobalState.vpnMark = vpnConfig['Mark']
	else:
		GlobalState.vpnMark = 20

	if 'PingOne' in vpnConfig:
		GlobalState.vpnPingOne = vpnConfig['PingOne']
	else:
		GlobalState.vpnPingOne = False

def configParseTorrents(torrentConfig):
	print("Torrent config:")
	if 'AddedPath' in torrentConfig:
		GlobalState.torrentAddedPath = torrentConfig['AddedPath']
	else:
		print("Error: Provided config does not specify the torrents added path")
		sys.exit(1)

	if 'ActivePath' in torrentConfig:
		GlobalState.torrentActivePath = torrentConfig['ActivePath']
	else:
		print("Error: Provided config does not specify the active torrents path")
		sys.exit(1)

def getConfig(configFile):
	config = configparser.ConfigParser()
	try:
		config.read(configFile)
		if 'VPN' not in config.sections():
			print("Error: Provided config contains no VPN section")
			sys.exit(1)

		configParseShared(config['DEFAULT'])
		configParseVpn(config['VPN'])
		configParseTorrents(config['Torrents'])

	except configparser.ParsingError:
		print("Error parsing config file %s" % configFile)
		sys.exit(1)

######################################################################################
print("The current time is %d:%d" % (localtime.hour, localtime.minute))
optionParsing(sys.argv)
getConfig(GlobalState.configFile)

setGlobalLanInfo()

if (((localtime.hour % 2) == 0) and (localtime.minute < 5)):
	print ("Check flexget")
	GlobalState.flexget_needed = True

torrents_check()

print("\n")

if (GlobalState.flexget_needed or GlobalState.transmision_needed):
	print("We need to check/start the VPN interface")
	vpn = vpnet.VPN(GlobalState.vpnProvider, GlobalState.vpnInterface, GlobalState.initSystem, GlobalState.vpnPingOne)

	r = vpnCheck(vpn, 2)
	if (r == SUCCESS):
		print("VPN is good to go")
	else:
		print("VPN error, aborting")
		sys.exit(1);

	# Here the VPN can be concidered up and functional
	# TODO: run flexget (if needed)
	# TODO: start transmission (if needed)

else:
	print("Nothing needs the VPN, stop it if it is up")
	print("(but not yet actually doing so)")
	# TODO: stop transmission
	#vpn.stop()
