
import subprocess

# Some "Constant" values
UP = 1
DOWN = 0
SERVICE_MAX_TRY_COUNT = 5
SERVICE_TRY_WAIT_TIME = 2

class Service:
	def __init__(self, name, initSystem):
		self.name = name
		self.initSystem = initSystem
		
	def getCmd(self, action):
		theCmd = ""
		if (self.initSystem == "openRC"):
			theCmd = ["/etc/init.d/" + self.name] + [action]
		else:
			print("Unsupported service %s" % self.initSystem)
			# TODO: throw and handle exception
		return theCmd

	def getStatus(self):
		cmd = self.getCmd("status")
		print("Command to execute [%d]: %s" % (len(cmd), cmd))
		try:
			output = subprocess.check_output(cmd)
			print("Command output: \n%s" % output.decode("utf-8"))
			return UP
		except subprocess.CalledProcessError as cpe:
			print("Service status error: %d" % cpe.returncode)
			print("Command output:\n%s" % cpe.output.decode("utf-8"))
		
		return DOWN
