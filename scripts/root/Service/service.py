
import subprocess
import time

# Some "Constant" values
STOPPED = 0
RUNNING = 1

SERVICE_MAX_TRY_COUNT = 5
SERVICE_TRY_WAIT_TIME = 2

class Service:
	def __init__(self, name, initSystem):
		self.name = name
		self.initSystem = initSystem
		if (self.initSystem == "openRC"):
			self.OK_STR = "[ ok ]"
		else:
			print("Unsupported service %s" % self.initSystem)
			# TODO: throw and handle exception
		
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
			outString = output.decode("utf-8")
			print("Command output:\n%s" % outString)
			return RUNNING
		except subprocess.CalledProcessError as cpe:
			outString = cpe.output.decode("utf-8")
			print("Service status error: %d" % cpe.returncode)
			print("Exception Command output:\n%s" % outString)
		return STOPPED

	def start(self, testCount = 1, waitTime = 3):
		# TODO: Exception on (testCount < 1)
		cmd = self.getCmd("start")
		print("Command to execute [%d]: %s" % (len(cmd), cmd))
		try:
			output = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
			#output = subprocess.run(cmd) # python 3.5
			outString = output.decode("utf-8")
			print("Command output:\n%s" % outString)
			return RUNNING
		except subprocess.CalledProcessError as cpe:
			outString = cpe.output.decode("utf-8")
			print("Service start error: %d" % cpe.returncode)
			#print("Exception stderr output:\n%s" % cpe.stderr) # python 3.5
			print("Exception Command output:\n%s" % outString)
			# Even if service start returns an error code, it is not necessarily a
			# catastrophic failure. Search for the OK_STR, for the situation where
			# a delayed start is encountered. In this case wait a bit to give the
			# service a chance to start (VPN for eg can take almost 30s in certain
			# situations)
			idx = outString.find(self.OK_STR)
			if (idx == -1):
				print("OK string not found")
				return STOPPED
		# Here the service have most likely started, but is not yet listed as running
		for cnt in range(0, testCount):
			print("Testing service status [%d/%d]" % (cnt, testCount))
			status = self.getStatus()
			if (status == RUNNING):
				print("Start -> status is running")
				return RUNNING
			else:
				time.sleep(waitTime)
		print("Service not started yet after %d rounds" % testCount)
		return STOPPED
		
	def stop(self):
		cmd = self.getCmd("stop")
		print("Command to execute [%d]: %s" % (len(cmd), cmd))
		try:
			output = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
			#output = subprocess.run(cmd) # python 3.5
			outString = output.decode("utf-8")
			print("Command output:\n%s" % outString)
		except subprocess.CalledProcessError as cpe:
			outString = cpe.output.decode("utf-8")
			print("Service stop error: %d" % cpe.returncode)
			#print("Exception stderr output:\n%s" % cpe.stderr) # python 3.5
			print("Exception Command output:\n%s" % outString)
		return STOPPED
