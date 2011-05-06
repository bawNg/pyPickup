#!/usr/bin/env python

import sys
import re
from pymongo.connection import Connection
from mongobongo import Document
import config as default_config

class Config(Document):
    collection = 'config'
    
    @property
    def irc(self): return default_config.irc
    @property
    def items(self): return self.objects.db.items()

class User(Document):
    collection = 'users'
    
    @classmethod
    def find_or_create_by_nick(self, nick):
        user = self.find_one({'nickname': re.compile(nick, re.IGNORECASE)})
        if not user: user = User(nickname = nick)
        return user

class Game(Document):
    collection = 'games'

class News_Article(Document):
    collection = 'news'

class Todo(Document):
    collection = "todo"

print "[Model] Connecting to the database..."
mongo_connection = Connection("localhost", 27017)
mongo_database = mongo_connection.tf2mix

for attr_name in dir():
    if attr_name.startswith("__") or attr_name == "Document": continue
    attr = getattr(sys.modules[__name__], attr_name)
    if type(attr) != type(Document): continue
    attr.objects.db = mongo_database


def sync_database_config():
    print "[sync_database_config] Checking that database config is in sync..."
    is_updated = False
    for attr in dir(default_config.defaults):
        if attr.startswith("__"): continue
        default_value = getattr(default_config.defaults, attr)
        if not getattr(config, attr):
            setattr(config, attr, default_value)
            print "[sync_database_config] Attribute [%s] did not exist in database. Set value to [%s]." % (attr, default_value)
            if not is_updated: is_updated = True
    if is_updated:
        config.save()
        print "[sync_database_config] Updated database config successfully."
    else:
        print "[sync_database_config] Database config is up-to-date."

config = Config.find_one()
if not config: config = Config()
sync_database_config()

#player = Player(author = 'Alex', title = 'Pink Pony\'s Life', tags = ['mongo', 'bongo'])
#article.save()
#articles = Article.objects.all()