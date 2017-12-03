# coding=utf-8
#------------------------------------------------------------------------------------------------------
# TDA596 Labs - Server Skeleton
# server/server.py
# Input: Node_ID total_number_of_ID
# Student Group: 5
# Student names: Fredrik Mårlind
#------------------------------------------------------------------------------------------------------
# We import various libraries
from BaseHTTPServer import HTTPServer, BaseHTTPRequestHandler # Socket specifically designed to handle HTTP requests
import sys # Retrieve arguments
from urlparse import parse_qs # Parse POST data
from httplib import HTTPConnection # Create a HTTP connection, as a client (for POST requests to the other vessels)
from urllib import urlencode # Encode POST content into the HTTP header
from codecs import open # Open a file
from threading import  Thread # Thread Management
import re
import random
import time
import ast
#------------------------------------------------------------------------------------------------------

# Global variables for HTML templates
board_frontpage_footer_template = ""
board_frontpage_header_template = ""
boardcontents_template = ""
entry_template = ""

#------------------------------------------------------------------------------------------------------
# How many times should we try to resend a message
RETRY_COUNTS = 5
# How long should we wait before we try to resend a messege
RETRY_WAIT_TIME = 0.1
# Delay between contacting the leader
LEADER_ALIVE_CHECK_TIME = 5
#------------------------------------------------------------------------------------------------------
# The port we should use, it is just instanciated to 0
port = 0




#------------------------------------------------------------------------------------------------------
#------------------------------------------------------------------------------------------------------
class BlackboardServer(HTTPServer):
#------------------------------------------------------------------------------------------------------
	def __init__(self, server_address, handler, node_id, vessel_list):
	# We call the super init
		HTTPServer.__init__(self,server_address, handler)
		# we create the dictionary of values
		self.store = {}
		# We keep a variable of the next id to insert
		self.current_key = -1
		# our own ID (IP is 10.1.0.ID)
		self.vessel_id = vessel_id
		# The list of other vessels
		self.vessels = vessel_list
		# Decide leader
		self.leader_id = -1
		self.leader_value = random.randint(0,pow(len(self.vessels)+1,4))
		self.vessels[self.vessel_id] = self.leader_value
		self.leader_election()
		self.check_leader()
#------------------------------------------------------------------------------------------------------
	# We add a value received to the store
	def add_value_to_store(self, value):
		# We add the value to the store
		self.current_key += 1
		self.store[self.current_key] = value
		pass
#------------------------------------------------------------------------------------------------------
	# We modify a value received in the store
	def modify_value_in_store(self,key,value):
		# we modify a value in the store if it exists
		if key in self.store:
			self.store[key] = value
		pass
#------------------------------------------------------------------------------------------------------
	# We delete a value received from the store
	def delete_value_in_store(self,key):
		# we delete a value in the store if it exists
		if key in self.store:
			del self.store[key]
		pass
#------------------------------------------------------------------------------------------------------
# Contact a specific vessel with a set of variables to transmit to it
	def contact_vessel(self, action_type, vessel_id, path, post_content):
		# the Boolean variable we will return
		success = False
		# the HTTP header must contain the type of data we are transmitting, here URL encoded
		headers = {"Content-type": "application/x-www-form-urlencoded"}
		# We should try to catch errors when contacting the vessel
		try:
			# We contact vessel:PORT_NUMBER since we all use the same port
			# We can set a timeout, after which the connection fails if nothing happened
			connection = HTTPConnection("10.1.0.%d:%d" % (vessel_id, port), timeout = 30)
			# We send the HTTP request
			connection.request(action_type, path, post_content, headers)
			# We retrieve the response
			response = connection.getresponse()
			# We want to check the status, the body should be empty
			status = response.status
			# If we receive a HTTP 200 - OK
			if status == 200:
				success = True
		# We catch every possible exceptions
		except Exception as e:
			print ("Error while contacting %s" % vessel_id)
			# printing the error given by Python
			print(e)

		# we return if we succeeded or not
		return success
