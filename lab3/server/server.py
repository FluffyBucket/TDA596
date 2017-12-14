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
from operator import itemgetter
from ast import literal_eval as make_tuple
import re
import time
#------------------------------------------------------------------------------------------------------

# Global variables for HTML templates
board_frontpage_footer_template = ""
board_frontpage_header_template = ""
boardcontents_template = ""
entry_template = ""

#------------------------------------------------------------------------------------------------------
port = 0
#------------------------------------------------------------------------------------------------------




#------------------------------------------------------------------------------------------------------
#------------------------------------------------------------------------------------------------------
class BlackboardServer(HTTPServer):
#------------------------------------------------------------------------------------------------------
	def __init__(self, server_address, handler, node_id, vessel_list):
	# We call the super init
		HTTPServer.__init__(self,server_address, handler)
		# we create the dictionary of values
		# Contains: (value,origin_id,sequence)
		self.store = []
		# Short backlog of messages, for a post
		# (action,(value,origin_id,sequence),origin_id,sequence)
		# Where the second value contains the message, and the 3rd and 4th contains information about the sender/creator of the history.
		self.history = {}
		# We keep a variable of the next id to insert
		self.current_key = -1

		self.seq_number = -1
		# our own ID (IP is 10.1.0.ID)
		self.vessel_id = vessel_id
		# The list of other vessels
		self.vessels = vessel_list
		self.firstMsg = True
		self.start = time.time()
		self.end = time.time()
#------------------------------------------------------------------------------------------------------
	# We add a value received to the store
	def add_value_to_store(self, seq, value, origin_id):
		if firstMsg:
			start = time.time()

		if self.seq_number < seq:
			self.seq_number = seq

		self.insert_into_store(seq,value,origin_id)
		end = time.time()
		pass

	# This func will insert an item at its correct position
	def insert_into_store(self, seq, value, origin_id):
		# If we have a history already
		if (origin_id, seq) in self.history:
			old = self.history[origin_id, seq]
			# If it was an edit with lower origin_id or higher sequence
			# If it was deleted we will not add a new one
			if old[0] == 2 and (old[2] <= origin_id or old[3] > seq):
				self.store.append(old[1])
		else:
			self.store.append((value,origin_id,seq))
			self.history[(origin_id,seq)] = (0,(value,origin_id,seq),origin_id,seq)
		self.sort_store()

	def sort_store(self):
		# Sort by sequence first then by origin_id
		# (1,1)
		# (2,1)
		self.store.sort(key=itemgetter(2,1))

#------------------------------------------------------------------------------------------------------
	# We delete a value received from the store
	def delete_value_in_store(self,seq,value,origin_id):
		self.seq_number += 1
		if self.seq_number < seq:
			self.seq_number = seq

		deleted = make_tuple(value)
		print "delete:%d\t%s" % (seq,value)
		# we delete a value in the store if it exists
		if deleted in self.store:
			index = self.store.index(deleted)
			old = self.history[(deleted[1],deleted[2])]
			if (old[3] == seq and old[2] >= origin_id) or old[3] < seq:
				del self.store[index]
				self.history[(deleted[1],deleted[2])] = (1,deleted,origin_id,seq)
		else:
			self.history[(origin_id,seq)] = (1,value)
		pass
#------------------------------------------------------------------------------------------------------
	# We modify a value received in the store
	def modify_value_in_store(self,seq,value, origin_id):
		self.seq_number += 1
		if self.seq_number < seq:
			self.seq_number = seq
		# we modify a value in the store if it exists
		print "change: %d\t%s" % (seq,value)
		items = [(o,s) for (v,o,s) in self.store]

		new = make_tuple(value)
		# There must be a history if it exists
		if (new[1],new[2]) in self.history:
			old = self.history[(new[1],new[2])]
			if (new[1],new[2]) in items:
				index = items.index((new[1],new[2]))
				# Check if sequence number is higher and lower origin
				if (old[3] == seq and old[2] >= origin_id) or old[3] < seq:
					self.store[index] = new
					self.history[(new[1],new[2])] = (2,new,origin_id,seq)

			elif old[0] == 1 and (old[3] == seq and old[2] >= origin_id or old[3] < seq):
				self.store.append(new)
				self.sort_store()
		else:
			self.history[(new[1],new[2])] = (2,new,origin_id,seq)
		pass

#------------------------------------------------------------------------------------------------------
# Contact a specific vessel with a set of variables to transmit to it
	def contact_vessel(self, vessel_ip, path, action, value,post_content):
		# the Boolean variable we will return
		success = False
		# The variables must be encoded in the URL format, through urllib.urlencode

		# the HTTP header must contain the type of data we are transmitting, here URL encoded
		headers = {"Content-type": "application/x-www-form-urlencoded"}
		# We should try to catch errors when contacting the vessel
		try:
			# We contact vessel:PORT_NUMBER since we all use the same port
			# We can set a timeout, after which the connection fails if nothing happened
			connection = HTTPConnection("%s:%d" % (vessel_ip, port), timeout = 30)
			# We only use POST to send data (PUT and DELETE not supported)
			action_type = "POST"
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
			print ("Error while contacting %s" % vessel_ip)
			# printing the error given by Python
			print(e)

		# we return if we succeeded or not
		return success
