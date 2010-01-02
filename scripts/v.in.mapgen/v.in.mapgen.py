#!/usr/bin/env python
#
############################################################################
#
# MODULE:       v.in.mapgen
#
# AUTHOR(S):    Andreas Lange, andreas.lange@rhein-main.de
#               Updated for GRASS 6 by Hamish Bowman
#               Converted to Python by Glynn Clements
#
# PURPOSE:      Import data from Mapgen or Matlab into a GRASS vector map
#
# COPYRIGHT:    Original version (c) Andreas Lange
#               Updates by Hamish Bowman
#               (C) 2008 the GRASS Development Team
#
#               This program is free software under the GNU General Public
#               License (>=v2). Read the file COPYING that comes with GRASS
#               for details.
#############################################################################
#
# REQUIREMENTS:  awk
#
# DATA AVAILABILITY: e.g., NOAA's Online Coastline Extractor
#                    http://www.ngdc.noaa.gov/mgg/shorelines/shorelines.html
#

#%Module
#%  description: Import Mapgen or Matlab vector maps into GRASS.
#%  keywords: vector
#%  keywords: import
#%End
#%flag
#%  key: f
#%  description: Input map is in Matlab format
#%end
#%flag
#%  key: z
#%  description: Create a 3D vector points map from 3 column Matlab data 
#%end
#%option
#% key: input
#% type: string
#% gisprompt: old_file,file,input
#% description: Name of input file in Mapgen/Matlab format
#% required : yes
#%end
#%option
#% key: output
#% type: string
#% gisprompt: new,vector,vector
#% description: Name for output vector map (omit for display to stdout)
#% required : no
#%end

import sys
import os
import atexit
import string
import time
import shutil
from grass.script import core as grass

def cleanup():
    grass.try_remove(tmp)
    grass.try_remove(tmp + '.dig')

def main():
    global tmp

    infile = options['input']
    output = options['output']
    matlab = flags['f']
    threeD = flags['z']

    prog = 'v.in.mapgen'

    opts = ""

    if not os.path.isfile(infile):
	grass.fatal(_("Input file <%s> not found.") % infile)

    if output:
	name = output
    else:
	name = ''

    if threeD:
	matlab = True

    if threeD:
	do3D = 'z'
    else:
	do3D = ''

    tmp = grass.tempfile()

    #### create ascii vector file
    inf = file(infile)
    outf = file(tmp, 'w')

    if matlab:
	## HB:  OLD v.in.mapgen.sh Matlab import command follows.
	##    I have no idea what it's all about, so "new" matlab format will be
	##    a series of x y with "nan nan" breaking lines. (as NOAA provides)
	##  Old command:
	#  tac $infile | $AWK 'BEGIN { FS="," ; R=0 }
	#    $1~/\d*/   { printf("L %d\n", R) }
	#    $1~/   .*/ { printf(" %lf %lf\n", $2, $1) ; ++R }
	#    $1~/END/   { }' | tac > "$TMP"

	## matlab format.
	points = []
	for line in inf:
	    f = line.split()
	    if f[0].lower() == 'nan':
		if points != []:
		    outf.write("L %d\n" % len(points))
		    for point in points:
			outf.write(" %.8f %.8f %.8f\n" % tuple(map(float,point)))
		points = []
	    else:
		if len(f) == 2:
		    f.append('0')
		points.append(f)
	if points != []:
	    outf.write("L %d\n" % len(points))
	    for point in points:
		outf.write(" %.8f %.8f %.8f\n" % tuple(map(float,point)))
    else:
        ## mapgen format.
	points = []
	for line in inf:
	    if line[0] == '#':
		if points != []:
		    outf.write("L %d\n" % len(points))
		    for point in points:
			outf.write(" %.8f %.8f\n" % tuple(map(float,point)))
		points = []
	    else:
		points.append(line.rstrip('\r\n').split('\t'))
	if points != []:
	    outf.write("L %d\n" % len(points))
	    for point in points:
		outf.write(" %.8f %.8f\n" % tuple(map(float,point)))

    outf.close()
    inf.close()

    #### create digit header
    digfile = tmp + '.dig'
    outf = file(digfile, 'w')
    t = string.Template(\
"""ORGANIZATION: GRASSroots organization
DIGIT DATE:   $date
DIGIT NAME:   $user@$host
MAP NAME:     $name
MAP DATE:     $year
MAP SCALE:    1
OTHER INFO:   Imported with $proj
ZONE:         0
MAP THRESH:   0
VERTI:
""")
    date = time.strftime("%m/%d/%y")
    year = time.strftime("%Y")
    user = os.getenv('USERNAME') or os.getenv('LOGNAME')
    host = os.getenv('COMPUTERNAME') or os.uname()[1]
    s = t.substitute(prog = prog, name = name, date = date, year = year,
		     user = user, host = host)
    outf.write(s)

    #### process points list to ascii vector file (merge in vertices)
    inf = file(tmp)
    shutil.copyfileobj(inf, outf)
    inf.close()

    outf.close()

    if not name:
        #### if no name for vector file given, cat to stdout
	grass.message(_("Output to stdout")) 
	inf = file(digfile)
	shutil.copyfileobj(inf, sys.stdout)
	inf.close()
    else:
        #### import to binary vector file
	grass.message(_("Importing with v.in.ascii ...")) 
	if grass.run_command('v.in.ascii', flags = do3D, input = digfile,
			     output = name, format = 'standard') == 0:
	    grass.message(_('"%s" successfully created') % name) 
	else:
	    grass.fatal(_('An error occured on creating "%s", please check') % name)

if __name__ == "__main__":
    options, flags = grass.parser()
    atexit.register(cleanup)
    main()