#------------------------------------------------------------------------------------------------------
	# We send a received value to all the other vessels of the system
	def propagate_value_to_vessels(self, path, post_content):
		# We iterate through the vessel list
		for vessel_id in self.vessels.keys():
			# We should not send it to our own IP, or we would create an infinite loop of updates
			if vessel_id != self.vessel_id:
				self.contact_request("POST", vessel_id, path, post_content)

	def send_to_node(self,action_type,vessel_id, path, post_content):
		self.contact_request(action_type, vessel_id, path, post_content)

	def contact_request(self, action_type, vessel_id, path, post_content):
		# Create a new thread that will handle retries
		thread = Thread(target=self.contact_request_thread,args=(action_type,vessel_id, path, post_content))
		# We kill the process if we kill the server
		thread.daemon = True
		# We start the thread
		thread.start()

	def contact_request_thread(self,action_type, vessel_id, path, post_content):
		count = 0
		while count < RETRY_COUNTS:
			if self.contact_vessel(action_type,vessel_id, path, post_content):
				break
			else:
				count += 1
				time.sleep(RETRY_WAIT_TIME)
		if count == RETRY_COUNTS:
			self.remove_from_vessels(vessel_id)

	def remove_from_vessels(self,vessel_id):
		if vessel_id in self.vessels:
			del self.vessels[vessel_id]
		#New election!
		if vessel_id == self.leader_id:
			self.leader_id = -1
			self.leader_election()


	def check_leader(self):
		thread = Thread(target=self.check_leader_thread)
		thread.daemon = True
		thread.start()

	def check_leader_thread(self):
		while True:
			if not self.is_leader() and self.leader_id != -1:
				self.send_to_node("GET",self.leader_id,"/leader","")
				time.sleep(LEADER_ALIVE_CHECK_TIME)
#------------------------------------------------------------------------------------------------------

	# Leader election: in O(3n)=O(n) time
	# Check for neighbor, if it has changed.
	# Check if we have collected all the data.
	# If data collection is complete, iterate through and select a leader.
	# Send the complete set of data to the neighbor.
	def leader_election(self):
		if len(self.vessels) != 0:
			neighbor = self.find_neighbor()
			data_collection_complete = self.is_leader_data_complete()
			post_content = urlencode({'vessels': self.vessels})
			if data_collection_complete:
				max_leader = self.leader_value
				self.leader_id = self.vessel_id
				for vessel_id in self.vessels.keys():
					if self.vessels[vessel_id] > max_leader:
						max_leader = self.vessels[vessel_id]
						self.leader_id = vessel_id
					# Handels the unlikely case of the random value is the same, by selecting the one with highest id
					elif self.vessels[vessel_id] == max_leader:
						if self.leader_id < vessel_id:
							self.leader_id = vessel_id
			self.send_to_node("POST", neighbor,"/election",post_content)
		else:
			self.leader_id = self.vessel_id
			print "No other vessels :C\n"
	# Reset the nodes collected data, in O(n) time
	def clear_leader_values(self):
		for key in self.vessels.keys():
			self.vessels[key] = -1
	# Check if the data is complete in O(n) time
	def is_leader_data_complete(self):
		for vessel_id in self.vessels.keys():
			if self.vessels[vessel_id] == -1:
				return False
		return True

	# Adds values that does not exist to our list, removes those that does not exist in vessels param, O(n) time
	def modify_vessels_leader_value(self,vessels):
		for vessel_id in self.vessels.keys():
			if not (vessel_id in vessels):
				self.remove_from_vessels(vessel_id)
			elif vessels[vessel_id] != -1:
				self.vessels[vessel_id] = vessels[vessel_id]
	# Find the nodes nearest node, in O(n) time
	def find_neighbor(self):
		neighbor = self.vessel_id
		v_list = sorted(self.vessels.keys())
		#If we have the higest id we should just contact the on with the lowest directly
		if v_list[len(v_list)-1] == self.vessel_id:
			return v_list[0]
		for vessel in v_list:
			# When we find a vessel with a higher id, that will be our neighbor
			if vessel > neighbor:
				neighbor = vessel
				break

		return neighbor

	# Check if the node is leader
	def is_leader(self):
		if self.leader_id == self.vessel_id:
			return True
		else:
			return False

