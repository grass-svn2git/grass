#!/usr/bin/env python

############################################################################
#
# MODULE:       v.db.droprow
# AUTHOR(S):    Markus Neteler
#               Pythonized by Martin Landa
# PURPOSE:      Interface to v.extract -r to drop ...
# COPYRIGHT:    (C) 2009 by the GRASS Development Team
#
#               This program is free software under the GNU General Public
#               License (>=v2). Read the file COPYING that comes with GRASS
#               for details.
#
#############################################################################


#%module
#% description: Removes a vector object (point, line, area, face etc.) from a vector map through attribute selection.
#% keywords: vector
#% keywords: database
#% keywords: attribute table
#%end

#%option
#% key: input
#% type: string
#% gisprompt: old,vector,vector
#% key_desc : name
#% description: Vector map for which to drop vector objects
#% required : yes
#%end

#%option
#% key: output
#% type: string
#% gisprompt: new,vector,vector
#% key_desc : name
#% description: Name for output vector map
#% required : yes
#%end

#%option
#% key: layer
#% type: integer
#% description: Layer of attribute table to use for selection
#% answer: 1
#% required : no
#%end

#%option
#% key: where
#% type: string
#% description: WHERE conditions for vector delete, without 'where' keyword (e.g. "elevation IS NULL")
#% required : yes
#%end

import sys
import grass.script as grass

def main():
    file = grass.find_file(element = 'vector', name = options['input'],
                           mapset = grass.gisenv()['MAPSET'])['name']
    
    if not file:
        grass.fatal(_("Vector map <%s> not found in current mapset") % \
                        options['input'])
    
    # delete vectors via reverse selection
    ret = grass.run_command('v.extract',
                            flags = 'r',
                            input = options['input'], layer = options['layer'],
                            output = options['output'], where = options['where'])
    if ret != 0:
        grass.fatal(_("Error in 'where' statement"))

    # write cmd history:
    grass.vector_history(map = options['output'])

    return 0

if __name__ == "__main__":
    options, flags = grass.parser()
    sys.exit(main())
