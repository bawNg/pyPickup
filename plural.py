#!/usr/bin/env python

import re

en_rules = """\
^(sheep|deer|fish|moose|aircraft|series|haiku)$  ($)              \1
[ml]ouse$                                         ouse$           ice
child$                                            $               ren
booth$                                            $               s
foot$                                             oot$            eet
ooth$                                             ooth$           eeth
l[eo]af$                                          af$             aves
sis$                                              sis$            ses
^(hu|ro)man$                                      $               s
man$                                              man$            men
^lowlife$                                         $               s
ife$                                              ife$            ives
eau$                                              $               x
^[dp]elf$                                         $               s
lf$                                               lf$             lves
[sxz]$                                            $               es
[^aeioudgkprt]h$                                  $               es
(qu|[^aeiou])y$                                   y$              ies
$                                                 $               s"""

def rules(language):
    lines = en_rules.splitlines()
    if language != "en": lines = file('plural-rules.%s' % language)
    for line in lines:
        print line
        pattern, search, replace = line.split()
        yield lambda word: re.search(pattern, word) and re.sub(search, replace, word)

def plural(noun, language='en'):
    """returns the plural form of a noun"""
    for applyRule in rules(language):
        result = applyRule(noun)
        if result: return result

def pluralize(n, word):
    return "%s %s" % (n, plural(word) if n > 1 else word)
    
def pluralized(n, word):
    return plural(word) if n > 1 else word