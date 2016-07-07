#!/usr/bin/env python

############################################################################
#
# MODULE:        test_small_data
# AUTHOR:        Vaclav Petras
# PURPOSE:       Fast test using a small example
# COPYRIGHT:     (C) 2016 by Vaclav Petras and the GRASS Development Team
#
#                This program is free software under the GNU General Public
#                License (>=v2). Read the file COPYING that comes with GRASS
#                for details.
#
#############################################################################

from grass.gunittest.case import TestCase
from grass.gunittest.main import test
from grass.script import list_strings

# generated by
# g.region n=12 s=9 e=21 w=18 t=8 b=4 res=1 res3=1 -p3
# r3.mapcalc "x = rand(0,10)" seed=100 && r3.out.ascii x prec=0
INPUT = """\
version: grass7
order: nsbt
north: 12
south: 9
east: 21
west: 18
top: 8
bottom: 4
rows: 3
cols: 3
levels: 4
6 5 1
0 7 5
1 7 1
8 2 1
3 4 2
8 5 6
1 2 8
1 5 5
1 1 3
1 8 3
6 5 1
5 1 7
"""

# created from the above and template from
# r.mapcalc "x = rand(0,10)" seed=100 && r.out.ascii x prec=0
OUTPUTS = [
"""\
north: 12
south: 9
east: 21
west: 18
rows: 3
cols: 3
12.5 10.5 2.5
0.5 14.5 10.5
2.5 14.5 2.5
""",
"""\
north: 12
south: 9
east: 21
west: 18
rows: 3
cols: 3
16.5 4.5 2.5
6.5 8.5 4.5
16.5 10.5 12.5
""",
"""\
north: 12
south: 9
east: 21
west: 18
rows: 3
cols: 3
2.5 4.5 16.5
2.5 10.5 10.5
2.5 2.5 6.5
""",
"""\
north: 12
south: 9
east: 21
west: 18
rows: 3
cols: 3
2.5 16.5 6.5
12.5 10.5 2.5
10.5 2.5 14.5
""",
]


class TestR3ToRast(TestCase):
    # TODO: replace by unified handing of maps
    # mixing class and object attributes
    to_remove_3d = []
    to_remove_2d = []
    rast3d = 'r3_to_rast_test_a_b_coeff'
    rast2d = 'r3_to_rast_test_a_b_coeff'
    rast2d_ref = 'r3_to_rast_test_a_b_coeff_ref'
    rast2d_refs = []

    def setUp(self):
        self.use_temp_region()
        self.runModule('r3.in.ascii', input='-', stdin_=INPUT,
                       output=self.rast3d)
        self.to_remove_3d.append(self.rast3d)
        self.runModule('g.region', raster_3d=self.rast3d)

        for i, data in enumerate(OUTPUTS):
            rast = "%s_%d" % (self.rast2d_ref, i)
            self.runModule('r.in.ascii', input='-', stdin_=data,
                           output=rast)
            self.to_remove_2d.append(rast)
            self.rast2d_refs.append(rast)

    def tearDown(self):
        if self.to_remove_3d:
            self.runModule('g.remove', flags='f', type='raster_3d',
                           name=','.join(self.to_remove_3d), verbose=True)
        if self.to_remove_2d:
            self.runModule('g.remove', flags='f', type='raster',
                           name=','.join(self.to_remove_2d), verbose=True)
        self.del_temp_region()

    def test_a_b_coeff(self):
        self.assertModule('r3.to.rast', input=self.rast3d,
                          output=self.rast2d, multiply=2, add=0.5)
        rasts = list_strings('raster', mapset=".",
                             pattern="%s_*" % self.rast2d,
                             exclude="%s_*" % self.rast2d_ref)
        self.assertEquals(len(rasts), 4,
                          msg="Wrong number of 2D rasters present"
                              " in the mapset")
        ref_info = dict(cells=9)
        ref_univar = dict(cells=9, null_cells=0)
        for rast in rasts:
            self.assertRasterExists(rast)
            # the following doesn't make much sense because we just listed them
            self.to_remove_2d.append(rast)
            self.assertRasterFitsInfo(raster=rast, reference=ref_info,
                                      precision=0)
            self.assertRasterFitsUnivar(raster=rast, reference=ref_univar,
                                        precision=0)

        # check the actual values
        for rast_ref, rast in zip(self.rast2d_refs, rasts):
            self.assertRastersNoDifference(actual=rast,
                                           reference=rast_ref,
                                           precision=0.1)


if __name__ == '__main__':
    test()
