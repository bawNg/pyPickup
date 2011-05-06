#!/usr/bin/env python

import time
import urllib, urllib2
from thread_pool import *

class ControlCode:
    all_talk_off = 1
    all_talk_on  = 2
    quick_restart= 3
    change_map   = 4
    message      = 5
    password     = 6

class Controller(object):
    def __init__(self, username, password):
        self.url_login = "http://games.saix.net/pickup_tf2_user_login.php"
        self.url_control = "http://games.saix.net/pickup_tf2_server_control.php"

        self.http_headers = {"Content-type": "application/x-www-form-urlencoded"}
        self.post_login_data = {'login': 'Login', 'nickname': username, 'password': password}
        self.post_login_data = urllib.urlencode(self.post_login_data)
        self._get_sessionid()
        self._login()

    def _get_sessionid(self):
        http_request = urllib2.Request(self.url_login, None, self.http_headers)
        try:
            f = urllib2.urlopen(http_request)
        except urllib2.HTTPError, e:
            print "[get_sessionid] Unable to connect. Error code: %d (%.2f seconds)" % (e.code, (time.time() - timestamp))
            return False
        if 'Set-Cookie' in f.info(): self.http_headers['Cookie'] = f.info()['Set-Cookie']

    def _login(self):
        http_request = urllib2.Request(self.url_login, self.post_login_data, self.http_headers)
        print "[SaixGameServerController] (login) Connecting to server [%s]..." % http_request.get_full_url()
        timestamp = time.time()
        try:
            f = urllib2.urlopen(http_request)
        except urllib2.HTTPError, e:
            print "[SaixGameServerController] (login) Unable to connect. Error code: %d (%.2f seconds)" % (e.code, (time.time() - timestamp))
            return False
        print "[SaixGameServerController] (login) Sent login info. (%.2f seconds)" % (time.time() - timestamp)
        if 'Set-Cookie' in f.info(): self.http_headers['Cookie'] = f.info()['Set-Cookie']
        return True

    def send_command(self, server_number, control_code, command):
        server_id = -1
        if server_number == 1: server_id = 157
        if server_number == 2: server_id = 158
        if server_id == -1: return False

        post_data = {'command': command, 'ctr': control_code, 'pickup_rcon_command_send': 'Send Command To Server', 'serverid': server_id}
        http_request = urllib2.Request(self.url_control, urllib.urlencode(post_data), self.http_headers)
        print "[SaixGameServerController] (send_command) Connecting to server [%s]..." % http_request.get_full_url()
        timestamp = time.time()
        try:
            f = urllib2.urlopen(http_request)
        except urllib2.HTTPError, e:
            print "[SaixGameServerController] (send_command) Unable to connect. Error code: %d (%.2f seconds)" % (e.code, (time.time() - timestamp))
            return False
        print "[SaixGameServerController] (send_command) Sent command. (%.2f seconds)" % (time.time() - timestamp)
        if 'Set-Cookie' in f.info(): self.http_headers['Cookie'] = f.info()['Set-Cookie']
        page_source = f.read()
        if "Command Sent To Server." in page_source: return True
        dump_file = open("SaixGameServerController.dump", "wb")
        dump_file.write(page_source)
        dump_file.close()

        return False

class ControllerInterface(object):
    def __init__(self, username, password):
        self.thread_pool = ThreadPool(1)
        self.username = username
        self.password = password

    def dispatch_controller_command(self, server_number, control_code, command):
        self.thread_pool.queueTask(self.controller_send_command, (server_number, control_code, command))

    def controller_send_command(self, data):
        server_number, control_code, command = data
        controller = Controller(self.username, self.password)
        for i in xrange(1, 5):
            if controller.send_command(server_number, control_code, command):
                break
            print "[ControllerInterface] send_command failed. retrying (%d) more times..." % 5 - i
            print "[ControllerInterface] server [%d] control_code [%d] command [%s]" % (server_number, control_code, command)

    def set_all_talk(self, server_number, on):
        self.dispatch_controller_command(server_number, (ControlCode.all_talk_on if on else ControlCode.all_talk_off), "")
    def quick_restart(self, server_number):
        self.dispatch_controller_command(server_number, ControlCode.quick_restart, "")
    def change_map(self, server_number, map_name):
        self.dispatch_controller_command(server_number, ControlCode.change_map, map_name)
    def send_message(self, server_number, message_text):
        self.dispatch_controller_command(server_number, ControlCode.message, message_text)
    def set_password(self, server_number, password):
        self.dispatch_controller_command(server_number, ControlCode.password, password)