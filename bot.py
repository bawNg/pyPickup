#!/usr/bin/env python

import sys, string, traceback, bz2, time
from ircbot import SingleServerIRCBot
from irclib import nm_to_n, nm_to_h, irc_lower, ip_numstr_to_quad, ip_quad_to_numstr
from server_query import *
from pickup_game import PickupGame, PickupServer, PickupPlayer, PickupClass
from command_handler import *
import template as message
import saix
from model import config, User, Game
import config as default_config
from httpd import HTTPServer
from plural import pluralized

class TopicStatus:
    default = 0
    game_started = 1
    game_in_progress = 2

class TF2PickupBot(SingleServerIRCBot):
    def __init__(self, channel, nickname, server, port=6667):
        SingleServerIRCBot.__init__(self, [(server, port)], nickname, nickname)
        self.channel         = channel
        self.connection.add_global_handler("all_events", self.on_all_events, -100)
        self.topic_status    = TopicStatus.default
        self.channel_admins  = []
        self.game            = None
        self.scheduled_games = []
        self.next_game_time  = None
        self.command_handler = Command_Handler(self)
        self.httpd           = HTTPServer("", config.web_interface.port)
        self.httpd.timeout   = 0.1
        self.httpd.events.on_auth_request += self.httpd_on_auth_request
        self.saix_controller = saix.ControllerInterface(config.saix_web_username, config.saix_web_password)
        self.startup_time    = time.time()
    
    ### HTTPD Events ###
    def httpd_on_auth_request(self, nickname):
        if not self.is_admin(nickname):
            self.httpd.status[nickname] = "not_admin"
            return
        
        self.connection.who(nickname) 
        
    def send_dcc_auth(self, nickname):
        self.send_notice(nickname, "Please accept the DCC chat request to authenticate your IP for the admin web interface.")
        
        print "[httpd_on_auth_request] Attempting to get external IP address..."
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect(("whatsmyip.co.za",80))
            s.settimeout(1)
            external_ip = s.getsockname()[0]
            s.close()
            print "[httpd_on_auth_request] Successfully fetched external IP: %s" % external_ip
            dcc = self.ircobj.dcc()
            dcc.previous_buffer = "" 
            dcc.handlers = {} 
            dcc.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM) 
            dcc.passive = 1 
            dcc.socket.bind((external_ip, 0)) 
            dcc.localaddress, dcc.localport = dcc.socket.getsockname() 
            dcc.socket.listen(10) 
            self.dcc_connections.append(dcc)
        except socket.error:
            print "[httpd_on_auth_request] Failed to get external IP. Binding to default."
            dcc = self.dcc_listen()
        
        dcc.nick = nickname
        self.connection.ctcp("DCC", nickname, "CHAT chat %s %s" % (ip_quad_to_numstr(dcc.localaddress), dcc.localport))
    
    ### IRC Events ###
    def on_all_events(self, c, e):
        if e.eventtype() != "all_raw_messages":
            print e.source(), e.eventtype().upper(), e.target(), e.arguments()

    def on_welcome(self, c, e):
        c.mode(c.get_nickname(), "+B")

    def on_nicknameinuse(self, c, e):
        for n in config.irc.nickname:
            if n != c.get_nickname():
                c.nick(n)
                break
        if c.get_nickname() != config.irc.nickname[0]:
            c.nick(config.irc.nickname[0])
        c.nick(c.get_nickname() + "_")

    def on_privmsg(self, c, e):
        msg = e.arguments()[0]
        if (msg[:1] == "!") and ((msg.find("!",1,4) & msg.find("?",1,4)) == -1):
            msg = msg[1:]
        self.command_handler.process_command(e, msg)

    def on_pubmsg(self, c, e):
        msg = e.arguments()[0]
        a = msg.split(":", 1)
        if len(a) > 1 and irc_lower(a[0]) == irc_lower(c.get_nickname()):
            self.command_handler.process_command(e, a[1].strip())
        elif msg[:1] == "!" and ((msg.find("!",1,4) & msg.find("?",1,4)) == -1):
            self.command_handler.process_command(e, msg[1:])

    def on_privnotice(self, c, e):
        nick = nm_to_n(e.source())
        msg  = e.arguments()[0]
        if (nick == "NickServ") and \
        (msg.startswith("This nickname is registered and protected.")):
            c.privmsg(nick, "identify %s" % config.irc.password)
            c.join(self.channel)

    def on_kick(self, c, e):
        self.on_part(c, e) # fixxx

    def on_join(self, c, e):
        nick = nm_to_n(e.source())
        if nick == c.get_nickname(): return
        self.send_notice(nick, message.channel.join)
        
        articles = News_Article.find().sort('created_at', -1)
        self.send_notice(nick, message.news.header, channel=self.channel)
        
        article_count = articles.count()
        for i in xrange(3):
            if i > article_count - 1: break
            article = articles[i]
            self.send_notice(nick, message.news.line, author=article.author, body=article.body, \
                             date=datetime.datetime.strftime(article.created_at, "%d/%m/%Y"))
        
    def on_part(self, c, e):
        nick = nm_to_n(e.source())
        if e.eventtype() == "kick": nick = e.arguments()[0]
        if self.game:
            if self.game.contains_player(nick):
                if not self.game.is_in_progress: self.game.remove_player(nick)
        if nick.lower() in self.channel_admins: self.channel_admins.remove(nick.lower())

    def on_nick(self, c, e):
        target  = e.target()
        nick    = nm_to_n(e.source())
        
        if self.is_admin(nick):
            if nick.lower() in self.channel_admins: self.channel_admins.remove(nick.lower())
            self.channel_admins.append(target)
            
        if self.game:
            if self.game.contains_player(nick):
                if not self.game.is_in_progress: self.game.remove_player(nick)
                if nick == self.game.owner: self.game.owner = target

    def on_quit(self, c, e):
        self.on_part(c, e)

    def on_namreply(self, c, e):
        for name in e.arguments()[2].split():
            if name.startswith('~') or name.startswith('&') or \
               name.startswith('@') or name.startswith('%'):
                self.channel_admins.append(name[1:].lower())

    def on_mode(self, c, e):
        nick = nm_to_n(e.source())
        args = e.arguments()[0]
        param = 0
        for mode in args:
            if mode == "+": add = True
            if mode == "-": add = False
            if mode.lower() in ['q', 'a', 'o', 'h']:
                if not e.arguments()[param].lower() in self.channel_admins: self.channel_admins.append(e.arguments()[param].lower())
            param += 1
            
    def on_whoreply(self, c, e):
        nick = e.arguments()[1]
        if self.httpd.status.has_key(nick):
            if self.httpd.status[nick] == "requesting":
                self.httpd.status[nick] = "online"
    
    def on_endofwho(self, c, e):
        nick = e.arguments()[0]
        if self.httpd.status.has_key(nick):
            if self.httpd.status[nick] == "requesting":
                self.httpd.status[nick] = "offline"
            elif self.httpd.status[nick] == "online":
                self.send_dcc_auth(nick)
    
    def on_dcc_connect(self, c, e):
        #user = User.find_one({'nickname': c.nick})
        user = User.find_or_create_by_nick(c.nick)
        user.last_ip_address = e.source()
        user.save()
        print "[on_dcc_connect] Updated ip address from nickname [%s] to [%s]." % (c.nick, e.source())
        c.privmsg("Your IP has been authorized for web interface access.")
        c.disconnect()
        self.httpd.status[c.nick] = "updated"
        
    ### Wrapper Methods ###
    def _format_message(self, msg, tokens):
        if ("$" in msg) and tokens: msg = string.Template(msg).substitute(tokens)
        msg = msg.replace("#B", chr(2)).replace("#C", chr(3))
        msg = msg.replace("#O", chr(15)).replace("#R", chr(22))
        msg = msg.replace("#U", chr(31))
        
        def replace_with_pluralized(m):
            pluralized_word = pluralized(int(m.group(1)), m.group(3)[:len(m.group(3))-3])
            return m.group(1) + m.group(2) + pluralized_word
        
        return re.sub(r'(\d)(\W*?)(\S+\(s\))', replace_with_pluralized, msg)

    def send_message(self, *args, **tokens):
        target, msgs = self.channel, args[0]
        if len(args) == 2:
            target = args[0]
            msgs = args[1]
        if type(msgs) != list: msgs = [str(msgs)]
        for msg in msgs:
            msg = self._format_message(msg, tokens)
            self.connection.privmsg(target, msg)

    def send_notice(self, target, msg, **tokens):
        msgs = msg
        if type(msg) != list: msgs = [str(msg)]
        for msg in msgs:
            msg = self._format_message(msg, tokens)
            self.connection.notice(target, msg)

    def reset_modes(self):
        voiced_nicks = self.channels[self.channel].voiced()
        self.devoice_users(voiced_nicks, True)

    def devoice_everyone(self, unmoderate=False):
        self.devoice_users(self.channels[self.channel].voiced(), unmoderate)

    def set_topic(self, topic, **tokens):
        self.connection.topic(self.channel, self._format_message(topic, tokens))

    def set_modes(self, modes):
        self.connection.mode(self.channel, modes)

    def set_moderated(self, moderated=True):
        self.set_modes("%sm" % ('+' if moderated else '-'))

    def voice_users(self, targets):
        for start in xrange(0, len(targets), 12):
            end = start+12
            if len(targets) < end: end = len(targets)
            nicks = ""
            for t in targets[start:end]: nicks += "%s " % t
            modes = "+%s %s" % ('v'*(end-start), nicks)
            self.set_modes(modes)

    def devoice_users(self, targets, unmoderate=False):
        for start in xrange(0, len(targets), 12):
            end = start+12
            if len(targets) < end: end = len(targets)
            nicks = ""
            for t in targets[start:end]: nicks += "%s " % t
            modes = "-%s %s" % ('v'*(end-start), nicks)
            if unmoderate: modes = "-m%s" % modes[1:]
            self.set_modes(modes)

    ### Game Events ###
    def game_on_display_teams(self, g):
        self.send_message(g.get_players_message())

    def game_on_player_added(self, g, player):
        if not g.is_highlander:
            self.send_notice(player.name, message.player.added, team=player.team_name)
        else:
            self.send_notice(player.name, message.player.added_highlander, player_class=player.class_name)
        
        g.delay_display_teams()
        if not g.has_configured_server:
            if g.player_count >= (g.max_players - (g.max_players / 4)):
                # atleast three quarters of the game is full
                self.game_configure_server()

    def game_on_player_removed(self, g, player):
        self.send_notice(player.name, message.player.removed)
        g.delay_display_teams()

    def game_on_game_full(self, g):
        self.send_message(message.game.full, secs=config.time_before_close)

    def game_on_game_in_progress(self, g):
        for player in g.players:
            self.send_message(player.name, message.game.in_progress, server=g.server.name, password=g.password, \
                              ip=g.server.address[0], port=g.server.address[1])
            
            user = User.find_or_create_by_nick(player.name)
            if not user.games_played: user.games_played = 0
            user.games_played += 1
            user.save()
        
        user = User.find_or_create_by_nick(g.owner)
        if not user.games_admined: user.games_admined = 0
        user.games_admined += 1
        user.save()
        
        game_mode = "highlander" if g.is_highlander else "%sv%s" % (g.max_players / 2, g.max_players / 2)
        team_groups = (g.get_class_groups() if g.is_highlander else g.get_team_groups())
        team_groups = dict(map(lambda k: (str(k), team_groups[k]), team_groups))
        game = Game(created_at=datetime.datetime.now(), mode=game_mode, server=g.server.name, \
                    map=g.map, admin=g.owner, teams=team_groups)
        game.save()

        #self.set_topic_game_inprogress()
        self.game_end()

        self.send_message(message.game.sent_password)

    ### Game Methods ###
    def get_next_game_info(self):
        if self.scheduled_games:
            time_struct = time.localtime(self.scheduled_games[0][0])
            next_game_time = time.strftime("%I:%M %p", time_struct)
            next_game_map = "no map selected"
            if self.scheduled_games[0][2] is not None: next_game_map = self.scheduled_games[0][2]
            return (next_game_time, next_game_map)
        return (None, None)

    def topic_update_scheduled_game(self):
        if self.topic_status == TopicStatus.game_started: return

        topic = message.topic.base
        if self.topic_status == TopicStatus.default:
            topic += message.topic.seperator + message.topic.default
        elif self.topic_status == TopicStatus.game_in_progress:
            topic += message.topic.seperator + message.topic.game_in_progress

        next_game_time, next_game_map = self.get_next_game_info()
        if next_game_time: topic += message.topic.seperator + message.topic.next_game

        game_server, game_map = None, None
        if self.game: game_server, game_map = self.game.server.name, self.game.map

        self.set_topic(topic, server=game_server, map=game_map, next_time=next_game_time, next_map=next_game_map)

    def set_topic_default(self):
        topic = message.topic.base + message.topic.seperator + message.topic.default
        next_game_time, next_game_map = self.get_next_game_info()
        if next_game_time: topic += message.topic.seperator + message.topic.next_game
        self.set_topic(topic, next_time=next_game_time, next_map=next_game_map)
        self.topic_status = TopicStatus.default

    def set_topic_game_started(self):
        mode_name = "highlander" if self.game.is_highlander else "%sv%s" % (self.game.max_players / 2, self.game.max_players / 2)
        topic = message.topic.base + message.topic.seperator + message.topic.game_started
        self.set_topic(topic, owner=self.game.owner, mode=mode_name, server=(self.game.server.name if self.game.server else "some server"), map=self.game.map)
        self.topic_status = TopicStatus.game_started

    def set_topic_game_inprogress(self):
        topic = message.topic.base + message.topic.seperator + message.topic.game_in_progress
        next_game_time, next_game_map = self.get_next_game_info()
        if next_game_time: topic += message.topic.seperator + message.topic.next_game
        self.set_topic(topic, server=self.game.server.name, mode=self.game.mode, map=self.game.map, \
                              next_time=next_game_time, next_map=next_game_map)
        self.topic_status = TopicStatus.game_in_progress

    def game_start(self, who, map_name, max_players, is_highlander=False):
        self.game = PickupGame(who, map_name, max_players, is_highlander)
        g_events = self.game.events
        g_events.on_display_teams   += self.game_on_display_teams
        g_events.on_player_added    += self.game_on_player_added
        g_events.on_player_removed  += self.game_on_player_removed
        g_events.on_game_full       += self.game_on_game_full
        g_events.on_game_in_progress+= self.game_on_game_in_progress

        self.next_game_time = None

        # announce that game has been started
        self.send_message(message.game.started, map=self.game.map)

        self.game_select_server()
        self.set_topic_game_started()
        if not self.game.server: self.send_message(message.server.none_available, owner=self.game.owner)

    def game_end(self):
        self.game = None
        if self.topic_status != TopicStatus.default:
            self.set_topic_default()

    def game_select_server(self):
        n = 0 #-1 #skip IS
        for server_address in config.servers:
            n += 1
            server = SourceServer(server_address[0], server_address[1])
            if not server.connected: continue
            # check there are people playing on this server
            if len(server.players) > 5: continue
            server_details = server.get_details()

            server_type = PickupServer.Type.UNKNOWN
            if "SGS TF2" in server_details.name: server_type = PickupServer.Type.SAIX
            if re.match(r'\-IS(\-)? TF2', server_details.name): server_type = PickupServer.Type.IS

            self.game.server = PickupServer(n, server_type, server_address, server_details.name)
            return True

        # no server can be found
        return False

    def game_configure_server(self):
        self.game.has_configured_server = True
        if self.game.server.type == PickupServer.Type.SAIX:
            print "Configuring SGS server via web interface..."
            self.saix_controller.change_map(self.game.server.id, self.game.map)
            self.saix_controller.set_password(self.game.server.id, self.game.password)
            
        elif self.game.server.type == PickupServer.Type.IS:
            print "Not configuring server..."; return
            print "Configuring IS server via RCON..."
            server = SourceServer(self.game.server.address[0], self.game.server.address[1])
            if not server.connected:
                self.send_message(message.server.cannot_connect + " " + message.server.change_or_configure, owner=self.game.owner)
                return
            if not server.setRconPassword(config.is_rcon_password):
                self.send_message("Invalid RCON password for server! Unable to configure server. Oh no!")
                return
            server.rcon("sm_map " + self.game.map)
            #server.rcon("sv_password " + self.game.password)
        else:
            self.send_message(message.server.unknown, owner=self.game.owner)
            self.game.has_configured_server = False

    def process_scheduled_games(self):
        while self.scheduled_games:
            if time.time() >= self.scheduled_games[0][0]:
                if self.game:
                    #theres already a game started
                    if not self.game.is_in_progress:
                        #current game is not in progress yet
                        self.send_message(message.game.scheduled_game_overlap, map=self.scheduled_games[0][2])
                    else:
                        #current game is in progress
                        self.game_start(self.scheduled_games[0][1], self.scheduled_games[0][2], self.scheduled_games[0][3], self.scheduled_games[0][4])
                elif self.scheduled_games[0][2] is None:
                    self.send_message(message.game.scheduled_game, mode="highlander" if self.scheduled_games[0][4] else "%dv%d" % (self.scheduled_games[0][3] / 2, self.scheduled_games[0][3] / 2))
                else:
                    self.game_start(self.scheduled_games[0][1], self.scheduled_games[0][2], self.scheduled_games[0][3], self.scheduled_games[0][4])
                del self.scheduled_games[0]
            break
    ### Miscellaneous ###
    def is_admin(self, nick):
        if nick.lower() in config.irc.admins: return True
        if nick.lower() in self.channel_admins:
            return True
        return False

    def process_forever(self):
        self._connect()
        while 1:
            self.ircobj.process_once(0.1)
            if self.game: self.game.process_timeout()
            self.process_scheduled_games()
            self.httpd.handle_request()

def main():
    if len(sys.argv) is 5:
        bot = TF2PickupBot(sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]))
    elif len(sys.argv) is not 1:
        print "Usage:\n\tpyTF2Pickup.py [<#channel> <nickname> <server> <port>]"
        sys.exit(1)
    else:
        bot = TF2PickupBot(config.irc.channel, config.irc.nickname[0], \
                                    config.irc.server, config.irc.port)
    try:
        bot.process_forever()
    except KeyboardInterrupt:
        print "^C - Exiting gracefully..."
        bot.disconnect("Terminated at terminal.")
        sys.exit(0)
    except Exception as exc:
        bot.disconnect("I think something bad happened...")
        print "traceback:"
        print traceback.print_exc()
        sys.exit(0)

if __name__ == "__main__":
    main()
