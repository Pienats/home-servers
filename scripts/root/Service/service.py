'''
Linux service wrapper and abstraction
'''
import subprocess
import time
import logging

# Some "Constant" values
STOPPED = 0
RUNNING = 1

class ServiceError(RuntimeError):
	"""
	Service related exception
	"""
	def __init__(self, arg):
		self.args = arg

class Service:
	"""
	Class to represent a system service
	"""
	def __init__(self, name, initSystem, verbose = False):
		"""
		Constructor
		@param name Service name
		@param initSystem The init system in use by the OS
		@param verbose Indicate whether or not verbose mode should be used

		@throws ServiceError exception on unsupported initSystem
		"""
		self.name = name
		self.initSystem = initSystem
		self.verbose = verbose

		if (self.initSystem == "openRC"):
			self.OK_STR = "[ ok ]"
			self.STATUS_STARTED_STR = "started"
			self.STATUS_STOPPED_STR = "stopped"
		elif (self.initSystem == "systemd"):
			self.OK_STR = ""
			self.STATUS_STARTED_STR = "active (running)"
			self.STATUS_STOPPED_STR = "inactive (dead)"
		else:
			logging.info("Service: Unsupported service %s" % self.initSystem)
			if (self.verbose):
				print("Unsupported service %s" % self.initSystem)
			raise ServiceError("Unsupported init system type: %s" % (self.initSystem))

	def getCmd(self, action):
		"""
		Retrieve the service command to run
		@param action Specific service action to perform

		@return Command to run to perform the provided action for the service
		@throws ServiceError exception on unsupported initSystem
		"""
		theCmd = ""
		if (self.initSystem == "openRC"):
			theCmd = ["/etc/init.d/" + self.name] + [action]
		elif (self.initSystem == "systemd"):
			theCmd = ["systemctl", action, self.name]
		else:
			logging.info("Service: Unsupported service %s" % (self.initSystem))
			if (self.verbose):
				print("Unsupported service %s" % (self.initSystem))
			raise ServiceError("Unsupported init system type: %s" % (self.initSystem))
		return theCmd

	def getStatus(self):
		"""
		Retrieve service status

		@return RUNNING if service is active, STOPPED otherwise
		"""
		try:
			cmd = self.getCmd("status")
			if (self.verbose):
				print("Command to execute [%d]: %s" % (len(cmd), cmd))
			output = subprocess.check_output(cmd)
			outString = output.decode("utf-8")
			if (self.verbose):
				print("Command output:\n%s" % outString)
			if (self.STATUS_STARTED_STR in outString):
				logging.info("Service: %s status: Running" % (self.name))
				return RUNNING
			elif (self.STATUS_STOPPED_STR in outString):
				logging.info("Service: %s status: Stopped" % (self.name))
				return STOPPED
			else:
				logging.info("Service: %s status: Unknown state" % (self.name))
				if (self.verbose):
					print("Unknown state")
				return STOPPED
		except subprocess.CalledProcessError as cpe:
			# An exception here does not necessarily mean an error, so don't automatically
			# print the output
			if (self.verbose):
				outString = cpe.output.decode("utf-8")
				print("Service status error: %d" % cpe.returncode)
				print("Exception Command output:\n%s" % outString)
		except ServiceError as se:
			# Raise the exception again for calling code
			raise
		logging.info("Service: %s status: Exception occured, assuming Stopped" % (self.name))
		if (self.verbose):
			print("Service: %s status: Exception occured, assuming Stopped" % (self.name))
		return STOPPED

	def start(self, maxAttempts = 1, waitTime = 3):
		"""
		Start service
		@param maxAttempts The maximum number of attempts that should be made to start the service (defaults to 1)
		@param waitTime The time to wait (in seconds) between failed attempts to avoid false negatives (defaults to 3)

		@return RUNNING on successful service start, STOPPED otherwise
		"""
		cmd = self.getCmd("start")
		if (self.verbose):
			print("Command to execute [%d]: %s" % (len(cmd), cmd))
		try:
			logging.info("Service: %s start..." % (self.name))
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
				logging.info("Service: %s start error; OK string not found" % (self.name))
				if (self.verbose):
					print("OK string not found")
				return STOPPED
		# Here the service have most likely started, but is not yet listed as running
		for cnt in range(0, maxAttempts):
			logging.info("Service: %s started, testing status [%d/%d]" % (self.name, cnt, maxAttempts))
			if (self.verbose):
				print("Testing service status [%d/%d]" % (cnt, maxAttempts))
			status = self.getStatus()
			if (status == RUNNING):
				if (self.verbose):
					print("Start -> status is running")
				return RUNNING
			else:
				time.sleep(waitTime)

		logging.info("Service: %s not started yet after %d test attempts" % (self.name, maxAttempts))
		if (self.verbose):
			print("Service not started yet after %d test attempts" % (maxAttempts))
		return STOPPED

	def stop(self):
		"""
		Stop the serivce
		"""
		cmd = self.getCmd("stop")
		if (self.verbose):
			print("Command to execute [%d]: %s" % (len(cmd), cmd))
		try:
			logging.info("Service: %s stop..." % (self.name))
			output = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
			#output = subprocess.run(cmd) # python 3.5
			if (self.verbose):
				outString = output.decode("utf-8")
				print("Command output:\n%s" % outString)
		except subprocess.CalledProcessError as cpe:
			outString = cpe.output.decode("utf-8")
			logging.info("Service: %s stop error" % (self.name))
			logging.info("Exception Command output:\n%s" % outString)
			if (self.verbose):
				print("Service stop error: %d" % cpe.returncode)
				#print("Exception stderr output:\n%s" % cpe.stderr) # python 3.5
				print("Exception Command output:\n%s" % outString)
		return STOPPED
