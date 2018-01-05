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
import ast
import byzantine_behavior
#------------------------------------------------------------------------------------------------------
# Global variables for HTML templates
vote_frontpage_template = ""
vote_result_template = ""

#------------------------------------------------------------------------------------------------------
port = 0
#------------------------------------------------------------------------------------------------------
#What to do on a tie
ON_TIE = True

#------------------------------------------------------------------------------------------------------
#------------------------------------------------------------------------------------------------------
class BlackboardServer(HTTPServer):
#------------------------------------------------------------------------------------------------------
	def __init__(self, server_address, handler, node_id, vessel_list):
	# We call the super init
		HTTPServer.__init__(self,server_address, handler)
		# we create the dictionary of values
		# this will contain a vote vector of each vessel
		self.votes = {}
		# Contains our profile e.g attack,retreat or byzantine
		self.profile = -1

		# Keep a list of the byzantine nodes
		self.byzantine = {}
		# We keep a variable of the next id to insert
		self.current_key = -1

		# our own ID (IP is 10.1.0.ID)
		self.vessel_id = vessel_id
		# The list of other vessels
		self.vessels = vessel_list

		self.votes[vessel_id] = {}
#------------------------------------------------------------------------------------------------------
    # We add a value received to the store
	def add_vessel_vote(self, vote, vessel_id):
		self.votes[self.vessel_id][vessel_id] = vote

	# We add vote vector from vessel
	def add_vessel_votes(self, votes, vessel_id):
		self.votes[vessel_id] = votes

#------------------------------------------------------------------------------------------------------
# Contact a specific vessel with a set of variables to transmit to it
	def contact_vessel(self, vessel_ip, path, post_content):
		# the Boolean variable we will return
		success = False
		# The variables must be encoded in the URL format, through urllib.urlencode

		# the HTTP header must contain the type of data we are transmitting, here URL encoded
		headers = {"Content-type": "application/x-www-form-urlencoded"}
		# We should try to catch errors when contacting the vessel
		try:
			# We contact vessel:PORT_NUMBER since we all use the same port
			# We can set a timeout, after which the connection fails if nothing happened
			connection = HTTPConnection("10.1.0.%s:%d" % (vessel_ip, port), timeout = 30)
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
	def propagate_value_to_vessels(self, path, post_content):
		# We iterate through the vessel list
		for vessel in self.vessels:
			# We should not send it to our own IP, or we would create an infinite loop of updates
			if vessel != self.vessel_id:
				# A good practice would be to try again if the request failed
				# Here, we do it only once
				self.contact_vessel(vessel, path, post_content)

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
		#print("Receiving a GET on path %s" % self.path)
		# Here, we should check which path was requested and call the right logic based on it
		if self.path == "/":
			self.do_GET_Index()
		elif self.path == "/vote/result":
			self.do_GET_Results()
#------------------------------------------------------------------------------------------------------
# GET logic - specific path
#------------------------------------------------------------------------------------------------------
	def do_GET_Index(self):
		# We set the response status code to 200 (OK)
		self.set_HTTP_headers(200)
		self.make_Page()

	# Return the results of the vote
	def do_GET_Results(self):
		self.set_HTTP_headers(200)
		result_page = "<pre>Voting Results ...</pre>"
		if len(self.server.votes) == len(self.server.vessels):
			result_page = self.format_result()
		self.wfile.write(result_page)
	#Constructs the html pages to be rendered
	def make_Page(self):
		frontpage = vote_frontpage_template
		self.wfile.write(frontpage)

	# Formats the vote results
	def format_result(self):
		result_vector = self.calc_result_vector()
		result_page = "<h1>%s</h1>" % self.calc_result(result_vector)
		result_page += vote_result_template % result_vector
		return result_page
#------------------------------------------------------------------------------------------------------
# Request handling - POST
#------------------------------------------------------------------------------------------------------
	def do_POST(self):
		print("Receiving a POST on %s" % self.path)
		data = self.parse_POST_request()
		if self.path == "/vote/attack":
			self.do_POST_Attack()
		elif self.path == "/vote/retreat":
			self.do_POST_Retreat()
		elif self.path == "/vote/byzantine":
			self.do_POST_Byzantine()
		elif self.path == "/vote/result":
			self.do_POST_Results(data)
		elif self.path == "/reset":
			self.do_RESET()

		self.set_HTTP_headers(200)

