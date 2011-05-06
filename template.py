#!/usr/bin/env python

### Template formatting ###
#
# $var_name -- variables
# #B        -- toggle bold
# #U        -- toggle underline
# #O        -- origional
# #R        -- reversed
# #C03,43   -- set colour codes

class topic:
    base = "#C14-= #BTeam Fortress 2 Pickup#B =- ( type !help for a list of commands and !news for news )"
    seperator = " #C14-#O "
    default = "No games are currently running"
    game_started = "#C2[game.started] #C5#B$owner#B #C7will be admining a #C05#B$mode#B #C7game on the map #C05#B$map#B #C7on #C5#B$server#O"
    game_in_progress = "#C2[game.in.progress] #C7a #C05#B$mode#B #C7on #C5#B$server#B #C7(#C5$map#C7)#O"
    next_game = "#C7Next game: #C05$next_time #C7(#C14$next_map#C7)"

class channel:
    join = ["Welcome to #B#TF2Mix#B! Type !help for available commands. Enjoy your stay.", "Please note: This bot is still under development and is not yet complete."]

class command_syntax:
    start = 'Invalid syntax! Usage: "!start <mode> <map name>"'
    setserver = 'Invalid syntax! Usage: "!setserver <server number>"'
    setmap = 'Invalid syntax! Usage: "!setmap <map name>"'
    setadmin = 'Invalid syntax! Usage: "!setmap <map name>"'
    join = 'Invalid syntax! Usage: "!join [<team/class>]"'
    changeclass = 'Invalid syntax! Usage: "!changeclass <class name>"'
    schedulegame = 'Invalid syntax! Usage: "!schedulegame <time/date> <mode> [(map)]"'
    news = 'Invalid syntax! Usage: "!news [<number of articles>]"'
    addnews = 'Invalid syntax! Usage: "!addnews <article body>"'
    delnews = 'Invalid syntax! Usage: "!delnews <unique partial article body>"'
    debug = "Please note: This is a debug command. Do #Unot#U use this command unless you know exactly how!"

class server:
    set = "Successfully set server to [$server]."
    already_set = "Server is already set to that."
    invalid_number = "Invalid server number!"
    list = "Server list: $server_list"
    unknown = '$owner: I cannot find a method to configure the set server. Please either change the server with "!setserver <server number>" or manually configure the map and password.'
    none_available = '$owner: I cannot find an available server to designate. Please use "!setserver <server number>" to manually set the server.'
    cannot_connect = '$owner: I am unable to connect to the server.'
    change_or_configure = 'Please either change the server with "!setserver <server number>" or manually configure the map and password.'

class player:
    already_added = "You are already taking part in the game."
    not_taking_part = "You are not taking part in the game."
    added = "You have been added to the pickup on Team $team."
    added_highlander = "You have been added to the pickup as a [$player_class]."
    removed = "You have been removed from the game."
    changed_team = "You have changed to Team $team."
    changed_class = "You have changed class to [$player_class]."

class game:
    started = "A TF2 pickup game has been started, type !add [<team/class>] to join! The map is $map."
    not_started = "Sorry, there is currently no game started."
    not_started_user = not_started + " Ask an admin to start a game."
    cancelled = "A TF2 pickup game has been cancelled."
    full = "The game is full! Game will close in $secs seconds."
    in_progress = "Your game is starting in 60 seconds! #C07Server: #C05#B$server#B #C07Password: #C05#B$password#B#O. Enjoy!"
    sent_password = "Server details and password have been sent to all players taking part in the game."
    is_in_progress = "You cannot use that command while the current game is in progress."
    already_started = "There is already a game started."
    available_classes = "Available classes: $classes"
    available_classes_none = "There are no available classes at this time."
    team_invalid = "Invalid team! There is no team name matching [$team]."
    team_full = "Sorry, game team [$team] is already full."
    class_full = "Sorry, game class [$game_class] is already full."
    class_invalid = "Invalid class! There is no class name matching [$classname]."
    map_set = "Map successfully set to [$map]."
    map_doesnt_exist = 'There is no map matching [$map]. For available maps check "!maplist"'
    scheduled = "A game has been scheduled for [$time]."
    scheduled_game = "#C4A $mode TF2 pickup game is scheduled to begin now."
    scheduled_game_overlap = "#C4A TF2 pickup game on map [$map] was scheduled to begin now, but there is already a game started."
    game = "#C14The current game will be admined by [$admin] on map [$map] on server [$server]."
    teams = "[#C14$c/$max_players#O] #C07Team A: #C14$a #O|| #C07Team B: #C14$b"
    teams_seperator = " #O, #C14"
    admin_prefix = "#C02#U"
    admin_suffix = "#U"
    highlander_teams = "[#C14$c/18#O] #C07Sniper: #C14$? #O, #C14$? #O|| #C07Scout: #C14$? #O, #C14$? #O|| #C07Demoman: #C14$? #O, #C14$? #O|| #C07Soldier: #C14$? #O, #C14$? #O|| #C07Pyro: #C14$? #O, #C14$? #O|| #C07Spy: #C14$? #O, #C14$? #O|| #C07Medic: #C14$? #O, #C14$? #O|| #C07Heavy: #C14$? #O, #C14$? #O|| #C07Engineer: #C14$? #O, #C14$?"

class news:
    header = "#B$channel#B news"
    line = "o $date * $body ($author)"
    added = "Added article."
    removed = "Removed article [$body]."
    multiple_matches = "Query matched multiple articles. Try again with a unique string."

class general:
    uptime = "#C14I have been up for #B$days#B days, #B%hours#B hours, #B$minutes#B minutes, #B$seconds#B seconds."
    last_teams = "#C14The teams for the previous pickup were as follows:"
    last_game = "#C14The last game was admined by #B$admin#B on map #B$map#B and server #B$server#B at #B$time#B" #22:57:00, Friday 4 December
    no_last_game = "#C14There are no games recorded in the database."
    games_played = "#C14#B$nick#B has played #B$count#B pickup(s)."
    no_games_played = "#C14#B$nick#B has not played a pickup."
    next_game_none = "There are no games scheduled at the moment."
    unable_to_parse = "Unable to parse value [$value]."
    command_timeout = "Please wait a few seconds before using this command again."
    unknown_command = "'$command' is an unknown command. For the list of commands use: !help"
    help = "Commands: !add <class>, !remove, !changeclass, !teams, !maplist, !classes, !admins"
    map_list = "Available maps: $map_list"
    not_admin = "Only #Badmins#B may use that command."