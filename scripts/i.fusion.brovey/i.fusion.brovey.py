#!/usr/bin/env python

############################################################################
#
# MODULE:	i.fusion.brovey
# AUTHOR(S):	Markus Neteler. <neteler itc it>
#               Converted to Python by Glynn Clements
# PURPOSE:	Brovey transform to merge
#                 - LANDSAT-7 MS (2, 4, 5) and pan (high res)
#                 - SPOT MS and pan (high res)
#                 - QuickBird MS and pan (high res)
#
# COPYRIGHT:	(C) 2002-2008 by the GRASS Development Team
#
#		This program is free software under the GNU General Public
#		License (>=v2). Read the file COPYING that comes with GRASS
#		for details.
#
# REFERENCES:
#             (?) Roller, N.E.G. and Cox, S., 1980. Comparison of Landsat MSS
#                and merged MSS/RBV data for analysis of natural vegetation.
#                Proc. of the 14th International Symposium on Remote Sensing
#                of Environment, San Jose, Costa Rica, 23-30 April, pp. 1001-1007.
#
#               for LANDSAT 5: see Pohl, C 1996 and others
#
# TODO:         add overwrite test at beginning of the script
#############################################################################

#%Module
#%  description: Brovey transform to merge multispectral and high-res panchromatic channels
#%  keywords: raster, imagery, fusion
#%End
#%Flag
#%  key: l
#%  description: sensor: LANDSAT
#%END
#%Flag
#%  key: q
#%  description: sensor: QuickBird
#%END
#%Flag
#%  key: s
#%  description: sensor: SPOT
#%END
#%option
#% key: ms1
#% type: string
#% gisprompt: old,cell,raster
#% description: raster input map (green: tm2 | qbird_green | spot1)
#% required : yes
#%end
#%option
#% key: ms2
#% type: string
#% gisprompt: old,cell,raster
#% description: raster input map (NIR: tm4 | qbird_nir | spot2)
#% required : yes
#%end
#%option
#% key: ms3
#% type: string
#% gisprompt: old,cell,raster
#% description: raster input map (MIR; tm5 | qbird_red | spot3)
#% required : yes
#%end
#%option
#% key: pan
#% type: string
#% gisprompt: old,cell,raster
#% description: raster input map (etmpan | qbird_pan | spotpan)
#% required : yes
#%end
#%option
#% key: outputprefix
#% type: string
#% gisprompt: new,cell,raster
#% description: raster output map prefix (e.g. 'brov')
#% required : yes
#%end

import sys
import os
import string
import grass

def main():
    global tmp

    landsat = flags['l']
    quickbird = flags['q']
    spot = flags['s']

    ms1 = options['ms1']
    ms2 = options['ms2']
    ms3 = options['ms3']
    pan = options['pan']
    out = options['outputprefix']

    tmp = str(os.getpid())

    if not landsat and not quickbird and not spot:
	grass.fatal("Please select a flag to specify the satellite sensor")

    #get PAN resolution:
    s = grass.read_command('r.info', flags = 's', map = pan)
    kv = grass.parse_key_val(s)
    nsres = float(kv['nsres'])
    ewres = float(kv['ewres'])
    panres = (nsres + ewres) / 2

    # clone current region
    grass.use_temp_region()

    grass.message("Using resolution from PAN: %f" % panres)
    grass.run_command('g.region', flags = 'a', res = panres)

    grass.message("Performing Brovey transformation...")

    # The formula was originally developed for LANDSAT-TM5 and SPOT, 
    # but it also works well with LANDSAT-TM7
    # LANDSAT formula:
    #  r.mapcalc "brov.red=1. *  tm.5 / (tm.2 + tm.4 + tm.5) * etmpan"
    #  r.mapcalc "brov.green=1. * tm.4 /(tm.2 + tm.4 + tm.5) * etmpan"
    #  r.mapcalc "brov.blue=1. * tm.2 / (tm.2 + tm.4 + tm.5) * etmpan"
    #
    # SPOT formula:
    # r.mapcalc "brov.red= 1.  * spot.ms.3 / (spot.ms.1 + spot.ms.2 + spot.ms.3) * spot.p"
    # r.mapcalc "brov.green=1. * spot.ms.2 / (spot.ms.1 + spot.ms.2 + spot.ms.3) * spot.p"
    # r.mapcalc "brov.blue= 1. * spot.ms.1 / (spot.ms.1 + spot.ms.2 + spot.ms.3) * spot.p"
    # note: for RGB composite then revert brov.red and brov.green!

    grass.message("Calculating %s.{red,green,blue}: ..." % out)
    t = string.Template(
	'''eval(k = float("$pan") / ("$ms1" + "$ms2" + "$ms3"))
	   "$out.red"   = "$ms3" * k
	   "$out.green" = "$ms2" * k
	   "$out.blue"  = "$ms1" * k''')
    e = t.substitute(out = out, pan = pan, ms1 = ms1, ms2 = ms2, ms3 = ms3)
    if grass.run_command('r.mapcalc', expression = e) != 0:
	grass.fatal("An error occurred while running r.mapcalc")

    # Maybe?
    #r.colors   $GIS_OPT_OUTPUTPREFIX.red col=grey
    #r.colors   $GIS_OPT_OUTPUTPREFIX.green col=grey
    #r.colors   $GIS_OPT_OUTPUTPREFIX.blue col=grey
    #to blue-ish, therefore we modify
    #r.colors $GIS_OPT_OUTPUTPREFIX.blue col=rules << EOF
    #5 0 0 0
    #20 200 200 200
    #40 230 230 230
    #67 255 255 255
    #EOF

    if spot:
        #apect table is nice for SPOT:
	grass.message("Assigning color tables for SPOT ...")
	for ch in ['red', 'green', 'blue']:
	    grass.run_command('r.colors', map = "%s.%s" % (out, ch), col = 'aspect')
	grass.message("Fixing output names...")
	for s, d in [('green','tmp'),('red','green'),('tmp','red')]:
	    src = "%s.%s" % (out, s)
	    dst = "%s.%s" % (out, d)
	    grass.run_command('g.rename', rast = (src, dst), quiet = True)
    else:
	#aspect table is nice for LANDSAT and QuickBird:
	grass.message("Assigning color tables for LANDSAT or QuickBird ...")
	for ch in ['red', 'green', 'blue']:
	    grass.run_command('r.colors', map = "%s.%s" % (out, ch), col = 'aspect')

    grass.message("Following pan-sharpened output maps have been generated:")
    for ch in ['red', 'green', 'blue']:
	grass.message("%s.%s" % (out, ch))

    grass.message("To visualize output, run:")
    grass.message("g.region -p rast=%s.red" % out)
    grass.message("d.rgb r=%s.red g=%s.green b=%s.blue" % (out, out, out))
    grass.message("If desired, combine channels with 'r.composite' to a single map.")

    # write cmd history:
    for ch in ['red', 'green', 'blue']:
	grass.raster_history("%s.%s" % (out, ch))

if __name__ == "__main__":
    options, flags = grass.parser()
    main()
