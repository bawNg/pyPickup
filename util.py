#!/usr/bin/env python

def prntime(s):
    m,s=divmod(s,60)
    h,m=divmod(m,60)
    d,h=divmod(h,24)
    return d,h,m,s