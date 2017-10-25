#!/usr/bin/env python3

import datetime
import time
import os
import sys
import getopt
import configparser
import subprocess
import logging

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
	"""
	Class to keep global state
	"""
	testMode = False
	verbose = False
	basePath = os.curdir
	logFile = "/dev/shm/torrent_vpn.log"
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

def printUsage(appName):
	"""
	Print script usage
	"""
	print("\nUsage: %s [options]" % appName)
	print("Available Options:")
	print("  -h | --help                            This help message")
	print("  -b | --base-path     <base path>       Base path from where all scripts are accessible")
	print("  -c | --config        <config file>     Path to the configuration file to use for parameters")
	print("  -l | --log           <log file>        File to log to (defaults to %s)" % (GlobalState.logFile))
	print("  -t | --test                            Enable test mode (automatically lets certain checks return true")
	print("  -v | --verbose                         Enable verbose mode")
	sys.exit()

def parseCommandLine(argv):
	"""
	Parse command line options
	@param argv Argument vector to pass
	No return value, but GlobalState members are set
	"""
	try:
		opts, args = getopt.getopt(argv[1:], "hb:c:l:tv", ["help","base-path=","config=","log=","test","verbose"])
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
		elif opt in ("-l", "--log"):
			if (GlobalState.verbose):
				print("Log file to use: %s" % arg)
			GlobalState.logFile = arg
		elif opt in ("-t", "--test"):
			if (GlobalState.verbose):
				print("Test mode enabled")
			GlobalState.testMode = True
		elif opt in ("-v", "--verbose"):
			if (GlobalState.verbose):
				print("verbose mode enabled")
			GlobalState.verbose = True

def getRouteInfo():
	"""
	Get the system route info from the main routing table. Returns a list of routes
	@return None on error, route list otherwise
	"""
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

def setLanInfo():
	"""
	Find the default route in a list of routes
	Does not return anything, but sets the GlobalState LAN members based on the default route
	"""
	# Assume the default route is the one to 0.0.0.0
	routeList = getRouteInfo()
	if routeList is not None:
		for route in routeList:
			if (len(route) > 0):
				entry = route.split()
				if ((len(entry) > 0) and (entry[0] == "0.0.0.0")):
					GlobalState.lanInterface = interface.Interface(entry[7])
					GlobalState.lanGw = entry[1]
					if (GlobalState.verbose):
						print("\n\n\tLAN IF info: %s" % GlobalState.lanInterface.getNetworkParams())

def torrentsClearProcessed():
	"""
	Clear all torrents marked as 'added'
	(Note that these are torrents 'added' by Transmission, thus consumed from the
	 Flexget 'added' directory)
	At this stage, this function is Transmission specific
	"""
	for f in os.listdir(GlobalState.torrentAddedPath):
		if f.endswith(".added"):
			added_torrents.append(f)

	if (len(added_torrents) > 0):
		logging.info("Torrents: Clearing processed torrents")
		if (GlobalState.verbose):
			print("The following processed torrents will now be deleted:")
		for f in added_torrents:
			full_path = GlobalState.torrentAddedPath+"/"+f
			print(full_path)
			os.remove(full_path)
	elif (GlobalState.verbose):
		print("No added torrents to delete")

def needFlexget():
	"""
	Determine if Flexget should be run based on the time interval
	@return True if Flexget should be run, False otherwise
	"""
	if (GlobalState.testMode):
		return True

	if (((currentTime.hour % 2) == 0) and (currentTime.minute < 5)):
		logging.info("Flexget needs to be run")
		if (GlobalState.verbose):
			print("Flexget needs to be run")
		return True
	return False

def needTorrentClient():
	"""
	Determine if the torrenting client is needed based on new/active torrents
	@return True if torrenting client is needed, False otherwise
	"""
	for f in os.listdir(GlobalState.torrentAddedPath):
		if f.endswith(".torrent"):
			pending_torrents.append(f)

	for f in os.listdir(GlobalState.torrentActivePath):
		if f.endswith(".torrent"):
			active_torrents.append(f)

	if ((len(pending_torrents) > 0) or (len(active_torrents) > 0)):
		logging.info("Torrent client needs to be run")
		if (GlobalState.verbose):
			print("Pending or active torrents present (we need to start torrent client for these)")
		return True
	elif (GlobalState.verbose):
		print("No pending or active torrents (don't need to start torrent client)")
	logging.info("Torrent client not needed")
	return False

