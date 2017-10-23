'''
Linux service wrapper and abstraction
'''
import subprocess
import time

# Some "Constant" values
STOPPED = 0
RUNNING = 1

class Service:
	def __init__(self, name, initSystem, verbose = False):
		self.name = name
		self.initSystem = initSystem
		self.verbose = verbose

		if (self.initSystem == "openRC"):
			self.OK_STR = "[ ok ]"
			self.STATUS_STARTED_STR = "started"
			self.STATUS_STOPPED_STR = "stopped"
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
		if (self.verbose):
			print("Command to execute [%d]: %s" % (len(cmd), cmd))
		try:
			output = subprocess.check_output(cmd)
			outString = output.decode("utf-8")
			if (self.verbose):
				print("Command output:\n%s" % outString)
			if (self.STATUS_STARTED_STR in outString):
				return RUNNING
			elif (self.STATUS_STOPPED_STR in outString):
				return STOPPED
			else:
				print("Unknown state")
				return STOPPED
		except subprocess.CalledProcessError as cpe:
			# An exception here does not necessarily mean an error, so don't automatically
			# print the output
			if (self.verbose):
				outString = cpe.output.decode("utf-8")
				print("Service status error: %d" % cpe.returncode)
				print("Exception Command output:\n%s" % outString)
		return STOPPED

	def start(self, testCount = 1, waitTime = 3):
		# TODO: Exception on (testCount < 1)
		cmd = self.getCmd("start")
		if (self.verbose):
			print("Command to execute [%d]: %s" % (len(cmd), cmd))
		try:
			output = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
			#output = subprocess.run(cmd) # python 3.5
			if (self.verbose):
				outString = output.decode("utf-8")
				print("Command output:\n%s" % outString)
			return RUNNING
		except subprocess.CalledProcessError as cpe:
			outString = cpe.output.decode("utf-8")
			if (self.verbose):
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
		if (self.verbose):
			print("Command to execute [%d]: %s" % (len(cmd), cmd))
		try:
			output = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
			#output = subprocess.run(cmd) # python 3.5
			if (self.verbose):
				outString = output.decode("utf-8")
				print("Command output:\n%s" % outString)
		except subprocess.CalledProcessError as cpe:
			outString = cpe.output.decode("utf-8")
			print("Service stop error: %d" % cpe.returncode)
			#print("Exception stderr output:\n%s" % cpe.stderr) # python 3.5
			print("Exception Command output:\n%s" % outString)
		return STOPPED
