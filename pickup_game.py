#!/usr/bin/env python

import random, time
from events import Events
from timers import Timers
import template as message
from model import config

class PickupTeam:
    unknown = -1
    A       = 0
    B       = 1
    _name = {A: 'A', B: 'B'}

class PickupClass:
    unknown     = -1
    sniper      = 0
    scount      = 1
    demoman     = 2
    soldier     = 3
    pyro        = 4
    spy         = 5
    medic       = 6
    heavy       = 7
    engineer    = 8
    _name = {sniper: 'Sniper', scount: 'Scout', demoman: 'Demoman', soldier: 'Soldier', \
             pyro: 'Pyro', spy: 'Spy', medic: 'Medic', heavy: 'Heavy', engineer: 'Engineer'}

class PickupPlayer(object):
    def __init__(self, name, team_or_class=None):
        self.name = name
        self.team = self.game_class = team_or_class
    def get_team_name(self): return PickupTeam._name[self.team]
    team_name = property(get_team_name)
    def get_class_name(self): return PickupClass._name[self.game_class]
    class_name = property(get_class_name)

class PickupServer(object):
    class Type:
        UNKNOWN = -1
        IS      = 0
        SAIX    = 1
    def __init__(self, number, type, address, name):
        self.name       = name
        self.type       = type
        self.address    = address
        self.id         = number

class PickupGame_Events(Events):
    __events__ = ['on_game_start', 'on_game_end', 'on_game_full', 'on_game_in_progress', \
                  'on_player_added', 'on_player_removed', 'on_display_teams']
class PickupGame(object):
    def __init__(self, who, map_name, max_players, is_highlander=False):
        self.events = PickupGame_Events()
        self.timers = Timers()
        self.players     = []
        self.max_players = max_players
        self.owner       = who
        self.map         = map_name
        self.server      = None
        self.password    = "games" #self._generate_password()
        self.is_highlander = is_highlander
        self.is_in_progress = False
        self.has_configured_server = False
        self.last_show_teams = time.time() - 10
        self.events.on_game_start(self)

    def process_timeout(self):
        """Process timeouts, call this method atleast once every 0.5 seconds."""
        self.timers.process_timeout()

    def _generate_password(self):
        return config.password_base + str(random.randrange(10, 99))

    def in_progress(self):
        self.is_in_progress = True
        self.events.on_game_in_progress(self)

    def team_is_full(self, team):
        i = 0
        for player in self.players:
            if player.team == team: i += 1
        return i >= self.max_players / 2
    def contains_player(self, name):
        for player in self.players:
            if player.name.lower() == name.lower(): return True
        return False

    def get_player_count(self): return len(self.players)
    player_count = property(get_player_count)
    def get_team_count(self, team):
        team_count = 0
        for player in self.players:
            if player.team == team: team_count += 1
        return team_count

    def get_class_count(self, game_class):
        class_count = 0
        for player in self.players:
            if player.game_class == game_class: class_count += 1
        return class_count

    def get_available_classes(self):
        available_classes = []
        for game_class in PickupClass._name.keys():
            if self.get_class_count(game_class) < 2: available_classes.append(game_class)
        return available_classes

    def get_team(self, team_name):
        if team_name.lower() == "random":
            random_team = random.randrange(PickupTeam.A, PickupTeam.B)
            return random_team if not self.team_is_full(random_team) else not random_team
        for key, value in PickupTeam._name.items():
            if value.lower().startswith(team_name.lower()): return key
        return None
    def get_class(self, class_name):
        if class_name.lower() == "random":
            return random.randrange(PickupClass.sniper, PickupClass.engineer)
        for key, value in PickupClass._name.items():
            if value.lower().startswith(class_name.lower()): return key
        return None
    def get_player(self, name):
        for player in self.players:
            if player.name == name: return player

    def get_class_groups(self):
        classes = {}
        for class_name in PickupClass._name.values():
            classes[self.get_class(class_name)] = ['?', '?']

        for player in self.players:
            for i in xrange(2):
                if classes[player.game_class][i] == '?':
                    classes[player.game_class][i] = player.name
                    break
        return classes
    def get_team_groups(self):
        teams = {}
        for team_name in PickupTeam._name.values():
            teams[self.get_team(team_name)] = ['?' for i in xrange(self.max_players / 2)]

        for player in self.players:
            for i in xrange(self.max_players / 2):
                if teams[player.team][i] == '?':
                    teams[player.team][i] = player.name
                    break
        return teams
    
    def get_teams(self):
        teams = {}
        for p in g.players:
            if not p.team_name in teams: teams[p.team_name] = []
            teams[p.team_name].append(p.name)
        return teams

    teams = property(get_teams)
    def get_players_message(self):
        return self.get_teams_message(self.owner, self.max_players, (self.get_class_groups() if \
                                      self.is_highlander else self.get_team_groups()), self.is_highlander)
    
    @classmethod
    def get_teams_message(self, owner, max_players, team_groups, is_highlander):        
        if not is_highlander:
            msg = message.game.teams.replace("$c", str(max_players))
            msg = msg.replace("$max_players", str(max_players))
            for team in PickupTeam._name.keys():
                player_nicks = team_groups[team]
                team_msg = ""
                for i in xrange(max_players / 2):
                    if player_nicks[i] == owner:
                        player_nicks[i] = message.game.admin_prefix + player_nicks[i] + message.game.admin_suffix
                    team_msg += player_nicks[i] + (message.game.teams_seperator if i < (max_players / 2) - 1 else "")
                msg = msg.replace("$%s" % PickupTeam._name[team].lower(), team_msg)
            return msg
        else:
            msg = message.game.highlander_teams.replace("$c", str(max_players))
            for game_class in PickupClass._name.keys():
                player_nicks = team_groups[game_class]
                for i in xrange(2):
                    if player_nicks[i] == owner:
                        player_nicks[i] = message.game.admin_prefix + player_nicks[i] + message.game.admin_suffix
                    msg = msg.replace("$?", player_nicks[i], 1)
            return msg

    def get_mode(self):
        if self.is_highlander: return "highlander"
        return "%dv%d" % (self.max_players / 2, self.max_players / 2)
    mode = property(get_mode)
    def add_player(self, name, team_or_class):
        player = PickupPlayer(name, team_or_class)
        self.players.append(player)
        self.events.on_player_added(self, player)
        if self.player_count == self.max_players:
            #game is full
            self.timers.add_timer(config.time_flood_protect + 0.5, self.game_full)
            self.timers.add_timer(config.time_before_close + config.time_flood_protect, self.in_progress)

    def remove_player(self, name):
        self.timers.remove_all() # remove any game in-progress timer
        player = self.get_player(name)
        self.players.remove(player)
        self.events.on_player_removed(self, player)

    def delay_display_teams(self):
        existing_timer = self.timers.get_timer(self.display_teams)
        if existing_timer is not None:
            existing_timer.time_left = config.time_flood_protect
            return
        self.timers.add_timer(config.time_flood_protect, self.display_teams)
    def display_teams(self):
        self.events.on_display_teams(self)
    def game_full(self):
        self.events.on_game_full(self)