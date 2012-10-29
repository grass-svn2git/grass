#!/usr/bin/env python
############################################################################
#
# MODULE:       v.db.reconnect.all
# AUTHOR(S):    Radim Blazek
#               Converted to Python by Glynn Clements
#               Update for GRASS 7 by Martin Landa <landa.martin gmail.com>
# PURPOSE:      Reconnect all vector maps from the current mapset
# COPYRIGHT:    (C) 2004, 2012 by the GRASS Development Team
#
#               This program is free software under the GNU General
#               Public License (>=v2). Read the file COPYING that
#               comes with GRASS for details.
#
#############################################################################

#%module
#% description: Reconnects attribute tables for all vector maps from the current mapset to a new database.
#% keywords: vector
#% keywords: attribute table
#% keywords: database
#%end
#%flag
#% key: c
#% description: Copy attribute tables to the target database if not exist
#%end
#%flag
#% key: d
#% description: Delete attribute tables from the source database
#%end
#%option G_OPT_DB_DATABASE
#% key: old_database
#% description: Name of source database
#% required: yes
#%end
#%option G_OPT_DB_SCHEMA
#% key: old_schema
#% label: Name of source database schema
#%end
#%option
#% key: new_driver
#% description: Name for target driver
#%end
#%option G_OPT_DB_DATABASE
#% key: new_database
#% description: Name for target database
#% required: yes
#%end
#%option G_OPT_DB_SCHEMA
#% key: new_schema
#% label: Name for target database schema
#%end

import sys
import os
import string

import grass.script as grass

# substitute variables (gisdbase, location_name, mapset)
def substitute_db(database):
    gisenv = grass.gisenv()
    tmpl = string.Template(database)
    
    return tmpl.substitute(GISDBASE = gisenv['GISDBASE'],
                           LOCATION_NAME = gisenv['LOCATION_NAME'],
                           MAPSET = gisenv['MAPSET'])

# create database if doesn't exist
def create_db(driver, database):
    if database in grass.read_command('db.databases', quiet = True,
                                      driver = driver).splitlines():
        return False

    grass.info(_("Target database doesn't exist, "
                 "creating a new database using <%s> driver...") % driver)
    if 0 != grass.run_command('db.createdb', driver = driver,
                              database = database):
        grass.fatal(_("Unable to create database <%s> by driver <%s>") % \
                        (database, driver))
        
    return False

# copy tables if required (-c)
def copy_tab(from_driver, from_database, from_table,
             to_driver, to_database, to_table):
    if to_table in grass.read_command('db.tables', quiet = True,
                                      driver = to_driver,
                                      database = to_database,
                                      stderr = nuldev).splitlines():
        return False
    
    grass.info("Table <%s> in target database doesn't exist, "
               "copying data..." % to_table)
    if 0 != grass.run_command('db.copy', from_driver = from_driver,
                              from_database = from_database,
                              from_table = from_table, to_driver = to_driver,
                              to_database = to_database,
                              to_table = to_table):
        grass.fatal(_("Unable to copy table <%s>") % from_table)
    
    return True

# drop tables if required (-d)
def drop_tab(driver, database, table):
    if 0 != grass.run_command('db.droptable', quiet = True, flags = 'f',
                              driver = driver, database = database,
                              table = table, stderr = nuldev):
        grass.fatal(_("Unable to drop table <%s>") % table)
    
def main():
    old_database = substitute_db(options['old_database'])
    if options['new_driver']:
        new_driver = options['new_driver']
    else:
        new_driver = grass.parse_command('db.connect', flags = 'g')['driver']
    new_database = substitute_db(options['new_database'])
    old_schema = options['old_schema']
    new_schema = options['new_schema']
    
    mapset = grass.gisenv()['MAPSET']
        
    for vect in grass.list_grouped('vect')[mapset]:
        vect = "%s@%s" % (vect, mapset)
        grass.message('-' * 60)
        grass.message(_("Reconnecting vector map <%s>...") % vect)
        grass.message('-' * 60)
        for f in grass.vector_db(vect, stderr = nuldev).itervalues():
            layer = f['layer']
            schema_table = f['table']
            key = f['key']
            database = f['database']
            driver = f['driver']
            
            # split schema.table
            if '.' in schema_table:
                schema, table = schema_table.split('.', 1)
            else:
                schema = ''
                table = schema_table
            
            if new_schema:
                new_schema_table = "%s.%s" % (new_schema, table)
            else:
                new_schema_table = table
            
            grass.debug("DATABASE = '%s' SCHEMA = '%s' TABLE = '%s' ->\n"
                        "      NEW_DATABASE = '%s' NEW_SCHEMA_TABLE = '%s'" % \
                            (old_database, schema, table, new_database, new_schema_table))
            
            if database == old_database and schema == old_schema:
                grass.verbose(_("Reconnecting layer %d...") % layer)
                                          
                if flags['c']:
                    # check if database exists
                    create_db(new_driver, new_database)
                    
                    # check if table exists in new database
                    copy_tab(driver, database, schema_table,
                             new_driver, new_database, new_schema_table)
                
                # reconnect tables
                if 0 != grass.run_command('v.db.connect', flags = 'o', quiet = True, map = vect,
                                          layer = layer, driver = new_driver, database = new_database,
                                          table = new_schema_table, key = key):
                    grass.warning(_("Operation canceled"))
                
                # drop original table if required
                if flags['d']:
                    drop_tab(driver, database, schema_table)

            else:
                grass.warning(_("Layer <%d> will not be reconnected, "
                                "database or schema do not match.") % layer)
         
    return 0

if __name__ == "__main__":
    options, flags = grass.parser()
    nuldev = file(os.devnull, 'w')
    sys.exit(main())
