#!/usr/bin/env python
# -*- coding: utf-8 -*-

# generates topics.html and topic_*.html
# (c) 2013 by the GRASS Development Team, Luca Delucchi

import os
import sys
import glob
import string
from build_html import *

blacklist = ['Display', 'Database', 'General', 'Imagery', 'Misc', 'Postscript',
             'Raster', 'Raster3D', 'Temporal', 'Vector']

path = sys.argv[1]
year = os.getenv("VERSION_DATE")

keywords = {}

htmlfiles = glob.glob1(path, '*.html')

for fname in htmlfiles:
    fil = open(os.path.join(path, fname))
    # TODO maybe move to Python re (regex)
    lines=fil.readlines()
    try:
        index_keys = lines.index('<h2>KEYWORDS</h2>\n') + 1
        index_desc = lines.index('<h2>NAME</h2>\n') + 1
    except:
        continue
    try:
        keys = lines[index_keys].split(',')
    except:
        continue
    for key in keys:
        key = key.strip().title()
        if key not in keywords.keys():
            keywords[key] = []
            keywords[key].append(fname)
        elif fname not in keywords[key]:
            keywords[key].append(fname)

for black in blacklist:
    try:
        del keywords[black]
    except:
        continue

topicsfile = open(os.path.join(path, 'keywords.html'), 'w')
topicsfile.write(header1_tmpl.substitute(title = "GRASS GIS " \
                        "%s Reference Manual: Topics index" % grass_version))
topicsfile.write(headertopics_tmpl)
for key, values in sorted(keywords.iteritems()):
    keyword_line = "<li><b>%s</b>:" % key
    for value in values:
        keyword_line += ' <a href="%s">%s</a>,' % (value, value.replace('.html',
                                                                        ''))
    keyword_line = keyword_line.rstrip(',')
    keyword_line += '</li>\n'
    topicsfile.write(keyword_line)

topicsfile.write("</ul>\n")
write_html_footer(topicsfile, "index.html", year)  
topicsfile.close()
    
