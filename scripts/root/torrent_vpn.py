#!/usr/bin/env python3

import datetime
import time
import os
import sys
import getopt
import configparser
import subprocess

import Service.service as service
import Network.interface as interface
import Network.vpn as vpnet
#import Torrent.transmission as transmission

# Define some "constants"
ERROR = -1
SUCCESS = 0

currentDate = datetime.datetime.now()
currentTime = datetime.datetime.now().time()

class GlobalState:
	testMode = False
	verbose = False
	basePath = os.curdir
	configFile = ""

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
	torrentHomePath = ""
	torrentAddedPath = ""
	torrentActivePath = ""
	torrentConfigFile = ""
	torrentDaemonName = ""

	# Flexget
	flexgetBin = ""

	# LAN config
	lanInterface = None
	lanGw = ""


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
					if (GlobalState.verbose):
						print("\n\n\tLAN IF info: %s" % GlobalState.lanInterface.getNetworkParams())

def torrentsClearAdded():
	for f in os.listdir(GlobalState.torrentAddedPath):
		if f.endswith(".added"):
			added_torrents.append(f)

	if (len(added_torrents) > 0):
		print("The following added torrents will now be deleted:")
		for f in added_torrents:
			full_path = GlobalState.torrentAddedPath+"/"+f
			print(full_path)
			os.remove(full_path)
	elif (GlobalState.verbose):
		print("No added torrents to delete")

def needFlexget():
	if (GlobalState.testMode):
		return True

	if (((currentTime.hour % 2) == 0) and (currentTime.minute < 5)):
		if (GlobalState.verbose):
			print("Flexget needs to be called")
		return True
	return False

def needTransmission():
	for f in os.listdir(GlobalState.torrentAddedPath):
		if f.endswith(".torrent"):
			pending_torrents.append(f)

	for f in os.listdir(GlobalState.torrentActivePath):
		if f.endswith(".torrent"):
			active_torrents.append(f)

	if ((len(pending_torrents) > 0) or (len(active_torrents) > 0)):
		if (GlobalState.verbose):
			print("Pending or active torrents present (we need to start transmission for these)")
			print(pending_torrents)
		return True
	elif (GlobalState.verbose):
		print("No pending or active torrents (don't need to start transmission)")
	return False

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

	#print("Command to execute: %s" % cmd)

	try:
		output = subprocess.check_output(cmd)
		#output = subprocess.check_output(cmd, shell = True)
		outString = output.decode("utf-8")
		if (GlobalState.verbose):
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
			if (GlobalState.verbose):
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
		if (GlobalState.verbose):
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
	print("  -h | --help                            This help message")
	print("  -b | --base-path     <base path>       Base path from where all scripts are accessible")
	print("  -c | --config        <config file>     Path to the configuration file to use for parameters")
	print("  -t | --test                            Enable test mode (automatically lets certain checks return true")
	print("  -v | --verbose                         Enable verbose mode")
	sys.exit()

def optionParsing(argv):
	try:
		opts, args = getopt.getopt(argv[1:], "hb:c:tv", ["help","base-path=","config=","test","verbose"])
	except getopt.GetoptError as goe:
		print(goe)
		printUsage(argv[0])

	for opt, arg in opts:
		if opt in ("-h", "--help"):
			printUsage(argv[0])
		elif opt in ("-b", "--base-path"):
			if (GlobalState.verbose):
				print("Using base path %s" % arg)
			GlobalState.basePath = arg
		elif opt in ("-c", "--config"):
			if (GlobalState.verbose):
				print("Config file to use: %s" % arg)
			GlobalState.configFile = arg
		elif opt in ("-t", "--test"):
			if (GlobalState.verbose):
				print("Test mode enabled")
			GlobalState.testMode = True
		elif opt in ("-v", "--verbose"):
			if (GlobalState.verbose):
				print("verbose mode enabled")
			GlobalState.verbose = True

def configParseShared(sharedConfig):
	if 'InitSystem' in sharedConfig:
		GlobalState.initSystem = sharedConfig['InitSystem']
	else:
		print("Error: Provided config does not specify the init system")
		sys.exit(1)
	return

def configParseVpn(vpnConfig):
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
	if 'HomePath' in torrentConfig:
		GlobalState.torrentHomePath = torrentConfig['HomePath']
	else:
		print("Error: Provided config does not specify the torrents home path")
		sys.exit(1)

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

	if 'ConfigFile' in torrentConfig:
		GlobalState.torrentConfigFile = torrentConfig['ConfigFile']
	else:
		print("Error: Provided config does not specify the daemon name")
		sys.exit(1)

	if 'DaemonName' in torrentConfig:
		GlobalState.torrentDaemonName = torrentConfig['DaemonName']
	else:
		print("Error: Provided config does not specify the daemon name")
		sys.exit(1)

def configParseFlexget(torrentConfig):
	if 'FlexgetBin' in torrentConfig:
		GlobalState.flexgetBin = torrentConfig['FlexgetBin']
	else:
		print("Error: Provided config does not specify the Flexget binary location")
		sys.exit(1)