#------------------------------------------------------------------------------------------------------
# POST Logic
#------------------------------------------------------------------------------------------------------
	# Resets everything to do a complete new try
	def do_RESET(self):
		self.server.profile = -1
		self.server.votes.clear()
		self.server.votes[self.server.vessel_id] = {}
		self.server.byzantine.clear()

	# Set the vessel to vote an honest attack
	def do_POST_Attack(self):
		self.set_vote(1)

	# Set the vessel to vote an honest retreat
	def do_POST_Retreat(self):
		self.set_vote(0)

	# Set vessel to be dishonest
	def do_POST_Byzantine(self):
		self.server.profile = 2
		self.server.add_vessel_vote(2,self.server.vessel_id)
		self.server.byzantine[self.server.vessel_id] = 1
		self.new_Thread(2,2)
		self.round_one_complete()

	def set_vote(self,vote):
		self.server.profile = vote
		self.server.add_vessel_vote(vote,self.server.vessel_id)
		self.new_Thread(0,vote)
		self.round_one_complete()

	# Does round 2 when round 1 is "complete"
	def round_one_complete(self):
		# Way to check if we have gathered everything if vessel is byzantine
		num_byz = len(self.server.byzantine) if self.server.profile == 2 else 0
		if (len(self.server.votes[self.server.vessel_id]) + num_byz) == len(self.server.vessels):
			if self.server.profile == 2:
				total = len(self.server.vessels)
				num_loyal = total - len(self.server.byzantine)
				# Send to all loyal nodes what we vote and then the result vectors
				self.send_byz_votes(byzantine_behavior.compute_byzantine_vote_round1(num_loyal,total,ON_TIE))
				self.send_byz_vectors(byzantine_behavior.compute_byzantine_vote_round2(num_loyal,total,ON_TIE))
			else:
				# Send our result vectors to everyone
				self.new_Thread(1,self.server.votes[self.server.vessel_id])

	# Calculates the result vector
	def calc_result_vector(self):
		result_vector = []
		for v_id in self.server.vessels:
			attack = 0
			retreat = 0
			for vote in self.server.votes:
				if self.server.votes[vote][v_id] == 1:
					attack += 1
				else:
					retreat += 1
			if attack > retreat:
				result_vector.append(1)
			elif attack < retreat:
				result_vector.append(0)
			else:
				result_vector.append(-1)
		return result_vector
	# Using the result vector we decide what to do
	def calc_result(self,result_vector):
		attack = 0
		retreat = 0
		for vote in result_vector:
			if vote == 1:
				attack += 1
			elif vote == 0:
				retreat += 1
		if attack > retreat:
			return "ATTACK"
		elif attack < retreat:
			return "RETREAT"
		else:
			# On tie we attack
			return "ATTACK"
	# Send vote to every one that is not byzantine
	def send_byz_votes(self,data):
		index = 0
		for v_id in self.server.vessels:
			if v_id not in self.server.byzantine:
				self.send_to_vessel(v_id,0,int(data[index]))
				index += 1
	# Send votes to every one that is not byzantine
	def send_byz_vectors(self,data):
		index = 0
		for v_id in self.server.vessels:
			if v_id not in self.server.byzantine:
				res = {}
				for inner_i, vessel_vote in enumerate(data[index]):
					res[inner_i + 1] = int(vessel_vote)
				self.send_to_vessel(v_id,1,res)
				index += 1

	def do_POST_Results(self,data):
		v_id = int(self.client_address[0].split('.')[3])

		if data["type"][0] == '0':
			self.server.add_vessel_vote(int(data["value"][0]),v_id)
			self.round_one_complete()
		elif data["type"][0] == '1':
			votes = ast.literal_eval(data["value"][0])
			self.server.add_vessel_votes(votes,v_id)
		elif data["type"][0] == '2':
			self.server.byzantine[v_id] = 1
			self.round_one_complete()


	#Starts a new propagation thread
	def new_Thread(self, t, value):
		post_content = urlencode({'type': t, 'value': value})
		thread = Thread(target=self.server.propagate_value_to_vessels,args=("/vote/result", post_content) )
		# We kill the process if we kill the server
		thread.daemon = True
		# We start the thread
		thread.start()

	# Sends to one vessel only
	def send_to_vessel(self, vessel, t, votes):
		post_content = urlencode({'type': t, 'value': votes})
		thread = Thread(target=self.server.contact_vessel,args=(vessel,"/vote/result", post_content) )
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
	vote_frontpage_template = file("server/vote_frontpage_template.html").read()
	vote_result_template = file("server/vote_result_template.html").read()

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
			vessel_list.append(i) # We can add ourselves, we have a test in the propagation

	# We launch a server
	server = BlackboardServer(('', port), BlackboardRequestHandler, vessel_id, vessel_list)
	print("Starting the server on port %d" % port)

	try:
		server.serve_forever()
	except KeyboardInterrupt:
		server.server_close()
		print("Stopping Server")
#------------------------------------------------------------------------------------------------------
