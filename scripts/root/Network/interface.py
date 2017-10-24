
import subprocess
import netifaces
import ipaddress
import logging

# Some "Constant" values
UP = 1
DOWN = 0

KEY_ADDR = 'addr'
KEY_PEER = 'peer'
KEY_NETMASK = 'netmask'

class Interface:
	"""
	Class to represent a system network interface
	"""
	status = DOWN

	def __init__(self, ifId, verbose = False):
		"""
		Constructor
		@param ifId Interface identifier
		@param verbose Indicate whether or not verbose mode should be used
		"""
		self.ifId = ifId
		self.verbose = verbose
		self.addrType = netifaces.AF_INET # We are interested in IPv4 addresses

	def getId(self):
		"""
		Retrieve the interface identifier

		@return The interface identifier
		"""
		return self.ifId

	def getStatus(self):
		"""
		Retrieve the interface status

		@return UP if the interface is configured, DOWN otherwise
		"""
		availableIfs = netifaces.interfaces()

		if self.ifId in availableIfs:
			if (self.verbose):
				print("Interface %s is available" % (self.ifId))
			return UP
		elif (self.verbose):
			print("Interface %s not available" % (self.ifId))
		return DOWN

	def getTunnelParams(self):
		"""
		Retrieve the interface tunnel parameters (if applicable)

		@return dictionary of tunnel parameters
		@throws TODO: exception if interface is not a tunnel
		"""
		if (self.verbose):
			print("Retrieving tunnel parameters")
		# TODO: Test if interface ifId contains "tun", throw exception if not

		# Tunnels have the following parameters of interest:
		# * addr
		# * peer
		addrTypes = netifaces.ifaddresses(self.ifId)
		if (self.addrType in addrTypes):
			addrList = addrTypes[self.addrType]
			addr = addrList[0] # Assume the entry we want is the first list entry
			if (KEY_ADDR not in addr):
				logging.info("Interface: %s does not have an address" % (self.ifId))
				if (self.verbose):
					print("Interface %s does not have an address" % (self.ifId))
				return {}

			if (KEY_PEER not in addr):
				logging.info("Interface: %s does not contain a peer address" % (self.ifId))
				if (self.verbose):
					print("Interface %s does not contain a peer address" % (self.ifId))
				return {}

			return addr

		else:
			logging.info("Interface: %s: Key type %d not found in available address types" % (self.ifId, self.addrType))
			if (self.verbose):
				print("Key type %d not found in available address types" % (self.addrType))

	def getNetworkParams(self):
		"""
		Retrieve network parameters

		@return Network parameters
		@throws TODO: exception if interface is a tunnel
		"""
		if (self.verbose):
			print("Retrieving tunnel parameters")
		# TODO: Test if interface ifId contains "tun", throw exception if it does

		# Normal interfaces have the following parameters of interest:
		# * addr
		# * netmask
		addrTypes = netifaces.ifaddresses(self.ifId)
		if (self.addrType in addrTypes):
			addrList = addrTypes[self.addrType]
			addr = addrList[0] # Assume the entry we want is the first list entry
			if (KEY_ADDR not in addr):
				logging.info("Interface: %s does not have an address" % (self.ifId))
				if (self.verbose):
					print("Interface %s does not have an address" % (self.ifId))
				return None

			if (KEY_NETMASK not in addr):
				logging.info("Interface: %s does not contain a netmask" % (self.ifId))
				if (self.verbose):
					print("Interface %s does not contain a netmask" % (self.ifId))
				return None

			genStr = addr[KEY_ADDR]+"/"+addr[KEY_NETMASK]
			return ipaddress.ip_interface(genStr).network
		else:
			logging.info("Interface: %s: Key type %d not found in available address types" % (self.ifId, self.addrType))
			if (self.verbose):
				print("Key type %d not found in available address types" % (self.addrType))