def vpnSetRoutesAndRules():
	"""
	Set the VPN routes, rules and iptables entries based on configured parameters
	"""
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

	if (GlobalState.verbose):
		print("Command to execute: %s" % cmd)

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
	"""
	Check the VPN state and attempt to start it if necessary
	@param vpn VPN object to check & start
	@param maxAttempts The maximum number of attempts to start the VPN before giving up (defaults to 1)

	@return ERROR on failure, SUCCESS otherwise
	"""
	retVal = ERROR

	for attempt in range(0, maxAttempts):
		try:
			vpnStatus = vpn.getStatus()
		except vpnet.VPNError as ve:
			msg = ''.join(ve.args)
			logging.info("Exception occured while checking VPN status: %s" % (msg))
			if (GlobalState.verbose):
				print("Exception occured while checking VPN status: %s" % (msg))
			return ERROR

		if (vpnStatus != vpnet.UP):
			logging.info("Attempting to start VPN [%d/%d]" % (attempt, maxAttempts))
			if (GlobalState.verbose):
				print("VPN is down, starting it...")

			if (GlobalState.initSystem == "openRC"):
				vpnStatus = vpn.start()
			else:
				vpnStatus = vpn.start(5,5) # systemd might not be ready immediately

			if (vpnStatus != vpnet.UP):
				logging.info("VPN: failed to start on attempt %d of %d, aborting" % (attempt, maxAttempts))
				if (GlobalState.verbose):
					print("VPN failed to start on attempt %d of %d, aborting" % (attempt, maxAttempts))
				retVal = ERROR
				break

			# Set routes and rules
			retVal = vpnSetRoutesAndRules()
			if (retVal == ERROR):
				logging.info("VPN: failed to set rules and route on attempt %d of %d, aborting" % (attempt, maxAttempts))
				if (GlobalState.verbose):
					print("VPN failed to set rules and route on attempt %d of %d, aborting" % (attempt, maxAttempts))
				break

		# Here the VPN service should be up with the tunnel interface configured
		if (GlobalState.verbose):
			print("VPN appears up, getting info and pinging peer")
		vpn.updateInfo()
		vpnStatus = vpn.pingPeer()

		if (vpnStatus != vpnet.UP):
			logging.info("VPN: Failed to ping peer")
			if (GlobalState.verbose):
				print("Unable to ping VPN peer")
			retVal = ERROR
			vpn.stop() # Restart VPN to get a better connection
			continue

		# Reaching this point means the VPN is up and connected
		logging.info("VPN: Active and functional")
		retVal = SUCCESS
		break

	if (retVal == ERROR):
		vpn.stop()
	return retVal

def configParseShared(sharedConfig):
	"""
	Parse shared configuration
	@param sharedConfig Shared configuration dictionary as extracted from the supplied configuration file

	Nothing is returned, but GlobalState members are set
	"""
	if 'InitSystem' in sharedConfig:
		GlobalState.initSystem = sharedConfig['InitSystem']
	else:
		print("Error: Provided config does not specify the init system")
		sys.exit(1)
	return

def configParseVpn(vpnConfig):
	"""
	Parse VPN configuration
	@param vpnConfig VPN configuration dictionary as extracted from the supplied configuration file

	Nothing is returned, but GlobalState members are set
	"""
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
	"""
	Parse Torrent configuration
	@param torrentConfig Torrent configuration dictionary as extracted from the supplied configuration file

	Nothing is returned, but GlobalState members are set
	"""
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

def configParseFlexget(flexgetConfig):
	"""
	Parse Flexget configuration
	@param flexgetConfig Flexget configuration dictionary as extracted from the supplied configuration file

	Nothing is returned, but GlobalState members are set
	"""
	if 'FlexgetBin' in flexgetConfig:
		GlobalState.flexgetBin = flexgetConfig['FlexgetBin']
	else:
		print("Error: Provided config does not specify the Flexget binary location")
		sys.exit(1)

def getConfig(configFile):
	"""
	Parse the configuration file
	@param configFile configuration file to parse

	Nothing is returned, but GlobalState members are set by sub-config parsing functions
	"""

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
	"""
	Run the Flexget application to find and download new torrent files

	@return ERROR on failure, SUCCESS otherwise
	"""
	if (GlobalState.testMode):
		flexgetCmd = "%s --test execute" % GlobalState.flexgetBin
	else:
		flexgetCmd = "%s --cron execute" % GlobalState.flexgetBin

	cmd = ["su", "-l", GlobalState.vpnUser, "-s", "/bin/bash", "-c", flexgetCmd]
	#cmd = ["ls", "-lah", GlobalState.flexgetBin]
	if (GlobalState.verbose):
		print("Flexget: command to execute")
		print(cmd)
	try:
		logging.info("Flexget: running...")
		output = subprocess.check_output(cmd)
		outString = output.decode("utf-8")
		logging.info("Flexget: completed")
		if (GlobalState.verbose):
			print(outString)
		return SUCCESS
	except subprocess.CalledProcessError as cpe:
		outString = cpe.output.decode("utf-8")
		logging.info("Flexget: Error %d" % cpe.returncode)
		logging.info("Flexget: Exception Command output:\n%s" % outString)
		if (GlobalState.verbose):
			print("Flexget error: %d" % cpe.returncode)
			print("Exception Command output:\n%s" % outString)
	return ERROR

