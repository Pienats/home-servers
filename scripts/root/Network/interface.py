
import subprocess

# Some "Constant" values
UP = 1
DOWN = 0

class Interface:
	'Network interface class to determine status, starting and stopping'
	status = DOWN
	
	def __init__(self, name):
		self.name = name
	
	def getStatus(self):
		print("Getting status for Network interface %s" % self.name)
		try:
			output = subprocess.check_output(["ifconfig", self.name])
			print("Command output:\n%s" % output.decode("utf-8"))
			return UP
		except subprocess.CalledProcessError as cpe:
			print("Error getting interface config: %d" % cpe.returncode)
			print("Command output: %s" % cpe.output)
		return DOWN