#------------------------------------------------------------------------------------------------------
	# We send a received value to all the other vessels of the system
	def propagate_value_to_vessels(self, path, action, value, post_content):
		# We iterate through the vessel list
		for vessel in self.vessels:
			# We should not send it to our own IP, or we would create an infinite loop of updates
			if vessel != ("10.1.0.%s" % self.vessel_id):
				# A good practice would be to try again if the request failed
				# Here, we do it only once
				self.contact_vessel(vessel, path, action, value, post_content)
#------------------------------------------------------------------------------------------------------

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
		if self.path == "/":
			self.do_GET_Index()
		elif self.path == "/board":
			self.do_GET_Board()
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
	#Constructs the html pages to be rendered
	def make_Page(self):
		entries = self.get_Entries()
		header = board_frontpage_header_template
		content = boardcontents_template %(self.server.start,self.server.end,"Board Contents",entries)
		footer = board_frontpage_footer_template % "fremarl@student.chalmers.se"
		page =  header + content + footer
		self.wfile.write(page)

	#Formats current entries into a string
	def get_Entries(self):
		entries = ""
		for index,msg in enumerate(self.server.store):
			entries += entry_template % ("board/%d"% index,index,msg)
		return entries
#------------------------------------------------------------------------------------------------------
# Request handling - POST
#------------------------------------------------------------------------------------------------------
	def do_POST(self):
		print("Receiving a POST on %s" % self.path)

		data = self.parse_POST_request()
		print data
		if self.path == "/board":
			self.do_POST_New_Entry(data)
		elif re.search(r'\d+',self.path):
			self.do_POST_Edit(data)
		elif self.path == "/propagate":
			self.do_POST_Server(data)

		self.set_HTTP_headers(200)

#------------------------------------------------------------------------------------------------------
# POST Logic
#------------------------------------------------------------------------------------------------------

	#Handels propagation requests
	def do_POST_Server(self,data):
		v_id = int(self.client_address[0].split('.')[3])
		#New entry
		if data["action"][0] == '0':
			#self.server.current_key = int(data["key"][0]) - 1
			self.server.add_value_to_store(int(data["seq"][0]),data["value"][0],v_id)
		#Delete entry
		elif data["action"][0] == '1':
			self.server.delete_value_in_store(int(data["seq"][0]),data["value"][0],v_id)
		#Edit entry
		elif data["action"][0] == '2':
			self.server.modify_value_in_store(int(data["seq"][0]),data["value"][0],v_id)
	#Adds a new entry locally and then propagates it
	def do_POST_New_Entry(self,data):
		self.server.seq_number += 1
		seq = self.server.seq_number
		self.server.add_value_to_store(seq,data["entry"][0],self.server.vessel_id)
		self.new_Thread(0,seq,data["entry"][0])

	#Handels edits and deletes
	def do_POST_Edit(self,data):
		#Get the id of the entry
		msg_id = int(self.path[7:])
		value = data["entry"][0]
		seq = self.server.seq_number
		if data["delete"][0] == "0":
			self.server.modify_value_in_store(seq,value,self.server.vessel_id)
			self.new_Thread(2,seq,value)
		else:
			self.server.delete_value_in_store(seq,value,self.server.vessel_id)
			self.new_Thread(1,seq,value)
	#Starts a new propagation thread
	def new_Thread(self,action, seq, value):
		post_content = urlencode({'action': action, 'seq': seq, 'value': value})
		thread = Thread(target=self.server.propagate_value_to_vessels,args=("/propagate",action, value, post_content) )
		# We kill the process if we kill the server
		thread.daemon = True
		# We start the thread
		thread.start()

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

	vessel_list = []
	vessel_id = 0
	# Checking the arguments
	if len(sys.argv) != 4: # 3 args, the script and the vessel name
		print("Arguments: vessel_ID number_of_vessels port_number")
	else:
		# We need to know the vessel IP
		vessel_id = int(sys.argv[1])
		#Get the port number
		port = int(sys.argv[3])
		# We need to write the other vessels IP, based on the knowledge of their number
		for i in range(1, int(sys.argv[2])+1):
			vessel_list.append("10.1.0.%d" % i) # We can add ourselves, we have a test in the propagation

	# We launch a server
	server = BlackboardServer(('', port), BlackboardRequestHandler, vessel_id, vessel_list)
	print("Starting the server on port %d" % port)

	try:
		server.serve_forever()
	except KeyboardInterrupt:
		server.server_close()
		print("Stopping Server")
#------------------------------------------------------------------------------------------------------
