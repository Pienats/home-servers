import subprocess
import logging
import time

import Network.interface as interface
import Service.service as service

DOWN = -1
UP = 0

KEY_ADDR = 'addr'
KEY_PEER = 'peer'
KEY_PING = 'ping'

class VPNError(RuntimeError):
	"""
	VPN related exception
	"""
	def __init__(self, arg):
		self.args = arg

class VPN:
	"""
	Class to represent VPN connections
	VPNs for the purpose of this application has two main components:
	* Network interface (Communication interface; endpoint of encrypted tunnel)
	* System service (Allows the OS to start/stop the VPN and retrieve basic status)
	"""
	def __init__(self, provider, ifId, initSystem, pingOne = False, verbose = False):
		"""
		Constructor
		@param provider VPN provider
		@param ifId Interface identifier used by the OS to identify the VPN network interface
		@param initSystem The init system in use by the OS
		@param pingOne Indicates that the x.x.x.1 IP should be pinged to test connectivity, instead of the tunnel peer
		@param verbose Indicate whether or not verbose mode should be used
		"""
		self.provider = provider
		self.ifId = ifId
		self.initSystem = initSystem
		self.pingOne = pingOne
		self.ifParams = {}
		self.verbose = verbose

		try:
			if (self.initSystem == "openRC"):
				self.service = service.Service("openvpn." + self.provider, self.initSystem, self.verbose)
			elif (self.initSystem == "systemd"):
				self.service = service.Service("openvpn@" + self.provider, self.initSystem, self.verbose)
			else:
				logging.info("VPN: Unsupported init system type %s" % (self.initSystem))
				if (self.verbose):
					print("Unsupported init system type: %s" % (self.initSystem))
				msg = "Unsupported init system type: %s" % (self.initSystem)
				raise VPNError(msg)
		except service.ServiceError as se:
			srvMsg = ''.join(se.args)
			logging.info("VPN: service error: %s" % (srvMsg))
			if (self.verbose):
				print("VPN: service error: %s" % (srvMsg))
			msg = "Service error occured: %s" %  (srvMsg)
			raise VPNError(msg)

		self.vpnIf = interface.Interface(self.ifId, verbose)
		return

	def getStatus(self):
		"""
		Retrieve the VPN status
		Get status is somewhat ambiguous, as it means:
		1) The VPN service is started
		2) The connection is active and functional

		@return UP if the VPN is active and functional, DOWN otherwise
		"""
		# First try to find out if the service has started
		try:
			status = self.service.getStatus()
		except service.ServiceError as se:
			srvMsg = ''.join(se.args)
			logging.info("VPN: service error: %s" % (srvMsg))
			if (self.verbose):
				print("VPN: service error: %s" % (srvMsg))
			msg = "Service error occured: %s" %  (srvMsg)
			raise VPNError(msg)

		if (status == service.RUNNING):
			if (self.verbose):
				print("VPN Service is running")
			ifStatus = self.vpnIf.getStatus()
			if (ifStatus == interface.UP):
				if (self.verbose):
					print("VPN interface is up")
				return UP
			else:
				logging.info("VPN: Interface is not available")
				if (self.verbose):
					print("VPN interface is not available")
				self.service.stop()
		else:
			if (self.verbose):
				print("VPN service is not running")
			self.service.stop() # Make sure service is stopped
		return DOWN

	def start(self, ifAttempts = 1, ifWaitTime = 1):
		"""
		Start the VPN

		@return UP if VPN is active and functional, DOWN otherwise
		"""
		logging.info("VPN: Starting...")
		status = self.service.start(5, 5)
		if (status == service.RUNNING):
			logging.info("VPN: Started")

			for cnt in range(0, ifAttempts):
				ifStatus = self.vpnIf.getStatus()
				if (ifStatus == interface.UP):
					return UP
				else:
					time.sleep(ifWaitTime)

			logging.info("VPN: Interface not available")
			if (self.verbose):
				print("VPN: Interface not available")
			self.service.stop() # Make sure service is stopped
		else:
			logging.info("VPN: Service failed to start")
			if (self.verbose):
				print("VPN: Service failed to start")
			# To make sure a "long to start up" service isn't creating a stale
			# entry, stop the service
			self.service.stop()
		#self.service.stop()
		return

	def stop(self):
		"""
		Stop the VPN service
		"""
		logging.info("VPN: Stopping")
		self.service.stop()

	def updateInfo(self):
		"""
		Update VPN information based on tunnel interface
		"""
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
			logging.info("VPN: Need to ping gateway with last IP octet == 1")
			peer = self.ifParams[KEY_PEER]
			peerComps = peer.split('.')
			reconstPeer = peerComps[0] + "." + peerComps[1] + "." + peerComps[2] + ".1"
			if (self.verbose):
				print("Reconstituted peer: %s" % reconstPeer)
			self.ifParams[KEY_PING] = reconstPeer

	def pingPeer(self):
		"""
		Ping the tunnel peer

		@return UP if VPN is active and functional, DOWN otherwise
		"""
		if (len(self.ifParams) == 0):
			logging.info("No interface parameters available")
			if (self.verbose):
				print("No interface parameters available")
			return

		cmd = ["ping", "-c 1", self.ifParams[KEY_PING]]
		if (self.verbose):
			print("Command to execute [%d]: %s" % (len(cmd), cmd))
		try:
			logging.info("VPN: Attempting to ping %s" % (self.ifParams[KEY_PING]))
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
		"""
		Retrieve the VPN tunnel IP address

		@return The VPN tunnel IP address
		"""
		return self.ifParams[KEY_ADDR]
