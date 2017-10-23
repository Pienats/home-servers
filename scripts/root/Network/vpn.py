
import subprocess

import Network.interface as interface
import Service.service as service

DOWN = -1
UP = 0

KEY_ADDR = 'addr'
KEY_PEER = 'peer'
KEY_PING = 'ping'

class VPN:
	def __init__(self, provider, ifId, initSystem, pingOne = False, verbose = False):
		self.provider = provider
		self.ifId = ifId
		self.initSystem = initSystem
		self.pingOne = pingOne
		self.ifParams = {}
		self.verbose = verbose

		if ( initSystem == "openRC"):
			self.service = service.Service("openvpn." + self.provider, self.initSystem, self.verbose)
			self.vpnIf = interface.Interface(self.ifId, verbose)
		else:
			print("Unsupported start system type: %s" % initSystem)
			# TODO: throw exception
		# TODO: catch and handle/rethrow any exceptions
		return

	def getStatus(self):
		# Get status is somewhat ambiguous, as it means:
		# 1) The VPN service is started
		# 2) The connection is active and functioning

		# First try to find out if the service has started
		status = self.service.getStatus()
		if (status == service.RUNNING):
			print("VPN Service is running")
			ifStatus = self.vpnIf.getStatus()
			if (ifStatus == interface.UP):
				print("VPN interface is up")
				return UP
			else:
				print("VPN interface is not available")
				self.service.stop()
		else:
			print("VPN service is not running")
			self.service.stop() # Make sure service is stopped
		return DOWN

	def start(self):
		status = self.service.start(5, 5)
		if (status == service.RUNNING):
			#do stuff
			ifStatus = self.vpnIf.getStatus()
			if (ifStatus == interface.UP):
				print("VPN service is running")
				return UP
			else:
				print("Error starting VPN")
				self.service.stop() # Make sure service is stopped
		else:
			print("Service failed to start")
			# To make sure a "long to start up" service isn't creating a stale
			# entry, stop the service
			self.service.stop()
		#self.service.stop()
		return

	def stop(self):
		self.service.stop()

	def getInfo(self):
		self.ifParams = self.vpnIf.getTunnelParams()
		if (len(self.ifParams) == 0):
			print("No interface parameters available")
			return

		if (self.verbose):
			print("Interface parameters:")
			print("Addr: %s" % self.ifParams[KEY_ADDR])
			print("Peer: %s" % self.ifParams[KEY_PEER])

		if not self.pingOne:
			self.ifParams[KEY_PING] = self.ifParams[KEY_PEER]
		else:
			peer = self.ifParams[KEY_PEER]
			peerComps = peer.split('.')
			reconstPeer = peerComps[0] + "." + peerComps[1] + "." + peerComps[2] + ".1"
			if (self.verbose):
				print("Reconstituted peer: %s" % reconstPeer)
			self.ifParams[KEY_PING] = reconstPeer

	def pingPeer(self):
		if (len(self.ifParams) == 0):
			print("No interface parameters available")
			return

		cmd = ["ping", "-c 1", self.ifParams[KEY_PING]]
		if (self.verbose):
			print("Command to execute [%d]: %s" % (len(cmd), cmd))
		try:
			output = subprocess.check_output(cmd)
			if (self.verbose):
				outString = output.decode("utf-8")
				print("Command output:\n%s" % outString)
			return UP
		except subprocess.CalledProcessError as cpe:
			outString = cpe.output.decode("utf-8")
			print("Service status error: %d" % cpe.returncode)
			print("Exception Command output:\n%s" % outString)
			return DOWN

	def getAddr(self):
		return self.ifParams[KEY_ADDR]
