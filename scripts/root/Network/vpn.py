
import Network.interface as iface
import Service.service as service

class VPN:
	def __init__(self, provider, vpnIF, initSystem):
		self.provider = provider
		self.vpnIF = vpnIF
		self.initSystem = initSystem
		
		if ( initSystem == "openRC"):
			self.service = service.Service("openvpn." + provider, initSystem)
			self.vpnIf = iface.Interface(vpnIF)
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
		if (status == service.UP):
			print("VPN Service is UP")
		else:
			print("VPN service is not UP")
		return
