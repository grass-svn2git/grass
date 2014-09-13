#!/usr/bin/env python
#
############################################################################
#
# MODULE:       v.in.lines
#
# AUTHOR(S):    Hamish Bowman
#
# PURPOSE:      Import point data as lines ('v.in.mapgen -f' wrapper script)
#
# COPYRIGHT:    (c) 2009-2010 The GRASS Development Team
#
#               This program is free software under the GNU General Public
#               License (>=v2). Read the file COPYING that comes with GRASS
#               for details.
#
#############################################################################
#%module
#% description: Imports ASCII x,y[,z] coordinates as a series of lines.
#% keywords: vector
#% keywords: import
#%end
#%flag
#% key: z
#% description: Create a 3D line from 3 column data 
#%end
#%option G_OPT_F_INPUT
#% description: Name of input file (or "-" to read from stdin)
#%end
#%option G_OPT_V_OUTPUT
#%end
#%option G_OPT_F_SEP
#%end

import sys
import os
import atexit
import string
from grass.script.utils import separator, try_remove
from grass.script import core as grass

def cleanup():
    try_remove(tmp)

def main():
    global tmp

    fs = separator(options['separator'])
    threeD = flags['z']

    prog = 'v.in.lines'

    if threeD:
        do3D = 'z'
    else:
        do3D = ''


    tmp = grass.tempfile()


    #### parse field separator
    if fs in ('space', 'tab'):
        fs = ' '
    elif fs == 'comma':
        fs = ','
    else:
        if len(fs) > 1:
            grass.warning(_("Invalid field separator, using '%s'") % fs[0])
        try:
            fs = fs[0]
        except IndexError:
            grass.fatal(_("Invalid field separator '%s'") % fs)

    #### set up input file
    if options['input'] == '-':
        infile = None
        inf = sys.stdin
    else:
        infile = options['input']
        if not os.path.exists(infile):
            grass.fatal(_("Unable to read input file <%s>") % infile)
        grass.debug("input file=[%s]" % infile)


    if not infile:
        # read from stdin and write to tmpfile (v.in.mapgen wants a real file)
        outf = file(tmp, 'w')
        for line in inf:
            if len(line.lstrip()) == 0 or line[0] == '#':
                continue
            outf.write(line.replace(fs, ' '))

        outf.close()
        runfile = tmp
    else:
        # read from a real file
        if fs == ' ':
            runfile = infile
        else:
            inf = file(infile)
            outf = file(tmp, 'w')

            for line in inf:
                if len(line.lstrip()) == 0 or line[0] == '#':
                    continue
                outf.write(line.replace(fs, ' '))

            inf.close()
            outf.close()
            runfile = tmp


    ##### check that there are at least two columns (three if -z is given)
    inf = file(runfile)
    for line in inf:
        if len(line.lstrip()) == 0 or line[0] == '#':
            continue
        numcols = len(line.split())
        break
    inf.close()
    if (do3D and numcols < 3) or (not do3D and numcols < 2):
        grass.fatal(_("Not enough data columns. (incorrect fs setting?)"))


    grass.run_command('v.in.mapgen', flags = 'f' + do3D,
                      input = runfile, output = options['output'])


if __name__ == "__main__":
    options, flags = grass.parser()
    atexit.register(cleanup)
    main()
