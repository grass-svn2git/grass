#!/usr/bin/env python
# -*- coding: utf-8 -*-
############################################################################
#
# MODULE:	t.remove
# AUTHOR(S):	Soeren Gebbert
#               
# PURPOSE:	Remove space time or map dataset
# COPYRIGHT:	(C) 2011 by the GRASS Development Team
#
#		This program is free software under the GNU General Public
#		License (version 2). Read the file COPYING that comes with GRASS
#		for details.
#
#############################################################################

#%module
#% description: Remove space time or map datasets from temporal database
#% keywords: spacetime
#% keywords: dataset
#% keywords: remove
#%end

#%option
#% key: dataset
#% type: string
#% description: Name(s) of the space time or map dataset to be removed from the temporal database
#% required: yes
#% multiple: no
#%end

#%option
#% key: type
#% type: string
#% description: Type of the space time dataset, default is strds
#% required: no
#% options: strds, str3ds, stvds, raster, raster3d, vector
#% answer: strds
#%end

import grass.script as grass

############################################################################

def main():
    
    # Get the options
    names = options["dataset"]
    type = options["type"]

    # Make sure the temporal database exists
    grass.create_temporal_database()
    
    mapset =  grass.gisenv()["MAPSET"]
    
    for name in names.split(","):
        name = name.strip()
        # Check for the mapset in name
        if name.find("@") < 0:
            id = name + "@" + mapset
        else:
            id = name

        if type == "strds":
            ds = grass.space_time_raster_dataset(id)
        if type == "str3ds":
            ds = grass.space_time_raster3d_dataset(id)
        if type == "stvds":
            ds = grass.space_time_vector_dataset(id)
        if type == "raster":
            ds = grass.raster_dataset(id)
        if type == "raster3d":
            ds = grass.raster3d_dataset(id)
        if type == "vector":
            ds = grass.vector_dataset(id)

        if ds.is_in_db() == False:
            grass.fatal(ds.get_type() + " dataset <" + name + "> not found in temporal database")

        # We need to read some data from the temporal database
        ds.select()
        ds.delete()

if __name__ == "__main__":
    options, flags = grass.core.parser()
    main()

