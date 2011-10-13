#!/usr/bin/env python
# -*- coding: utf-8 -*-
############################################################################
#
# MODULE:	t.info
# AUTHOR(S):	Soeren Gebbert
#               
# PURPOSE:	Print information about a space-time dataset
# COPYRIGHT:	(C) 2011 by the GRASS Development Team
#
#		This program is free software under the GNU General Public
#		License (version 2). Read the file COPYING that comes with GRASS
#		for details.
#
#############################################################################

#%module
#% description: List informtion about space time and map datasets
#% keywords: spacetime dataset
#% keywords: remove
#%end

#%option
#% key: input
#% type: string
#% description: Name of an existing space time or map dataset
#% required: no
#% multiple: no
#%end

#%option
#% key: type
#% type: string
#% description: Type of the dataset, default is strds (space time raster dataset)
#% required: no
#% options: strds, str3ds, stvds, rast, rast3d, vect
#% answer: strds
#%end

#%flag
#% key: g
#% description: Print information in shell style
#%end

#%flag
#% key: t
#% description: Print temporal relation matrix for space time datasets
#%end

#%flag
#% key: s
#% description: Print information about the temporal DBMI interface and exit
#%end


import grass.script as grass
import grass.temporal as tgis

############################################################################

def main():

    # Get the options
    name = options["input"]
    type = options["type"]
    shellstyle = flags['g']
    tmatrix = flags['t']
    system = flags['s']

    # Make sure the temporal database exists
    tgis.create_temporal_database()

    #Get the current mapset to create the id of the space time dataset

    if system:
        #      0123456789012345678901234567890
        print " +------------------- Temporal DBMI backend information ----------------------+"
        print " | DBMI Python interface:...... " + str(tgis.dbmi.__name__)
        print " | DBMI init string:........... " + str(tgis.get_temporal_dbmi_init_string())
        print " | SQL template path:.......... " + str(tgis.get_sql_template_path())
        print " +----------------------------------------------------------------------------+"
        return

    if not system and not name:
        grass.fatal(_("Please specify %s=") % ("name"))

    if name.find("@") >= 0:
        id = name
    else:
        mapset =  grass.gisenv()["MAPSET"]
        id = name + "@" + mapset

    if type == "strds":
        sp = tgis.space_time_raster_dataset(id)
    if type == "str3ds":
        sp = tgis.space_time_raster3d_dataset(id)
    if type == "stvds":
        sp = tgis.space_time_vector_dataset(id)
    if type == "rast":
        sp = tgis.raster_dataset(id)
        tmatrix = False
    if type == "rast3d":
        sp = tgis.raster3d_dataset(id)
        tmatrix = False
    if type == "vect":
        sp = tgis.vector_dataset(id)
        tmatrix = False

    if sp.is_in_db() == False:
        grass.fatal("Dataset <" + name + "> not found in temporal database")
        
    # Insert content from db
    sp.select()

    if tmatrix:
        matrix = sp.get_temporal_relation_matrix()

        for row in matrix:
            for col in row:
                print col,
            print " "
        print " "

    if shellstyle == True:
        sp.print_shell_info()
    else:
        sp.print_info()

if __name__ == "__main__":
    options, flags = grass.parser()
    main()