#------------------------------------------------------------------------------------------------------
#------------------------------------------------------------------------------------------------------
# This class implements the logic when a server receives a GET or POST request
# It can access to the server data through self.server.*
# i.e. the store is accessible through self.server.store
# Attributes of the server are SHARED accross all request hqndling/ threads!
class BlackboardRequestHandler(BaseHTTPRequestHandler):
#------------------------------------------------------------------------------------------------------
	# We fill the HTTP headers
	def set_HTTP_headers(self, status_code = 200):
		 # We set the response status code (200 if OK, something else otherwise)
		self.send_response(status_code)
		# We set the content type to HTML
		self.send_header("Content-type","text/html")
		# No more important headers, we can close them
		self.end_headers()
#------------------------------------------------------------------------------------------------------
	# a POST request must be parsed through urlparse.parse_QS, since the content is URL encoded
	def parse_POST_request(self):
		post_data = ""
		# We need to parse the response, so we must know the length of the content
		length = int(self.headers['Content-Length'])
		# we can now parse the content using parse_qs
		post_data = parse_qs(self.rfile.read(length), keep_blank_values=1)
		# we return the data
		return post_data
#------------------------------------------------------------------------------------------------------
#------------------------------------------------------------------------------------------------------
# Request handling - GET
#------------------------------------------------------------------------------------------------------
	# This function contains the logic executed when this server receives a GET request
	# This function is called AUTOMATICALLY upon reception and is executed as a thread!
	def do_GET(self):
		print("Receiving a GET on path %s" % self.path)
		# Here, we should check which path was requested and call the right logic based on it
		if self.server.leader_id != -1:
			if self.path == "/":
				self.do_GET_Index()
			elif self.path == "/board":
				self.do_GET_Board()
			elif self.path == "/leader":
				self.set_HTTP_headers(200)
		else:
			self.do_GET_NoLeader()
#------------------------------------------------------------------------------------------------------
# GET logic - specific path
#------------------------------------------------------------------------------------------------------
	def do_GET_Index(self):
		# We set the response status code to 200 (OK)
		self.set_HTTP_headers(200)
		self.make_Page()

	def do_GET_Board(self):
		self.set_HTTP_headers(200)
		self.make_Page()
	def do_GET_NoLeader(self):
		self.set_HTTP_headers(200)
		header = board_frontpage_header_template
		content = "<h1>No leader elected!</h1>" + boardcontents_template % (0,0,"Board Contents","")
		footer = board_frontpage_footer_template % "fremarl@student.chalmers.se"
		page =  header + content + footer
		self.wfile.write(page)
	#Constructs the html pages to be rendered
	def make_Page(self):
		entries = self.get_Entries()
		header = board_frontpage_header_template
		content = boardcontents_template %(self.server.leader_id,self.server.vessels[self.server.leader_id],"Board Contents",entries)
		footer = board_frontpage_footer_template % "fremarl@student.chalmers.se"
		page =  header + content + footer
		self.wfile.write(page)

	#Formats current entries into a string
	def get_Entries(self):
		entries = ""
		for msg_id in sorted(self.server.store.keys()):
			entries += entry_template % ("board/%d"% msg_id,msg_id,self.server.store[msg_id])
		return entries

#------------------------------------------------------------------------------------------------------
# Request handling - POST
#------------------------------------------------------------------------------------------------------
	def do_POST(self):
		print("Receiving a POST on %s" % self.path)
		self.set_HTTP_headers(200)
		data = self.parse_POST_request()
		if self.path == "/board":
			self.do_POST_New_Entry(data)
		elif re.search(r'\d+',self.path):
			self.do_POST_Edit(data)
		elif self.path == "/propagate":
			self.do_POST_Server(data)
		elif self.path == "/election":
			self.do_Leader_Election(data)
		elif self.path == "/election/result":
			self.accept_leader(data)



