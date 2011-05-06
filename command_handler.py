#!/usr/bin/env python

import re, datetime
from json import dumps
from parsedatetime import parsedatetime
from irclib import nm_to_n, nm_to_h, irc_lower, ip_numstr_to_quad, ip_quad_to_numstr
from server_query import *
from pickup_game import *
from model import User, Game, News_Article, config
from util import prntime
import template as message

class CommandType:
    public  = 0
    ingame  = 1
    admin   = 2
class Command:
    help        = CommandType.public
    serverinfo  = CommandType.public
    serverlist  = CommandType.public
    maplist     = CommandType.public
    lastteams   = CommandType.public
    lastgame    = CommandType.public
    nextgame    = CommandType.public
    stats       = CommandType.public
    news        = CommandType.public
    uptime      = CommandType.public
    add         = CommandType.ingame
    remove      = CommandType.ingame
    changeteam  = CommandType.ingame
    changeclass = CommandType.ingame
    teams       = CommandType.ingame
    classes     = CommandType.ingame
    game        = CommandType.ingame
    start       = CommandType.admin
    end         = CommandType.admin
    setserver   = CommandType.admin
    setmap      = CommandType.admin
    setadmin    = CommandType.admin
    schedulegame= CommandType.admin
    addnews     = CommandType.admin
    delnews     = CommandType.admin
    todo        = CommandType.admin
    authme      = CommandType.admin
    say         = CommandType.admin
    send        = CommandType.admin
    die         = CommandType.admin
    set         = CommandType.admin
    config      = CommandType.admin
    admins      = CommandType.public
    cmdlist     = CommandType.public
    _aliases    = {'startgame': 'start', 'sg': 'start', 'cg': 'end', 'join': 'add', 'rem': 'remove', \
                   'rm': 'remove', 'moveme': 'changeteam', 'servers': 'serverlist', 'maps': 'maplist', \
                   'admin': 'setadmin', 'server': 'setserver'}

class Command_Message:
    def __init__(self, e, msg):
        self.event_type     = e.eventtype()         # event type is pubmsg, privmsg,etc
        self.source         = e.source()            # source user's nick mask
        self.target         = e.target()            # target user/channel to reply to
        self.nick           = nm_to_n(e.source())   # source user's nickname
        self.raw_message    = msg                   # raw message sent by user
        self.command        = msg.split()[0].lower()# command string is the first word
        self.payload        = None                  # payload is the first argument
        self.args           = None                  # all arguments given after command
        self.arguments      = None
        if len(msg.split()) >= 2:
            self.payload    = msg.split()[1]
            self.args       = msg.split()[1:]
            self.arguments  = msg[len(self.command)+1:]