def transmissionUpdateBindIp(transmissionService, configFile, vpnIp):
	"""
	Update the Transmission IPv4 bind address (if necessary)
	@param configFile Transmission configuration file
	@param vpnIp The current VPN IP

	@return ERROR on failure, SUCCESS otherwise
	"""
	logging.info("Transmission: VPN IP: %s" % vpnIp)
	if (GlobalState.verbose):
		print("VPN IP: %s" % vpnIp)
	try:
		with open(configFile, 'r') as config:
			data = config.readlines()
	except FileNotFoundError as fnfe:
		logging("Transmission: File %s not found" % configFile)
		if (GlobalState.verbose):
			print("File %s not found" % configFile)
		return ERROR

	idx = 0
	while idx < len(data):
		line = data[idx]

		if "bind-address-ipv4" in line:
			#tmp = line.split()
			bindIp = line.split()[1].strip('",')
			logging.info("Transmission: Bind IPv4: %s" % bindIp)
			if (GlobalState.verbose):
				print("Bind IPv4: %s" % bindIp)
			if (bindIp == vpnIp):
				logging.info("Transmission: No Transmission IPv4 bind address update required")
				if (GlobalState.verbose):
					print("No Transmission IPv4 bind address update required")
				return SUCCESS
			else:
				logging.info("Transmission: Current and stored IPs do not match, update required")
				if (GlobalState.verbose):
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

	logging.info("Transmission: IPv4 bind address update")
	return SUCCESS

######################################################################################
def main():
	parseCommandLine(sys.argv)
	getConfig(GlobalState.configFile)

	# Start log
	logging.basicConfig(filename = GlobalState.logFile, level = logging.INFO)

	curDate = "%04d-%02d-%02d" % (currentDate.year, currentDate.month, currentDate.day)
	curTime = "%02d:%02d" % (currentTime.hour, currentTime.minute)

	logging.info("========================================================================")
	logging.info("%s - %s" % (curDate, curTime))

	if (GlobalState.verbose):
		print("The current date is %s" % (curDate))
		print("The current time is %s" % (curTime))

	setLanInfo()

	currentTorrents = False

	try:
		vpn = vpnet.VPN(GlobalState.vpnProvider, GlobalState.vpnInterface, GlobalState.initSystem, GlobalState.vpnPingOne, GlobalState.verbose)
		transmission = service.Service(GlobalState.torrentDaemonName, GlobalState.initSystem, GlobalState.verbose)
	except vpnet.VPNError as ve:
		msg = ''.join(ve.args)
		logging.info("VPN exception occured: %s" % (msg))
		if (GlobalState.verbose):
			print("VPN exception occured: %s" % (msg))
		sys.exit(1)
	except service.ServiceError as se:
		msg = ''.join(se.args)
		logging.info("Service exception occured: %s" % (msg))
		if (GlobalState.verbose):
			print("Service exception occured: %s" % (msg))
		sys.exit(1)

	if (needFlexget() or needTorrentClient()):
		logging.info("VPN: connection is needed")
		if (GlobalState.verbose):
			print("VPN connection is needed")

		r = vpnCheck(vpn, 2)
		if (r == SUCCESS):
			if (GlobalState.verbose):
				print("VPN is good to go")
		else:
			if (GlobalState.verbose):
				print("VPN error, aborting")
			sys.exit(1);

	# Here the VPN can be concidered up and functional
	if (needFlexget()):
		flexgetRun()

	if (needTorrentClient()):
		currentTorrents = True
		if (transmissionUpdateBindIp(transmission, GlobalState.torrentConfigFile, vpn.getAddr()) == SUCCESS):
			if (GlobalState.verbose):
				print("Transmission bind IP is OK")
		else:
			logging.info("Transmission: Error with bind IP, aborting")
			if (GlobalState.verbose):
				print("Error with Transmission bind IP, aborting")
			sys.exit(1)

		if (transmission.getStatus() == service.STOPPED):
			logging.info("Transmission: Starting Transmission service")
			if (GlobalState.verbose):
				print("Starting Transmission service")
			transmission.start()
			# If Transmission service fails to start, there is probably nothing we can do at this point
			# So don't test for it, just fall through and catch any error output in the log

	if (not currentTorrents):
		logging.info("Transmission: No current torrents; Stop the torrent daemon and VPN")
		if (GlobalState.verbose):
			print("No current torrents\nStop the torrent daemon and VPN")
		transmission.stop()
		vpn.stop()

	# Clear any already added torrents
	torrentsClearProcessed()
	logging.info("")


if __name__ == '__main__':
	main()