def getConfig(configFile):
	config = configparser.ConfigParser(interpolation=configparser.ExtendedInterpolation())
	try:
		config.read(configFile)
		# WHD: It seems like DEFAULT is not included in the sections list
		#if 'DEFAULT' not in config.sections():
			#print("Error: Provided config contains no default section")
			#sys.exit(1)

		if 'VPN' not in config.sections():
			print("Error: Provided config contains no VPN section")
			sys.exit(1)

		if 'Torrents' not in config.sections():
			print("Error: Provided config contains no torrents section")
			sys.exit(1)

		if 'Flexget' not in config.sections():
			print("Error: Provided config contains no Flexget section")
			sys.exit(1)

		configParseShared(config['DEFAULT'])
		configParseVpn(config['VPN'])
		configParseTorrents(config['Torrents'])
		configParseFlexget(config['Flexget'])

	except configparser.ParsingError:
		print("Error parsing config file %s" % configFile)
		sys.exit(1)

def flexgetRun():
	#flexgetCmd = "%s --test execute" % GlobalState.flexgetBin
	flexgetCmd = "%s --cron execute" % GlobalState.flexgetBin
	cmd = ["su", "-l", GlobalState.vpnUser, "-s", "/bin/bash", "-c", flexgetCmd]
	#cmd = ["ls", "-lah", GlobalState.flexgetBin]
	if (GlobalState.verbose):
		print("Flexget: command to execute")
		print(cmd)
	try:
		output = subprocess.check_output(cmd)
		outString = output.decode("utf-8")
		if (GlobalState.verbose):
			print(outString)
		return SUCCESS
	except subprocess.CalledProcessError as cpe:
		outString = cpe.output.decode("utf-8")
		print("Route error: %d" % cpe.returncode)
		print("Exception Command output:\n%s" % outString)
	return ERROR
	#return SUCCESS

def transmissionUpdateBindIp(transmissionService, configFile, vpnIp):
	""" Updates the Transmission IPv4 bind address (if necessary)
	@param configFile	Transmission configuration file
	@param vpnIp		The current VPN IP

	@return ERROR on failure, SUCCESS otherwise
	"""

	if (GlobalState.verbose):
		print("VPN IP: %s" % vpnIp)
	try:
		with open(configFile, 'r') as config:
			data = config.readlines()
	except FileNotFoundError as fnfe:
		print("File %s not found" % configFile)
		return ERROR

	idx = 0
	while idx < len(data):
	#for line in data:
		line = data[idx]

		if "bind-address-ipv4" in line:
			#tmp = line.split()
			bindIp = line.split()[1].strip('",')
			if (GlobalState.verbose):
				print("Bind IPv4: %s" % bindIp)
			if (bindIp == vpnIp):
				print("No Transmission IPv4 bind address update required")
				return SUCCESS
			else:
				print("Current and stored IPs do not match, update required")
				# Stop the transmission service
				while (transmissionService.getStatus() == service.RUNNING):
					transmissionService.stop()
					# Give the service time to stop
					currentTime.sleep(1)

				# Update the configured IPv4 bind address
				data[idx] = "    \"bind-address-ipv4\": \""+ vpnIp +"\",\n"

		else:
			newLine = line
		idx += 1

	# Wrtie back the data to the file
	with open(configFile, 'w') as config:
		config.writelines(data)

	return SUCCESS

######################################################################################
print("The current date is %d-%d-%d" % (currentDate.year, currentDate.month, currentDate.day ))
print("The current time is %d:%d" % (currentTime.hour, currentTime.minute))
optionParsing(sys.argv)
getConfig(GlobalState.configFile)

setGlobalLanInfo()

print("\n")

currentTorrents = False

vpn = vpnet.VPN(GlobalState.vpnProvider, GlobalState.vpnInterface, GlobalState.initSystem, GlobalState.vpnPingOne)
transmission = service.Service(GlobalState.torrentDaemonName, GlobalState.initSystem)

if (needFlexget() or needTransmission()):
	print("VPN connection is needed")

	r = vpnCheck(vpn, 2)
	if (r == SUCCESS):
		print("VPN is good to go")
	else:
		print("VPN error, aborting")
		sys.exit(1);

# Here the VPN can be concidered up and functional
if (needFlexget()):
	flexgetRun()

# TODO: start transmission (if needed)
if (needTransmission()):
	currentTorrents = True
	# TODO:
	# * Validate transmission bind IP against VPN IP
	#	- If it differs:
	#		+ Stop transmission
	#		+ Update config to bind to VPN address
	# * If transmission stopped
	#	- Start transmission
	if (transmissionUpdateBindIp(transmission, GlobalState.torrentConfigFile, vpn.getAddr()) == SUCCESS):
		print("Transmission bind IP is OK")
	else:
		print("Error with Transmission bind IP, aborting")
		sys.exit(1)

	if (transmission.getStatus() == service.STOPPED):
		print("Starting Transmission service")
		transmission.start()
		# If Transmission service fails to start, there is probably nothing we can do at this point
		# So don't test for it, just fall through and catch any error output in the log

if (not currentTorrents):
	print("No current torrents\nStop the torrent daemon and VPN")
	transmission.stop()
	vpn.stop()

# Clear any already added torrents
torrentsClearAdded()
