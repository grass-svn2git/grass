#!/usr/bin/env python
#
############################################################################
#
# MODULE:	r.buffer
# AUTHOR(S):	Glynn Clements
# PURPOSE:	Replacement for r.buffer using r.grow.distance
#
# COPYRIGHT:	(C) 2008 by Glynn Clements
#
#		This program is free software under the GNU General Public
#		License (>=v2). Read the file COPYING that comes with GRASS
#		for details.
#
#############################################################################

#%Module
#% description: Creates a raster map layer showing buffer zones surrounding cells that contain non-NULL category values.
#% keywords: raster, buffer
#%End
#%Flag
#% key: z
#% description: Ignore zero (0) data cells instead of NULL cells
#%End
#%Option
#% key: input
#% type: string
#% required: yes
#% multiple: no
#% key_desc: name
#% description: Name of input raster map
#% gisprompt: old,cell,raster
#%End
#%Option
#% key: output
#% type: string
#% required: yes
#% multiple: no
#% key_desc: name
#% description: Name for output raster map
#% gisprompt: new,cell,raster
#%End
#%Option
#% key: distances
#% type: double
#% required: yes
#% multiple: yes
#% description: Distance zone(s)
#%End
#%Option
#% key: units
#% type: string
#% required: no
#% multiple: no
#% options: meters,kilometers,feet,miles,nautmiles
#% description: Units of distance
#% answer: meters
#%End

import sys
import os
import atexit
import string
import math
import grass

scales = {
    'meters': 1.0,
    'kilometers': 1000.0,
    'feet': 0.3048,
    'miles': 1609.344,
    'nautmiles': 1852.0
    }

# what to do in case of user break:
def cleanup():
    grass.run_command('g.remove', quiet = True, flags = 'f', rast = temp_src)
    grass.run_command('g.remove', quiet = True, flags = 'f', rast = temp_dist)

def main():
    global temp_dist, temp_src

    input = options['input']
    output = options['output']
    distances = options['distances']
    units = options['units']
    zero = flags['z']

    tmp = str(os.getpid())
    temp_dist = "r.buffer.tmp.%s.dist" % tmp
    temp_src = "r.buffer.tmp.%s.src" % tmp

    #check if input file exists
    if not grass.find_file(input)['file']:
	grass.fatal("<%s> does not exist." % input)

    scale = scales[units]

    distances  = distances.split(',')
    distances1 = [scale * float(d) for d in distances]
    distances2 = [d * d for d in distances1]

    grass.run_command('r.grow.distance',  input = input, metric = 'squared',
		      distance = temp_dist)

    if zero:
	t = string.Template("$temp_src = if($input == 0,null(),1)")
    else:
	t = string.Template("$temp_src = if(isnull($input),null(),1)")

    e = t.substitute(temp_src = temp_src, input = input)
    grass.run_command('r.mapcalc', expression = e)

    s = "$output = if(!isnull($input),$input,%s)"
    for n, dist2 in enumerate(distances2):
	s %= "if($dist <= %f,%d,%%s)" % (dist2,n + 2)
    s %= "null()"

    t = string.Template(s)
    e = t.substitute(output = output, input = temp_src, dist = temp_dist)
    grass.run_command('r.mapcalc', expression = e)

    p = grass.feed_command('r.category', map = output, rules = '-')
    p.stdin.write("1:distances calculated from these locations\n")
    d0 = "0"
    for n, d in enumerate(distances):
	p.stdin.write("%d:%s-%s %s\n" % (n + 2, d0, d, units))
	d0 = d
    p.stdin.close()
    p.wait()

    grass.run_command('r.colors', map = output, color = 'rainbow')

    # write cmd history:
    grass.raster_history(output)

if __name__ == "__main__":
    options, flags = grass.parser()
    atexit.register(cleanup)
    main()
