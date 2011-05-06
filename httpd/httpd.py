#!/usr/bin/env python

import posixpath, json, time, re, sys
from SocketServer import TCPServer
from SimpleHTTPServer import SimpleHTTPRequestHandler
from cgi import escape
from urllib import unquote_plus
from urlparse import parse_qs
from string import Template
from events import Events
import template
from model import User, config

#TODO: make update_template_attribute work for lists

def get_file_contents(filename):
    f = open(filename)
    data = f.read()
    f.close()
    return data

def update_template_attribute(category, name, value):
    contents = get_file_contents("template.py")
    
    match = re.search("([\\s\\S]*class "+category+":\\n)([\\s\\S]*?)(class .*?:[\\s\\S]*)", contents)
    groups = match.groups()
    line = re.search("(.*"+name+" = )(.+)(\n[\\s\\S]*)", groups[1]).groups()
    d = line[1][:1]
    output = groups[0] + line[0] + d + value + d + line[2] + groups[2]
    
    f = open("template.py", "w")
    f.write(output)
    f.close()
    
    return output == contents

class HTTPHandler(SimpleHTTPRequestHandler):    
    def guess_type(self, path):
        base, ext = posixpath.splitext(path)
        if ext == ".js": return "text/javascript; charset=UTF-8"
        if ext == ".css": return "text/css; charset=UTF-8"
        if ext == ".gif": return "text/image"
        SimpleHTTPRequestHandler.guess_type(self, path)
    
    def do_POST(self):
        data = self.rfile.read(int(self.headers['Content-Length']))
        if data:
            data = parse_qs(data)
            for key, value in data.items():
                if len(value) == 1: data[key] = value[0]
        print "[do_POST] Received data: %s" % data
        
        if self.path in ["/auth", "/update"]:
            self.send_response(200)
            self.send_header("Content-Type", "text/json; charset=UTF-8")
            self.end_headers()
        
        if self.path == "/auth":
            if data['request'] == "check":
                pass #if config.
            elif data['request'] == "auth":
                nickname = data['nickname']
                if self.client_address[0] not in self.server.auth_requests:
                    self.server.auth_requests[self.client_address[0]] = []
                
                failure_count = 0
                if len(self.server.auth_requests[self.client_address[0]]) > 1:
                    for request in self.server.auth_requests[self.client_address[0]]:
                        if (time.time() - request[1]) < (60 * 60): failure_count += 1
                
                if failure_count >= 2:
                    self.wfile.write("{'status': 'banned'}")
                    return
                
                self.server.auth_requests[self.client_address[0]].append((nickname, time.time()))
                
                self.server.status[nickname] = "requesting"
                self.wfile.write("{'status': '%s'}" % self.server.status[nickname])
                self.server.events.on_auth_request(nickname)
                
            elif data['request'] == "update":
                nickname = data['nickname']
                if nickname not in self.server.status.keys():
                    self.wfile.write("{'status': 'error'}")
                    return
                
                if self.server.status[nickname] == "online":
                    self.wfile.write("{'status': 'requesting'}")
                    return
                
                if self.server.status[nickname] == "updated":
                    user = User.find_one({'nickname': nickname})
                    if user.last_ip_address == self.client_address[0]:
                        self.server.status[nickname] = "authorized"
                    else:
                        self.server.status[nickname] = "denied"
                self.wfile.write("{'status': '%s'}" % self.server.status[nickname])
        elif self.path == "/update":
            name = data['name']
            values  = data['values[]']
            category = getattr(template, data['category'])
            setattr(category, name, values)
            
            # update the file
            update_template_attribute(category, name, values)
            
            self.wfile.write(json.dumps(values))
    
    def do_GET(self):
        if not config.web_interface.is_enabled:
            self.send_response(204)
            self.end_headers()
            return
        
        base, ext = posixpath.splitext(self.path)
        if ext != "":
            SimpleHTTPRequestHandler.do_GET(self)
            return
        
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=UTF-8")
        self.end_headers()
        
        if not self.is_authorized():
            self.wfile.write(self.get_auth_html())
            return
        
        self.wfile.write(self.get_template_page_html())
    
    def get_auth_html(self):
        html = get_file_contents("login.html")
        return html
            
    def get_template_page_html(self):
        html = get_file_contents("index.html")
        template_html = ""
        id = 0
        for category_name in dir(template):
            if category_name.startswith("__") or category_name.startswith("DBGPHide"): continue
            category = getattr(template, category_name)
            template_html += "<div class=\"span-24 last menu_head\">%s</div>\n" % category_name.capitalize()
            template_html += '<div class="menu_body">'
            for attr in dir(category):
                if attr.startswith("__"): continue
                lines = getattr(category, attr)
                if type(lines) != list: lines = [lines]
                partial = "<div class=\"span-4\"><strong>%s</strong></div>" % escape(attr)
                for i in xrange(len(lines)):
                    if i > 0: partial += "<div class=\"span-4\">&nbsp;</div>"
                    value = "<span id=\"value_%s_%s\" class=\"editable value_%s\">%s</span>" % (id, i, id, escape(str(lines[i]).strip()))
                    partial += "<div class=\"span-20 last\">%s</div>" % value
                
                template_html += "%s\n" % partial
                id += 1
            template_html += "</div>\n"
        
        return html.replace("${template}", template_html)
    
    def is_authorized(self):
        user = User.find_one({'last_ip_address': self.client_address[0]})
        if user: return True
        return False

class HTTPServer_Events(Events):
    __events__ = ['on_auth_request']
class HTTPServer(TCPServer):
    def __init__(self, address, port):
        TCPServer.__init__(self, (address, port), HTTPHandler)
        print "HTTPServer started listening on port %d..." % port
        self.events = HTTPServer_Events()
        self.status = {}
        self.auth_requests = {}


if __name__ == "__main__":
    httpd = HTTPServer("", 8888)
    #httpd.timeout = 0.1
    
    #while 1:
    #    httpd.handle_request()
    httpd.serve_forever()

