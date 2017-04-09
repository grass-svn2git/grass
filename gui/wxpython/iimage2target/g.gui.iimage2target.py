#!/usr/bin/env python

############################################################################
#
# MODULE:    Create 3-Dimensional GCPs from elevation and target image
# AUTHOR(S): Yann modified the code (was Markus Metz for the GCP manager)
# PURPOSE:   Georectification and Ground Control Points management for 3D correction.
# COPYRIGHT: (C) 2012-2017 by Markus Metz, and the GRASS Development Team
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
############################################################################

#%module
#% description: Georectifies a map and allows managing Ground Control Points for 3D correction.
#% keyword: imagery
#% keyword: aerial
#% keyword: photo
#% keyword: georectification
#% keyword: GCP
#% keyword: GUI
#%end

##%option G_OPT_M_LOCATION
##% key: source_location
##% label: The name of the source location (has no projection)
##% description: The name of the source location (has no projection)
###% section: source
##% required: yes
##%end

##%option G_OPT_M_MAPSET
##% key: source_mapset
##% label: The name of the source mapset (has no projection)
##% description: The name of the source mapset (has no projection)
###% section: source
##% required: yes
##%end

##%option G_OPT_I_GROUP
##% key: source_group
##% required: yes
##% section: source
##%end

##%option G_OPT_R_INPUT
##% key: source_image
##% required: yes
###% section: source
##%end

##%option G_OPT_R_INPUT
##% key: target_image
##% label: The name of the image that is already georeferenced used to find location of GCPs
##% description: The name of the image that is already georeferenced used to find the location of GCPs
###% section: target
##% required: no
##%end

##%option 
##% key: camera
##% type: string
##% label: The name of the camera (generated in i.ortho.camera)
##% description: The name of the camera (generated in i.ortho.camera)
##% required: yes
###% section: parameters
##%end

##%option 
##% key: order
##% type: string
##% label: The rectification order 
##% description: The rectification order 
##% required: yes
##% answer: 1
###% section: parameters
##%end

##%option 
##% key: extension
##% type: string
##% label: The name of the output files extension
##% description: The name of the output files extension
##% required: yes
##% answer: _ii2t_out
##% section: target
##%end


"""
Module to run GCP management tool as stadalone application.

@author Vaclav Petras  <wenzeslaus gmail.com> (standalone module)
"""

import os

import grass.script as gscript


def main():
    """
    Sets the GRASS display driver
    """
    options, flags = gscript.parser()

    import wx

    from grass.script.setup import set_gui_path
    set_gui_path()

    from core.settings import UserSettings
    from core.globalvar import CheckWxVersion
    from core.giface import StandaloneGrassInterface
    from iimage2target.ii2t_manager import GCPWizard

    driver = UserSettings.Get(group='display', key='driver', subkey='type')
    if driver == 'png':
        os.environ['GRASS_RENDER_IMMEDIATE'] = 'png'
    else:
        os.environ['GRASS_RENDER_IMMEDIATE'] = 'cairo'

#    if options['source_location']:
#        src_loc = options['source_location']
#    else:
#        gscript.fatal(_("No georeferenced source location provided"))

#    if options['source_mapset']:
#        src_mpt = options['source_mapset']
#    else:
#        gscript.fatal(_("No georeferenced source mapset provided"))

#    if options['source_group']:
#        src_grp = options['source_group']
#    else:
#        gscript.fatal(_("Please provide a source group name to process"))
    
#    if options['source_image']:
#        src_ras = options['source_image']
#    else:
#        gscript.fatal(_("Please provide a source image map name to process"))

#    if options['target_image']:
#        tgt_ras = options['target_image']
#    else:
#        gscript.fatal(_("No georeferenced target map provided"))

#    if options['camera']:
#        camera = options['camera']
#    else:
#        gscript.fatal(_("Please provide a camera name (generated by i.ortho.camera)"))

#    if options['order']:
#        order = options['order']
#    else:
#        gscript.fatal(_("Please provive an order value"))

#    if options['extension']:
#        extension = options['extension']
#    else:
#        gscript.fatal(_("Please provide an output file extension"))


    app = wx.App()
    if not CheckWxVersion([2, 9]):
        wx.InitAllImageHandlers()

#    wizard = GCPWizard(parent=None, giface=StandaloneGrassInterface(), 
#            srcloc=src_loc,srcmpt=src_mpt,srcgrp=src_grp,srcras=src_ras,
#            tgtras=tgt_ras,camera=camera, order=order, extension=extension)

    wizard = GCPWizard(parent=None, giface=StandaloneGrassInterface())
    app.MainLoop()

if __name__ == '__main__':
    main()
