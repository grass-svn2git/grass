#!/usr/bin/env python

############################################################################
#
# MODULE:       wxpyimgview
# AUTHOR(S):    Glynn Clements <glynn@gclements.plus.com>
# COPYRIGHT:    (C) 2010 Glynn Clements
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
#############################################################################/

#%Module
#% description: View BMP images from the PNG driver.
#% keywords: display
#% keywords: raster
#%End
#%Option
#% key: image
#% type: string
#% required: yes
#% multiple: no
#% description: Image file
#% gisprompt: old_file,file,input
#%End
#%Option
#% key: percent
#% type: integer
#% required: no
#% multiple: no
#% description: Percentage of CPU time to use
#% answer: 10
#%End

import sys
import os
import grass.script as grass

if __name__ == "__main__":
    options, flags = grass.parser()
    image   = options['image']
    percent = options['percent']
    python = os.getenv('GRASS_PYTHON', 'python')
    gisbase = os.environ['GISBASE']
    script = os.path.join(gisbase, "etc", "wxpyimgview_gui.py")
    os.execlp(python, script, script, image, percent)