#------------------------------------------------------------------------------------------------------
# POST Logic
#------------------------------------------------------------------------------------------------------
	#Handels propagation requests, used by children to get their commands from the leader
	def do_POST_Server(self,data):
		print data
		#New entry
		if data["action"][0] == '0':
			self.server.current_key = int(data["key"][0]) -1
			self.server.add_value_to_store(data["value"][0])
		#Delete entry
		elif data["action"][0] == '1':
			self.server.delete_value_in_store(int(data["key"][0]))
		#Edit entry
		elif data["action"][0] == '2':
			self.server.modify_value_in_store(int(data["key"][0]),data["value"][0])
	#Adds a new entry locally and then propagates it
	def do_POST_New_Entry(self,data):
		if self.server.is_leader():
			self.server.add_value_to_store(data["entry"][0])
			self.propagate_to_children(0,self.server.current_key,data["entry"][0])
		else:
			self.to_leader("/board",data["entry"][0],0)
	#Handels edits and deletes
	def do_POST_Edit(self,data):
		#Get the id of the entry
		msg_id = int(self.path[7:])
		value = data["entry"][0]
		if data["delete"][0] == "0":
			if self.server.is_leader():
				self.server.modify_value_in_store(msg_id,value)
				self.propagate_to_children(0,msg_id,value)
			else:
				self.to_leader("/board/%d"%msg_id,data["entry"][0],0)
		else:
			if self.server.is_leader():
				self.server.delete_value_in_store(msg_id)
				self.propagate_to_children(1,msg_id,value)
			else:
				self.to_leader("/board/%d"%msg_id,data["entry"][0],1)
	#Starts a new propagation thread
	def propagate_to_children(self,action,key,value):
		# The variables must be encoded in the URL format, through urllib.urlencode
		post_content = urlencode({'action': action, 'key': key, 'value': value})
		thread = Thread(target=self.server.propagate_value_to_vessels,args=("/propagate",post_content) )
		# We kill the process if we kill the server
		thread.daemon = True
		# We start the thread
		thread.start()

	# Sends data to the leader
	def to_leader(self,path,value,delete):
		# The variables must be encoded in the URL format, through urllib.urlencode
		post_content = urlencode({'entry': value,'delete': delete})
		thread = Thread(target=self.server.send_to_node,args=("POST",self.server.leader_id,path,post_content) )
		# We kill the process if we kill the server
		thread.daemon = True
		# We start the thread
		thread.start()

	# Do leader election:
	# If we do have a leader we transmit the result to the sender node
	# If the don't have a leader set yet we continue the leader election
	def do_Leader_Election(self,data):
		vessels = ast.literal_eval(data["vessels"][0])
		self.server.modify_vessels_leader_value(vessels)
		if self.server.leader_id != -1:
			post_content = urlencode({'vessels': self.server.vessels})
			v_id = int(self.client_address[0].split('.')[3])
			self.server.send_to_node("POST",v_id,"/election/result",post_content)
			print "LEADER IS ELECTED!"
		else:
			self.server.leader_election()
	# If we get the result from a sender node we accept we result
	# We update our own vessel list to the current one
	def accept_leader(self,data):
		vessels = ast.literal_eval(data["vessels"][0])
		self.server.vessels = vessels


#------------------------------------------------------------------------------------------------------
#------------------------------------------------------------------------------------------------------
# Execute the code
if __name__ == '__main__':

	## read the templates from the corresponding html files
	#Loading from ./server/ since that is where mininet instances will load from
	board_frontpage_footer_template = file("server/board_frontpage_footer_template.html").read()
	board_frontpage_header_template = file("server/board_frontpage_header_template.html").read()
	boardcontents_template = file("server/boardcontents_template.html").read()
	entry_template = file("server/entry_template.html").read()

	vessel_list = {}
	vessel_id = 0
	# Checking the arguments
	if len(sys.argv) != 4: # 2 args, the script and the vessel name
		print("Arguments: vessel_ID number_of_vessels port_number")
	else:
		# We need to know the vessel IP
		vessel_id = int(sys.argv[1])
		#Get the port number
		port = int(sys.argv[3])
		# We need to write the other vessels IP, based on the knowledge of their number
		for i in range(1, int(sys.argv[2])+1):
			#vessel_list.append("10.1.0.%d" % i) # We can add ourselves, we have a test in the propagation
			vessel_list[i] = -1

	# We launch a server
	server = BlackboardServer(('', port), BlackboardRequestHandler, vessel_id, vessel_list)
	print("Starting the server on port %d" % port)
	time.sleep(5)
	try:
		server.serve_forever()
	except KeyboardInterrupt:
		server.server_close()
		print("Stopping Server")
#------------------------------------------------------------------------------------------------------
