
import subprocess
import netifaces
import ipaddress

# Some "Constant" values
UP = 1
DOWN = 0

KEY_ADDR = 'addr'
KEY_PEER = 'peer'
KEY_NETMASK = 'netmask'

class Interface:
	'Network interface class to determine status, starting and stopping'
	status = DOWN

	def __init__(self, ifId, verbose = False):
		self.ifId = ifId
		self.verbose = verbose
		self.addrType = netifaces.AF_INET # We are interested in IPv4 addresses

	def getId(self):
		return self.ifId

	def getStatus(self):
		availableIfs = netifaces.interfaces()

		if self.ifId in availableIfs:
			print("Interface %s is available" % self.ifId)
			return UP
		else:
			print("Interface %s not available" % self.ifId)
		return DOWN

	def getTunnelParams(self):
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
				print("Interface %s does not have an address" % self.ifId)
				return {}

			if (KEY_PEER not in addr):
				print("Interface %s does not contain a peer address" % self.ifId)
				return {}

			return addr

		else:
			print("Key type %d not found in available address types" % self.addrType)

	def getNetworkParams(self):
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
				print("Interface %s does not have an address" % self.ifId)
				return None

			if (KEY_NETMASK not in addr):
				print("Interface %s does not contain a netmask" % self.ifId)
				return None

			genStr = addr[KEY_ADDR]+"/"+addr[KEY_NETMASK]
			return ipaddress.ip_interface(genStr).network
		else:
			print("Key type %d not found in available address types" % self.addrType)