class Command_Handler:
    def __init__(self, bot):
        self.bot        = bot
        self.c          = bot.connection
        self.send_msg   = bot.send_message
        self.send_notice= bot.send_notice
        self.is_admin   = bot.is_admin

    def process_command(self, e, msg):
        if msg.strip() == "": return 0
        e_msg = Command_Message(e, msg)

        #check for aliases
        if e_msg.command == "_aliases": return 0
        if e_msg.command in Command._aliases.keys():
            e_msg.command = Command._aliases[e_msg.command]

        print "[Command_Handler] Recieved command [%s] from [%s] type [%s]." % \
                    (msg, e_msg.nick,  e.eventtype().upper())

        #check if command exists
        if not hasattr(Command, e_msg.command):
            self.send_notice(e_msg.nick, message.general.unknown_command, command=e_msg.command)
            return 0

        #check if command is for admins
        if (getattr(Command, e_msg.command) == CommandType.admin) and \
                                            not self.bot.is_admin(e_msg.nick):
            self.send_notice(e_msg.nick, message.general.not_admin, nick=e_msg.nick)
            return 0

        #check if command is for ingame
        if (getattr(Command, e_msg.command) == CommandType.ingame):
            if (self.bot.game is None):
                self.send_notice(e_msg.nick, message.game.not_started_user)
                return 0

        #dispatch command to command handler
        if hasattr(self, "cmd_%s" % e_msg.command):
            do_cmd = getattr(self, "cmd_%s" % e_msg.command)
            do_cmd(self.c, e_msg)
        else:
            print "[Error] Handler missing for command [%s]." % e_msg.command

    ### Public commands ###
    def cmd_uptime(self, c, e):
        d, h, m, s = prntime(time.time() - self.bot.startup_time)
        self.send_msg(message.general.uptime, days=d, hours=h, minutes=m, seconds=s)
    
    def cmd_help(self, c, e):
        self.send_notice(e.nick, message.general.help)

    def cmd_stats(self, c, e):
        nickname = e.payload  or e.nick
        user = User.find_one({'nickname': nickname})
        if not user or not user.games_played or user.games_played == 0:
            self.send_msg(message.general.no_games_played, nick=nickname)
            return
        self.send_msg(self.bot.channel, message.general.games_played, nick=user.nickname, count=user.games_played)
    
    def cmd_news(self, c, e):
        count = 3
        if e.payload:
            if not e.payload.isdigit():
                self.send_notice(e.nick, message.command_syntax.news)
                return
            count = int(e.payload)
        
        articles = News_Article.find().sort('created_at', -1)
        self.send_notice(e.nick, message.news.header, channel=self.bot.channel)
        
        article_count = articles.count()
        for i in xrange(count):
            if i > article_count - 1: break
            article = articles[i]
            self.send_notice(e.nick, message.news.line, author=article.author, body=article.body, \
                             date=datetime.datetime.strftime(article.created_at, "%d/%m/%Y"))
    
    def cmd_addnews(self, c, e):
        if not e.payload:
            self.send_notice(e.nick, message.command_syntax.addnews)
            return
        
        article = News_Article(created_at=datetime.datetime.now(), author=e.nick, body=e.arguments)
        article.save()
        self.send_notice(e.nick, message.news.added)
    
    def cmd_delnews(self, c, e):
        if not e.payload:
            self.send_notice(e.nick, message.command_syntax.delnews)
            return
        
        articles = News_Article.find({'body': re.compile(".*" + e.arguments + ".*")})
        if articles.count() > 1:
            self.send_notice(e.nick, message.news.multiple_matches)
            return
        
        self.send_notice(e.nick, message.news.removed, body=articles[0].body)
        articles[0].remove()
        
        
    
    def cmd_serverlist(self, c, e):
        serverlist = ""
        for i in xrange(len(config.servers)):
            server_address = config.servers[i]
            server = SourceServer(server_address[0], server_address[1])
            if not server.connected:
                self.send_msg(e.nick, message.server.cannot_connect, owner=e.nick)
                return
            server_details = server.get_details()
            serverlist += "[%d] %s, " % (i, server_details.name)

        self.send_notice(e.nick, message.server.list, server_list=serverlist[:len(serverlist) - 2])

    def cmd_maplist(self, c, e):
        map_list = ", ".join(config.maps)
        self.send_notice(e.nick, message.general.map_list, map_list=map_list)

    def cmd_game(self, c, e):
        self.send_msg(message.game.game, admin=self.bot.game.owner, \
                      map=self.bot.game.map, server=self.bot.game.server.name)
    
    def cmd_add(self, c, e):
        game = self.bot.game
        if game.is_highlander and not e.payload:
            self.send_notice(e.nick, message.command_syntax.join)
            return
        elif game.is_in_progress:
            self.send_notice(e.nick, message.game.is_in_progress)
            return
        elif game.contains_player(e.nick):
            self.send_notice(e.nick, message.player.already_added)
            return
        
        if not game.is_highlander:
            team = game.get_team(e.payload if e.payload else "random")
            if team is None:
                self.send_notice(e.nick, message.game.team_invalid, team=e.payload)
                return
            elif game.get_team_count(team) == game.max_players / 2:
                self.send_notice(e.nick, message.game.team_full, team=PickupTeam._name[team])
                return
        else:
            game_class = game.get_class(e.payload)
            if game_class is None:
                self.send_notice(e.nick, message.game.class_invalid, classname=e.payload)
                return
            elif game.get_class_count(game_class) == 2:
                self.send_notice(e.nick, message.game.class_full, game_class=PickupClass._name[game_class])
                return

        game.add_player(e.nick, game_class if game.is_highlander else team)

    def cmd_remove(self, c, e):
        game = self.bot.game
        if game.is_in_progress:
            self.send_notice(e.nick, message.game.is_in_progress)
            return
        elif not game.contains_player(e.nick):
            self.send_notice(e.nick, message.player.not_taking_part)
            return
        game.remove_player(e.nick)

    def cmd_teams(self, c, e):
        game = self.bot.game
        
        if game.last_show_teams < (time.time() - 3):
            display_timer = self.bot.game.timers.get_timer(self.bot.game.display_teams)
            if display_timer: display_timer.remove()
            self.send_msg(self.bot.game.get_players_message())
            game.last_show_teams = time.time()
        else:
            self.send_notice(e.nick, message.general.command_timeout)

    def cmd_changeteam(self, c, e):
        game = self.bot.game
        if game.is_highlander: return
        if game.is_in_progress:
            self.send_notice(e.nick, message.game.is_in_progress)
            return
        team = int(not game.get_player(e.nick).team)
        if e.payload: team = game.get_team(e.payload)
        if team is None:
            self.send_notice(e.nick, message.game.class_invalid, team=e.payload)
            return
        elif game.get_team_count(team) == 2:
            self.send_notice(e.nick, message.game.team_full, team=PickupTeam._name[team])
            return

        game.get_player(e.nick).team = team

        self.send_notice(e.nick, message.player.changed_team, team=PickupTeam._name[team])
        game.delay_display_teams()
        
    def cmd_classes(self, c, e):
        game = self.bot.game
        if not game.is_highlander: return
        available_game_classes = game.get_available_classes()
        if available_game_classes == []:
            self.send_msg(message.game.available_classes_none)
            return
        available_classes = ""
        for game_class in available_game_classes:
            available_classes += "%s, " % PickupClass._name[game_class]
        self.send_msg(message.game.available_classes, classes=available_classes[:len(available_classes) - 2])

    def cmd_changeclass(self, c, e):
        game = self.bot.game
        if not game.is_highlander: return
        if not e.payload:
            self.send_notice(e.nick, message.command_syntax.changeclass)
            return
        elif game.is_in_progress:
            self.send_notice(e.nick, message.game.is_in_progress)
            return
        game_class = game.get_class(e.payload)
        if game_class is None:
            self.send_notice(e.nick, message.game.class_invalid, classname=e.payload)
            return
        elif game.get_class_count(game_class) == 2:
            self.send_notice(e.nick, message.game.class_full, game_class=PickupClass._name[game_class])
            return
        elif game.get_player(e.nick).game_class == game_class:
            self.send_notice(e.nick, "You already belong to that class.") #TODO: move to template
            return

        game.get_player(e.nick).game_class = game_class

        self.send_notice(e.nick, message.player.changed_class, player_class=PickupClass._name[game_class])
        game.delay_display_teams()


    def cmd_schedulegame(self, c, e):
        #strftime("%a, %d %b %Y %H:%M:%S +0000", gmtime())
        if e.payload is None:
            self.send_notice(e.nick, message.command_syntax.schedulegame)
            return

        match = re.search(r"([^()]+)(\d{1,2}(?:v)\d{1,2}|highlander)(?:\s*\(([^()]+)\))?", e.arguments)
        if not match:
            self.send_notice(e.nick, message.command_syntax.schedulegame)
            return
        
        input_time = match.group(1).strip()
        input_mode = match.group(2)
        input_map = match.group(3)
        if input_mode != "highlander":
            x, y = int(input_mode.split("v")[0]), int(input_mode.split("v")[1])
            # Check if the teams are ballanced and are not too large
            if x != y or (x + y) > config.max_players:
                self.send_notice(e.nick, message.command_syntax.schedulegame)
                return
            
        if input_map:
            input_map = input_map.lower()
            if input_map not in config.maps:
                self.send_notice(e.nick, message.game.map_doesnt_exist, map=input_map)
                return

        p = parsedatetime.Calendar()
        parsed_time = p.parse(input_time)

        if parsed_time[1] == 0:
            self.send_notice(e.nick, message.general.unable_to_parse, value=e.arguments)
            return

        current_sheduled_game = None
        if self.bot.scheduled_games: current_sheduled_game = self.bot.scheduled_games[0]

        timestamp = time.mktime(parsed_time[0])
        self.bot.scheduled_games.append((timestamp, e.nick, input_map, (x + y) if input_mode != "highlander" else 12, True if input_mode == "highlander" else False))
        self.bot.scheduled_games.sort()
        print "scheduled_games: %s" % self.bot.scheduled_games

        str_time = time.strftime("%a, %d %b %Y %I:%M %p", parsed_time[0])
        self.send_notice(e.nick, message.game.scheduled, time=str_time)

        if current_sheduled_game != self.bot.scheduled_games[0]:
            self.bot.topic_update_scheduled_game()


    def cmd_start(self, c, e):
        if ((len(e.args) < 2) if e.args else True):
            self.send_notice(e.nick, message.command_syntax.start)
            return
        elif self.bot.game:
            self.send_notice(e.nick, message.game.already_started)
            return
        elif e.args[1].lower() not in config.maps:
            self.send_notice(e.nick, message.game.map_doesnt_exist, map=e.args[1].lower())
            return
        
        match = re.search(r"(\d{1,2})(?:v(?:s)?)?(\d{1,2})?|(highlander)", e.payload.lower())
        if match.group(1):
            x, y = int(match.group(1)), int(match.group(2)) if match.group(2) else 0
            # Check if the teams are ballanced and are not too large
            if match.group(2):
               if x != y: match = None
            if (x + y) > config.max_players: match = None
            
        if not match:
            self.send_notice(e.nick, message.command_syntax.start)
            return
        
        max_players = 12
        if match.group(1): max_players = x + y
        
        self.bot.game_start(e.nick, e.args[1].lower(), max_players, True if match.group(3) else False)

    def cmd_end(self, c, e):
        if not self.bot.game:
            self.send_notice(e.nick, message.game.not_started)
            return
        self.bot.game_end()
        self.send_msg(message.game.cancelled)

    def cmd_setserver(self, c, e):
        if not e.payload:
            self.send_notice(e.nick, message.command_syntax.setserver)
            return
        elif not self.bot.game:
            self.send_notice(e.nick, message.game.not_started)
            return
        elif self.bot.game.is_in_progress:
            self.send_notice(e.nick, message.game.is_in_progress)
            return
        elif not e.payload.isdigit():
            self.send_notice(e.nick, message.server.invalid_number)
            return
        elif int(e.payload) > (len(config.servers) - 1):
            self.send_notice(e.nick, message.server.invalid_number)
            return

        server_address = config.servers[int(e.payload)]
        if self.bot.game.server:
            if self.bot.game.server.address == server_address:
                self.send_notice(e.nick, message.server.already_set)
                return

        server = SourceServer(server_address[0], server_address[1])
        if not server.connected:
            self.send_msg(message.server.cannot_connect, owner=e.nick)
            return
        
        server_details = server.get_details()

        server_type = PickupServer.Type.UNKNOWN
        if "SGS TF2 PICKUP" in server_details.name: server_type = PickupServer.Type.SAIX
        if "-IS- TF2 PICKUP" in server_details.name: server_type = PickupServer.Type.IS

        self.bot.game.server = PickupServer(int(e.payload), server_type, server_address, server_details.name)
        self.send_notice(e.nick, message.server.set, server=server_details.name)
        self.bot.set_topic_game_started()

        #if server has already been configured, reconfigure
        if self.bot.game.has_configured_server: self.bot.game_configure_server()

    def cmd_setmap(self, c, e):
        if not e.payload:
            self.send_notice(e.nick, message.command_syntax.setmap)
            return
        elif not self.bot.game:
            self.send_notice(e.nick, message.game.not_started)
            return
        elif self.bot.game.is_in_progress:
            self.send_notice(e.nick, message.game.is_in_progress)
            return
        elif e.payload.lower() not in config.maps:
            self.send_notice(e.nick, message.game.map_doesnt_exist, map=e.payload.lower())
            return

        self.bot.game.map = e.payload.lower()
        self.send_notice(e.nick, message.game.map_set, map=self.bot.game.map)
        self.bot.set_topic_game_started()

        #if server has already been configured, reconfigure
        if self.bot.game.has_configured_server: self.bot.game_configure_server()

    def cmd_setadmin(self, c, e):
        if not e.payload:
            self.send_notice(e.nick, message.command_syntax.setadmin)
            return
        elif not self.bot.game:
            self.send_notice(e.nick, message.game.not_started)
            return
        elif self.bot.game.is_in_progress:
            self.send_notice(e.nick, message.game.is_in_progress)
            return
        
        self.bot.game.owner = e.payload
        self.send_notice(e.nick, "Set game admin to [%s]." % e.payload)
        self.bot.set_topic_game_started()
        
    def cmd_lastteams(self, c, e):
        games = Game.find().sort('created_at', -1)
        if not games:
            self.send_notice(e.nick, "No previous game found.")
            return
        game = games[0]
        
        max_players, is_hl = 12, (game.mode == "highlander")
        if not is_hl: max_players = int(game.mode.split("v")[0]) * 2
        teams_groups = dict(map(lambda k: (int(k), getattr(game.teams, k)), iter(game.teams)))
        teams_message = PickupGame.get_teams_message(game.owner, max_players, teams_groups, is_hl)
        
        self.send_msg(message.general.last_teams)
        self.send_msg(teams_message)
        
    
    def cmd_lastgame(self, c, e):
        games = Game.find().sort('created_at', -1)
        if not games:
            self.send_msg(message.general.no_games_played)
            return
        
        g = games[0]
        
        self.send_msg(message.general.last_game, admin=g.admin, map=g.map, server=g.server, \
                      time=datetime.datetime.strftime(g.created_at, "%I:%M:%S %p, %A %d %B")) #22:57:00, Friday 4 December
    
    def cmd_nextgame(self, c, e):
        next_time, next_map = self.bot.get_next_game_info()
        if not next_time:
            self.send_msg(message.general.next_game_none)
            return
        
        self.send_msg(message.topic.next_game, next_time=next_time, next_map=next_map)

    def cmd_admins(self, c, e):
        self.send_notice(e.nick, "Admins: %s" % ", ".join(self.bot.channel_admins))
    def cmd_serverinfo(self, c, e): 
        if not e.payload: e.payload = 0
        server_number = int(e.payload)
        
        if server_number >= len(config.servers):
            self.send_notice(e.nick, "Invalid server number.")
            return

        server = SourceServer(config.servers[server_number][0], config.servers[server_number][1])
        if not server.connected:
            self.send_msg(message.server.cannot_connect, owner=e.nick)
            return
        details = server.get_details()
        self.send_msg("Server: %s" % details.name)
        self.send_msg("IP: %s:%s" % (config.servers[server_number][0], config.servers[server_number][1]))
        self.send_msg("Map / Player Count: %s (%s)" % (details.map, details.player_count))
        players = server.players
        if len(players) == 0:
            self.send_msg("There are currently no players on the server.")
        else:
            players_output = ""
            for index, player in players.items():
                players_output += "%s (%s), " % (player.name, player.kills)
            self.send_msg("Players: %s" % players_output[:len(players_output) - 2])

    def cmd_imdraken(self, c, e):
        if e.nick.lower() == "draken":
            c.kick(e.target, e.nick, "You are Draken.")
        else:
            self.send_notice(e.nick, "No you're not.")
    def cmd_cmdlist(self, c, e):
        cmds = filter(lambda c: False if c.startswith("_") else True, dir(Command))
        self.send_notice(e.nick, "Listing all commands: %s" % ", ".join(cmds))
        pass
    ### Admin commands ###
    def cmd_authme(self, c, e):
        self.bot.send_dcc_auth(e.nick)
    
    def cmd_todo(self, c, e):
        if not e.payload:
            self.send_notice(e.nick, "Not yet implemented.")
            return
    
    def cmd_say(self, c, e):
        self.send_msg(e.payload, e.raw_message[len(e.command)+len(e.payload)+2:])

    def cmd_send(self, c, e):
        c.send_raw(e.raw_message[len(e.command)+1:])

    def cmd_die(self, c, e):
        self.bot.die("Killed by admin. (%s)" % e.nick)
    def cmd_set(self, c, e):
        if e.payload == "user":
            user = User.find_or_create_by_nick(e.args[1])
            attr, value = e.args[2].split("=", 1)
            setattr(user, attr, int(value) if value.isdigit() else value)
            user.save()
            self.send_msg("Set attribute [%s] for user [%s] to value [%s]." % (attr, user.nickname, value))
            
    def cmd_config(self, c, e):
        if not e.payload:
            [i for attr in config]
            for attr in dir(default_config.defaults):
                if attr.startswith("__"): continue
            return
        
        attr_name = e.payload.lower()
        attr = getattr(config, attr_name)
        if not attr:
            self.send_notice(e.nick, "Unable to find config attribute named [%s]." % attr_name)
            return
        
        if len(e.args) < 2:
            self.send_notice(e.nick, "Attribute [%s] has value: %s" % (attr_name, dumps(attr)))
            return
        
        args = e.arguments[len(e.payload) + 1:]
        
        if type(attr) == int:
            if not args.isdigit():
                self.send_notice(e.nick, "Invalid value. Attribute [%s] is an integer.")
                return
            setattr(config, attr_name, int(args))
            self.send_notice(e.nick, "Set attribute [%s] to value [%d]." % (attr_name, int(args)))
            
        elif type(attr) == str or type(attr) == unicode:
            setattr(config, attr_name, args)
            self.send_notice(e.nick, "Set attribute [%s] to value [%s]." % (attr_name, args))
            
        elif type(attr) == list:
            def send_unknown_attribute_command_notice():
                self.send_notice(e.nick, "Unknown list attribute command.")
                self.send_notice(e.nick, "Usage: \"!config <attribute name> <add/remove> <value>\"")
            def send_invalid_ip_port_attribute_notice():
                self.send_notice(e.nick, "Invalid ip/port attribute value.")
                self.send_notice(e.nick, "Usage: \"!config <attribute name> <add/remove> <ip_address:port>\"")
            def send_invalid_tuple_attribute_notice(value_count):
                self.send_notice(e.nick, "Invalid list attribute value.")
                self.send_notice(e.nick, "Usage: \"!config <attribute name> <add/remove> %s\"" % ", ".join([("<value %s>" % i) for i in xrange(1, value_count + 1)]))
            
            def is_ip_port_pair(attr):
                if (len(attr[0]) == 2):
                    if ((type(attr[0][0]) == str) or (type(attr[0][0]) == unicode)) and (type(attr[0][1]) == int):
                        return True
                return False
            
            if (len(e.args) < 2):
                send_unknown_attribute_command_notice()
                return
            
            args = e.arguments[len(e.payload) + len(e.args[1]) + 2:]
            if e.args[1] == "add" or e.args[1] == "remove":
                if args == "":
                    self.send_notice(e.nick, "Error: No value.")
                    return
                
                if type(attr[0]) == str or type(attr[0]) == unicode:
                    if e.args[1] == "add":
                        attr.append(args)
                        setattr(config, attr_name, attr)
                        self.send_notice(e.nick, "Added value [%s] to attribute list [%s]." % (args, attr_name))
                    else:
                        if not args in attr:
                            self.send_notice(e.nick, "Attribute list [%s] does not contain value [%s]." % (attr_name, args))
                            return
                        
                        attr.remove(args)
                        setattr(config, attr_name, attr)
                        self.send_notice(e.nick, "Removed value [%s] from attribute list [%s]." % (args, attr_name))
                
                elif type(attr[0]) == list:
                    if is_ip_port_pair(attr):
                        if args.find(":") == -1:
                            send_invalid_ip_port_attribute_notice()
                            return
                        server_ip, server_port = map(str.strip, args.split(":"))
                        print "server_ip/port:", server_ip, server_port
                        if not re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", server_ip) or not server_port.isdigit():
                            send_invalid_ip_port_attribute_notice()
                            return
                        
                        address = (server_ip, int(server_port))
                        
                        if e.args[1] == "add":
                            attr.append(address)
                            setattr(config, attr_name, attr)
                            self.send_notice(e.nick, "Added address [%s] to attribute list [%s]." % (args, attr_name))
                        else:
                            if not address in attr:
                                self.send_notice(e.nick, "Attribute list [%s] does not contain address [%s]." % (attr_name, args))
                                return
                        
                            attr.remove(address)
                            setattr(config, attr_name, attr)
                            self.send_notice(e.nick, "Removed address [%s] from attribute list [%s]." % (args, attr_name))
                    else:
                        args = map(str.strip, args.split(","))
                        if len(attr[0]) != len(args):
                            send_invalid_tuple_attribute_notice(len(attr[0]))
                            return
                        for i in xrange(attr[0]):
                            if type(attr[0][i]) == int and not arg[i].isdigit():
                                self.send_notice(e.nick, "Value %d should be a number. You gave [%s]." % (i + 1, arg[i]))
                                return
                        
                        if e.args[1] == "add":
                            attr.append(args)
                            setattr(config, attr_name, attr)
                            self.send_notice(e.nick, "Added %s to attribute list [%s]." % (args, attr_name))
                        else:
                            if not args in attr:
                                self.send_notice(e.nick, "Attribute list [%s] does not contain tuple %s." % (attr_name, args))
                                return
                        
                            attr.remove(address)
                            setattr(config, attr_name, attr)
                            self.send_notice(e.nick, "Removed tuple %s from attribute list [%s]." % (args, attr_name))
                else:
                    self.send_notice(e.nick, "Unknown attribute type [%s]." % type(attr[0]))
                    return

            else:
                send_unknown_attribute_command_notice()
                return
        
        else:
            self.send_notice(e.nick, "Unknown attribute type [%s]." % type(attr))
            return
        
        config.save()
        
        