#!/usr/bin/env python

#!/usr/bin/env python

import socket, errno
import struct
import time

class SourceServerDetails:
    def __init__(self):
        self.map            = ""
        self.dedicated      = ""
        self.is_secure      = False
        self.name           = ""
        self.bot_count      = 0
        self.game_dir       = ""
        self.game_version   = ""
        self.version        = 0
        self.appid          = 0
        self.game_description = ""
        self.player_count   = 0
        self.is_password    = False
        self.os             = ""
        self.max_players    = 0

class SourceServerPlayer:
    def __init__(self):
        self.name           = ""
        self.kills          = 0
        self.time_connected = 0

class SourceServerError(Exception): pass

class SourceServer(object):
   S2C_CHALLENGE = '\x41'
   S2A_PLAYER = '\x44'
   S2A_RULES = '\x45'
   S2A_INFO = '\x49'
   A2A_ACK = '\x6A'

   A2S_INFO = '\xFF\xFF\xFF\xFF\x54Source Engine Query'
   A2S_PLAYER = '\xFF\xFF\xFF\xFF\x55'
   A2S_RULES = '\xFF\xFF\xFF\xFF\x56'
   A2S_SERVERQUERY_GETCHALLENGE = '\xFF\xFF\xFF\xFF\x57'
   A2A_PING = '\xFF\xFF\xFF\xFF\x69'

   SERVERDATA_EXECCOMMAND = 2
   SERVERDATA_AUTH = 3
   SERVERDATA_RESPONSE_VALUE = 0
   SERVERDATA_AUTH_RESPONSE = 2

   """ Class functions """
   # http://developer.valvesoftware.com/wiki/Server_Queries

   def __init__(self, network, port):
      self.connected = False
      self.tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
      try:
        self.tcp.connect((network, port))
      except socket.error, (errorCode, errorMsg):
        print "[SourceServer] TCP connect error. %s: %s" % (errno.errorcode[errorCode], errorMsg)
        return
      
      self.udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
      try:
        self.udp.connect((network, port))
      except socket.error, (errorCode, errorMsg):
        print "[SourceServer] UDP connect error. %s: %s" % (errno.errorcode[errorCode], errorMsg)
        return

      self.connected = True
      self.password = ''
      self.request_id = 1
      self.strBuffer = ""
      self.bufLen = 0

   def settimeout(self, value):
      self.tcp.settimeout(value)
      self.udp.settimeout(value)

   def disconnect(self):
      """Disconnects from server"""
      self.tcp.close()
      self.udp.close()

   def raw_recv_tcp(self):
      while 1:
         strTemp = ""
         try:
            strTemp = self.tcp.recv(1024)
         except socket.error, (errorCode, errorMsg):
            print "[server_query] Error receiving from socket. %s: %s" % (errno.errorcode[errorCode], errorMsg)
         
         recvLen = len(strTemp)
         if recvLen == 0:
            print "[server_query] Lost connection to server."
            return None
        
         self.strBuffer += strTemp
         self.bufLen += recvLen
        
         # Received packet header and length
         while (self.bufLen >= 4):
            # Get packet length
            pktLen, = struct.unpack('<I', self.strBuffer[:4])
            pktLen += 4
            # Break if received buffer is smaller then packet length
            if (self.bufLen < pktLen): break
           
            strPacket = self.strBuffer[:pktLen]
            self.strBuffer = self.strBuffer[pktLen:]
            self.bufLen -= pktLen
              
            return self.parsePacket(strPacket)

   def raw_send_tcp(self, data):
      """Sends raw tcp data to the server"""
      if data:
        p = struct.unpack('<3I', data[:12]) + (data[12:].split('\x00'),)
        print "[raw_send_tcp] len=%d request=%s command=%s strings: %s" % (p[0], p[1], p[2], p[3])
        #debug_packet(data, "[tcp_send]")
        self.tcp.send(data)
      else:
        print "[tcp_send] nothing to send"
      return self.raw_recv_tcp()
      #return self.parsePacket(self.tcp.recv(4108))

   def raw_send_udp(self, data):
      """Sends raw udp data to the server"""
      if data:
         self.udp.send(data)
      return self.udp.recv(4096)

   """ TCP """

   def setRconPassword(self, password):
      """Sets the server RCON password"""
      self.password = password

      print "[setRconPassword] sending auth packet to server..."
      self.raw_send_tcp(self.packet(self.SERVERDATA_AUTH, password, 1234))
      return self.raw_send_tcp(None)[1] == 1234

   def rcon(self, command):
      """Sends an RCON command to the server and returns the result"""
      # Authenticate
      #if not self.setRconPassword(self.password): raise SourceServerError, 'Bad RCON password'
      if self.password == "": raise SourceServerError, 'Blank RCON password'

      print "[SourceServer] Sending RCON command [%s] to server..." % command

      # Send RCON command
      result = filter(bool, self.raw_send_tcp(self.packet(self.SERVERDATA_EXECCOMMAND, command, self.request_id))[~0])
      self.request_id += 1
      return result[~0] if result else None

   """ UDP """

   def get_ping(self):
      """Returns the server ping in milliseconds"""
      starttime = time.time()
      result = self.raw_send_udp(self.A2A_PING)

      if result.startswith('\xFF\xFF\xFF\xFF') and result[4] == self.A2A_ACK:
         return (time.time() - starttime) * 1000

      raise SourceServerError, 'Unexpected server response \'%s\'' % result[4]
   ping = property(get_ping)
   def getChallenge(self):
      """Returns a challenge value for querying the server"""
      result = self.raw_send_udp(self.A2S_SERVERQUERY_GETCHALLENGE)
      if result.startswith('\xFF\xFF\xFF\xFF') and result[4] == self.S2C_CHALLENGE:
         return result[5:]

      raise SourceServerError, 'Unexpected server response \'%s\'' % result[4]

   def get_rules(self):
      """Returns a dictionary of server rules"""
      result = self.raw_send_udp(self.A2S_RULES + self.getChallenge())

      if result.startswith('\xFF\xFF\xFF\xFF') and result[4] == self.S2A_RULES:
         rules = {}
         lines = result[7:].split('\x00')
         for x in range(0, len(lines) - 1, 2):
            rules[lines[x]] = lines[x + 1]

         return rules

      raise SourceServerError, 'Unexpected server response \'%s\'' % result[4]

   def get_details(self):
      """Returns a SourceServerDetails object of server details"""
      result = self.raw_send_udp(self.A2S_INFO)

      if result.startswith('\xFF\xFF\xFF\xFF') and result[4] == self.S2A_INFO:
         details = SourceServerDetails()
         details.version = struct.unpack('<B', result[6])[0]
         lines = result[6:].split('\x00', 4)

         details.name = lines.pop(0)
         details.map = lines.pop(0)
         details.game_dir = lines.pop(0)
         details.game_description = lines.pop(0)

         line = lines.pop(0)
         (details.appid, details.player_count, details.max_players, details.bot_count, details.dedicated,
            details.os, details.is_password, details.is_secure) = struct.unpack('<H3BccBB', line[:9])
         details.game_version = line[9:].split('\x00')[0]

         return details

      raise SourceServerError, 'Unexpected server response \'%s\'' % result[4]

   def get_players(self):
      """Returns a list of SourceServerPlayer objects"""
      result = self.raw_send_udp(self.A2S_PLAYER + self.getChallenge())

      if result.startswith('\xFF\xFF\xFF\xFF') and result[4] == self.S2A_PLAYER:
         playercount = struct.unpack('<B', result[5])[0]

         index, x = 0, 6
         players = {}
         resultlen = len(result)
         while x < resultlen:
            index = struct.unpack('<B', result[x])[0]
            if index in players:
               x += 5
               continue

            currentplayer = players[index] = SourceServerPlayer()
            y = result.find('\x00', x + 1)
            if y == -1: raise SourceServerError, 'Error parsing player information'

            currentplayer.name = result[x + 1:y]
            currentplayer.kills, currentplayer.time_connected = struct.unpack('<BB', result[y + 1:y + 3])
            x = y + 4

         return players

      raise SourceServerError, 'Unexpected server response \'%s\'' % result[4]
   players = property(get_players)
   """ Data format functions """

   @staticmethod
   def packet(command, strings, request):
      """Compiles a raw packet string to send to the server"""
      if isinstance(strings, str): strings = (strings,)
      result = struct.pack('<II', request, command) + ''.join([x + '\x00' for x in strings])
      return struct.pack('<I', len(result)) + result

   @staticmethod
   def parsePacket(data):
      # Lengeth, Request, Command, Strings
      if not data:
        print "[parsePacket] empty packet"
        return None
      p = struct.unpack('<3I', data[:12]) + (data[12:].split('\x00'),)
      print "[parsePacket] len=%d request=%s command=%s strings: %s" % (p[0], p[1], p[2], p[3])
      return p


def debug_packet(data, heading = ""):
    out = ""
    if heading != "": out = heading + " "
    for b in data:
            append = "%x" %ord(b)
            if len(append) == 1: append = "0%s" %append
            out += append + " "
    print out

if __name__ == "__main__":
    import the_dynamic_config
    import config
    print "Configuring IS server via RCON..."
    server = SourceServer(config.servers[0][0], config.servers[0][1])
    if not server.setRconPassword(config.IS.rcon_password):
        self.send_message("Invalid RCON password for server! Unable to configure server. Oh no!")
    else:
        server.rcon("sm_map pl_goldrush")
        server.rcon("sv_password games")
        