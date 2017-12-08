from ..cisco_base_device import CiscoBaseDevice
import re
import optparse
import xml.etree.cElementTree as ET
from StringIO import StringIO

class CiscoNXOS(CiscoBaseDevice):

	def get_run_config_cmd(self):
		command = 'show running-config | exclude !'
		return command

	def get_start_config_cmd(self):
		command = 'show startup-config | exclude !'
		return command

	def get_cdp_neighbor_cmd(self):
		command = 'show cdp neighbors | begin ID'
		return command

	def pull_interface_config(self):
		command = "show run interface %s | exclude version | exclude Command | exclude !" % (self.interface)
		return self.split_on_newline(self.run_ssh_command(command))

	def pull_interface_mac_addresses(self):
		command = "show mac address-table interface %s | exclude VLAN | exclude Legend" % (self.interface)
		return self.split_on_newline(self.replace_double_spaces_commas(result).replace('*', ''))

	def pull_interface_statistics(self):
		command = "show interface %s" % (self.interface)
		return self.split_on_newline(self.run_ssh_command(command))

	def pull_interface_info(self):
		intConfig = self.pull_interface_config()
		intMac = self.pull_interface_mac_addresses()
		intStats = self.pull_interface_statistics()

		return intConfig, intMac, intStats

	def pull_device_uptime(self):
		command = 'show version | include uptime'
		uptime = self.split_on_newline(self.run_ssh_command(command))
		for x in uptime:
			output = x.split(' ', 3)[-1]
		return outputoutput

	def pull_host_interfaces(self):
		command = "show interface status | xml"
		result = self.run_ssh_command(command)

		# Returns False if nothing was returned
		if not result:
			return result
		result = re.findall("\<\?xml.*reply\>", result, re.DOTALL)
		# Strip namespaces
		it = ET.iterparse(StringIO(result[0]))
		for _, el in it:
		    if '}' in el.tag:
		        el.tag = el.tag.split('}', 1)[1]  # strip all namespaces
		root = it.root

		# This variable is to skip the first instance of "ROW_interface" in the XML output
		a = False
		nameStatus = False
		for elem in root.iter():
			if a:
				if not elem.tag.isspace() and not elem.text.isspace():
					# This is in case there is no name/description:
					# Reset counter var to True on each loop back to a new 'interface'
					if elem.tag == 'interface':
						nameStatus = True
					# Name input provided, set var to False to skip the '--' ahead
					elif elem.tag == 'name':
						nameStatus = False
					# No Name column provided, use '--' instead
					elif elem.tag == 'state' and nameStatus:
						outputResult = outputResult + 'ip,--,'

					# Skip certain columns
					if elem.tag == 'vlan' or elem.tag == 'duplex' or elem.tag == 'type':
						pass
					# Placeholder 'ip' for upcoming IP address lookup in new function
					elif elem.tag == 'name':
						# Truncate description (name column) to 25 characters only
						outputResult = outputResult + 'ip,' + elem.text[:25] + ','
					# Otherwise store output to string
					else:
						outputResult = outputResult + elem.text + ','

			# This is to skip the first instance of "ROW_interface" in the XML output
			if elem.tag == 'ROW_interface':
				outputResult = outputResult + '\n'
				a = True


		command = 'sh run int | egrep interface|ip.address | ex passive | ex !'

		result = self.run_ssh_command(command)

		# Set intStatus var to False initially
		intStatus = 0
		# Keeps track of the name of the interface we're on currently
		currentInt = ''
		realIP = ''
		realIPList = []
		# This extracts the IP addresses for each interface, and inserts them into the outputResult string
		for x in self.split_on_newline(result):
			# Line is an interface
			if 'interface' in x:
				currentInt = x.split(' ')
				intStatus += 1

			# No IP address, so use '--' instead
			if 'interface' in x and intStatus == 2:
				# Reset counter
				intStatus = 1
				a = currentInt[1] + ',ip'
				b = currentInt[1] + ',--'
			else:
				realIPList = x.split(' ')
				realIP = realIPList[-1]
				a = currentInt[1] + ',ip'
				b = currentInt[1] + ',' + realIP
				outputResult = outputResult.replace(a, b)

		# Cleanup any remaining instances of 'ip' in outputResult
		outputResult = outputResult.replace(',ip,', ',--,')
		# Split by newlines and return as list
		return self.split_on_newline(outputResult)

	def count_interface_status(self, interfaces): #required
		up, down, disabled, total = 0
		for interface in interfaces:
			if not 'Interface' in interface:
				if 'disabled' in interface:
					disabled += 1
				elif 'notconnect' in interface:
					down += 1
				elif 'sfpAbsent' in interface:
					down += 1
				elif 'down,' in interface:
					down += 1
				elif 'noOperMembers' in interface:
					down += 1
				elif 'connected' in interface:
					up += 1

				total += 1
		# Counter on NX-OS is always off by 1
		total -= 1

		return up, down, disabled, total

