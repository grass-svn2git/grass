"""Test t.rast.to.rast3

(C) 2014 by the GRASS Development Team
This program is free software under the GNU General Public
License (>=v2). Read the file COPYING that comes with GRASS
for details.

@author Soeren Gebbert
"""

import grass.pygrass.modules as pymod
import subprocess
from grass.gunittest.case import TestCase
from grass.gunittest.gmodules import SimpleModule

class TestSTRDSToRast3(TestCase):

    def setUp(self):
        """Create input data
        """
        self.use_temp_region()
        self.runModule("g.gisenv",  set="TGIS_USE_CURRENT_MAPSET=1")
        self.runModule("g.region",  s=0,  n=80,  w=0,  e=120,  b=0,  t=50,  res=10,  res3=10)

        self.runModule("r.mapcalc", expression="prec_1i = 100")
        self.runModule("r.mapcalc", expression="prec_2i = 200")
        self.runModule("r.mapcalc", expression="prec_3i = 300")
        self.runModule("r.mapcalc", expression="prec_4i = 400")
        self.runModule("r.mapcalc", expression="prec_5i = 500")
        self.runModule("r.mapcalc", expression="prec_6i = 600")
        
        self.runModule("r.mapcalc", expression="prec_1d = 100.0")
        self.runModule("r.mapcalc", expression="prec_2d = 200.0")
        self.runModule("r.mapcalc", expression="prec_3d = 300.0")
        self.runModule("r.mapcalc", expression="prec_4d = 400.0")
        self.runModule("r.mapcalc", expression="prec_5d = 500.0")
        self.runModule("r.mapcalc", expression="prec_6d = 600.0")
        
        self.runModule("r.mapcalc", expression="prec_1f = float(100.0)")
        self.runModule("r.mapcalc", expression="prec_2f = float(200.0)")
        self.runModule("r.mapcalc", expression="prec_3f = float(300.0)")
        self.runModule("r.mapcalc", expression="prec_4f = float(400.0)")
        self.runModule("r.mapcalc", expression="prec_5f = float(500.0)")
        self.runModule("r.mapcalc", expression="prec_6f = float(600.0)")
        
        self.runModule("t.create", type="strds",  temporaltype="absolute",  
                       output="precip_i",  title="A test integer",  
                       description="A test integer values")
        self.runModule("t.register", flags="i",  type="raster",  input="precip_i",  
                       maps="prec_1i,prec_2i,prec_3i,prec_4i,prec_5i,prec_6i",  
                       start="2001-01-01", increment="3 months")

        self.runModule("t.create", type="strds",  temporaltype="absolute",  
                       output="precip_f",  title="A test float",  
                       description="A test float values")
        self.runModule("t.register", flags="i",  type="raster",  input="precip_f",
                       maps="prec_1f,prec_2f,prec_3f,prec_4f,prec_5f,prec_6f",  
                       start="2001-01-01", increment="3 months")

        self.runModule("t.create", type="strds",  temporaltype="absolute",  
                       output="precip_d",  title="A test float",  
                       description="A test float values")
        self.runModule("t.register", flags="i",  type="raster",  input="precip_d",  
                       maps="prec_1d,prec_2d,prec_3d,prec_4d,prec_5d,prec_6d",  
                       start="2001-01-01", increment="3 months")

    def tearDown(self):
        """Remove generated data"""
        #self.runModule("t.remove",  flags="rf",  type="strds",  
        #                           inputs="precip_i,precip_f,precip_d")
        #self.runModule('g.remove', type='rast', pattern='prec_*', flags='f')
        self.del_temp_region()

    def otest_3m(self):
        """Convert STRDS into 3d raster map, granularity 3 months"""

        self.assertModule("t.rast.to.rast3",  input="precip_i",  output="precip_i")
        self.assertModule("t.rast.to.rast3",  input="precip_f",  output="precip_f")
        self.assertModule("t.rast.to.rast3",  input="precip_d",  output="precip_d")

        univar_string="""n=576
                        null_cells=0
                        cells=576
                        min=100
                        max=600
                        range=500
                        mean=350
                        mean_of_abs=350
                        stddev=170.782512765993
                        variance=29166.6666666667
                        coeff_var=48.7950036474267
                        sum=201600"""

        self.assertRaster3dFitsUnivar(raster="precip_i", reference=univar_string, precision=2)
        self.assertRaster3dFitsUnivar(raster="precip_f", reference=univar_string, precision=2)
        self.assertRaster3dFitsUnivar(raster="precip_d", reference=univar_string, precision=2)

        tinfo_string="""north=80
                        south=0
                        east=120
                        west=0
                        bottom=1213
                        top=1231
                        nsres=10
                        ewres=10
                        tbres=3
                        rows=8
                        cols=12
                        depths=6
                        datatype="DCELL"
                        timestamp="1 Jan 2001 00:00:00 / 1 Jul 2002 00:00:00"
                        units="none"
                        vertical_units="months" """

        self.assertRaster3dFitsInfo(raster="precip_i", reference=tinfo_string, precision=2)

        tinfo_string="""north=80
                        south=0
                        east=120
                        west=0
                        bottom=1213
                        top=1231
                        nsres=10
                        ewres=10
                        tbres=3
                        rows=8
                        cols=12
                        depths=6
                        datatype="FCELL"
                        timestamp="1 Jan 2001 00:00:00 / 1 Jul 2002 00:00:00"
                        units="none"
                        vertical_units="months" """

        self.assertRaster3dFitsInfo(raster="precip_f", reference=tinfo_string, precision=2)

        tinfo_string="""north=80
                        south=0
                        east=120
                        west=0
                        bottom=1213
                        top=1231
                        nsres=10
                        ewres=10
                        tbres=3
                        rows=8
                        cols=12
                        depths=6
                        datatype="DCELL"
                        timestamp="1 Jan 2001 00:00:00 / 1 Jul 2002 00:00:00"
                        units="none"
                        vertical_units="months" """

        self.assertRaster3dFitsInfo(raster="precip_d", reference=tinfo_string, precision=2)

    def test_3m_gap(self):
        """Convert STRDS with gaps into 3d raster map, granularity 3 months"""
  
        self.runModule("t.unregister", maps="prec_3d,prec_3f,prec_3i")

        self.assertModule("t.rast.to.rast3",  input="precip_i",  output="precip_i")
        self.assertModule("t.rast.to.rast3",  input="precip_f",  output="precip_f")
        self.assertModule("t.rast.to.rast3",  input="precip_d",  output="precip_d")

        univar_string="""n=480
                        null_cells=96
                        cells=576
                        min=100
                        max=600
                        range=500
                        mean=360
                        mean_of_abs=360
                        stddev=185.472369909914
                        variance=34400
                        coeff_var=51.5201027527539
                        sum=172800"""

        univar = SimpleModule("r3.univar", flags="g", map="precip_i")
        self.assertModuleKeyValue(module=univar, reference=univar_string, precision=2, sep="=")

        tinfo_string="""north=80
                        south=0
                        east=120
                        west=0
                        bottom=1213
                        top=1231
                        nsres=10
                        ewres=10
                        tbres=3
                        rows=8
                        cols=12
                        depths=6
                        datatype="DCELL"
                        timestamp="1 Jan 2001 00:00:00 / 1 Jul 2002 00:00:00"
                        units="none"
                        vertical_units="months" """

        self.assertRaster3dFitsInfo(raster="precip_i", reference=tinfo_string, precision=2)

        tinfo_string="""north=80
                        south=0
                        east=120
                        west=0
                        bottom=1213
                        top=1231
                        nsres=10
                        ewres=10
                        tbres=3
                        rows=8
                        cols=12
                        depths=6
                        datatype="FCELL"
                        timestamp="1 Jan 2001 00:00:00 / 1 Jul 2002 00:00:00"
                        units="none"
                        vertical_units="months" """

        self.assertRaster3dFitsInfo(raster="precip_f", reference=tinfo_string, precision=2)

        tinfo_string="""north=80
                        south=0
                        east=120
                        west=0
                        bottom=1213
                        top=1231
                        nsres=10
                        ewres=10
                        tbres=3
                        rows=8
                        cols=12
                        depths=6
                        datatype="DCELL"
                        timestamp="1 Jan 2001 00:00:00 / 1 Jul 2002 00:00:00"
                        units="none"
                        vertical_units="months" """

        self.assertRaster3dFitsInfo(raster="precip_d", reference=tinfo_string, precision=2)

class TestSTRDSToRast3MultiGran(TestCase):

    def setUp(self):
        """Create input data
        """
        self.use_temp_region()
        self.runModule("g.gisenv",  set="TGIS_USE_CURRENT_MAPSET=1")
        self.runModule("g.region",  s=0,  n=80,  w=0,  e=120,  b=0,  t=50,  res=10,  res3=10)
        
        self.runModule("r.mapcalc", expression="prec_1d = 100.0")
        self.runModule("r.mapcalc", expression="prec_2d = 200.0")
        self.runModule("r.mapcalc", expression="prec_3d = 300.0")
        self.runModule("r.mapcalc", expression="prec_4d = 400.0")
        self.runModule("r.mapcalc", expression="prec_5d = 500.0")
        self.runModule("r.mapcalc", expression="prec_6d = 600.0")

        self.runModule("t.create", type="strds",  temporaltype="absolute",  
                       output="precip_d",  title="A test float",  
                       description="A test float values")

    def tearDown(self):
        """Remove generated data"""
        #self.runModule("t.remove",  flags="rf",  type="strds", inputs="precip_d")
        #self.runModule('g.remove', type='rast', pattern='prec_*', flags='f')
        self.del_temp_region()

    def otest_years(self):
        """Convert STRDS into 3d raster map, granularity5 years"""

        self.runModule("t.register", flags="i",  type="rast",  input="precip_d",  
                       maps="prec_1d,prec_2d,prec_3d,prec_4d,prec_5d,prec_6d",  
                       start="2000-01-01", increment="5 years")

        self.assertModule("t.rast.to.rast3",  input="precip_d",  output="precip_d")

        tinfo_string="""north=80
                        south=0
                        east=120
                        west=0
                        bottom=100
                        top=130
                        nsres=10
                        ewres=10
                        tbres=3
                        rows=8
                        cols=12
                        depths=6
                        datatype="DCELL"
                        timestamp="1 Jan 2000 00:00:00 / 1 Jan 2030 00:00:00"
                        units="none"
                        vertical_units="years" """

        self.assertRaster3dFitsInfo(raster="precip_d", reference=tinfo_string, precision=2)

    def otest_months(self):
        """Convert STRDS into 3d raster map, granularity 6 months"""

        self.runModule("t.register", flags="i",  type="rast",  input="precip_d",  
                       maps="prec_1d,prec_2d,prec_3d,prec_4d,prec_5d,prec_6d",  
                       start="2000-01-01", increment="6 months")

        self.assertModule("t.rast.to.rast3",  input="precip_d",  output="precip_d")

        tinfo_string="""north=80
                        south=0
                        east=120
                        west=0
                        bottom=1201
                        top=1237
                        nsres=10
                        ewres=10
                        tbres=6
                        rows=8
                        cols=12
                        depths=6
                        datatype="DCELL"
                        timestamp="1 Jan 2000 00:00:00 / 1 Jan 2003 00:00:00"
                        units="none"
                        vertical_units="months" """

        self.assertRaster3dFitsInfo(raster="precip_d", reference=tinfo_string, precision=2)

    def otest_days(self):
        """Convert STRDS into 3d raster map, granularity 7 days"""

        self.runModule("t.register", flags="i",  type="rast",  input="precip_d",  
                       maps="prec_1d,prec_2d,prec_3d,prec_4d,prec_5d,prec_6d",  
                       start="2000-01-01", increment="7 days")

        self.assertModule("t.rast.to.rast3",  input="precip_d",  output="precip_d")
        self.runModule("r3.info", map="precip_d")

        tinfo_string="""north=80
                        south=0
                        east=120
                        west=0
                        bottom=36524
                        top=36566
                        nsres=10
                        ewres=10
                        tbres=7
                        rows=8
                        cols=12
                        depths=6
                        datatype="DCELL"
                        timestamp="1 Jan 2000 00:00:00 / 12 Feb 2000 00:00:00"
                        units="none"
                        vertical_units="days" """

        self.assertRaster3dFitsInfo(raster="precip_d", reference=tinfo_string, precision=2)

    def otest_hours(self):
        """Convert STRDS into 3d raster map, granularity 7 days"""

        self.runModule("t.register", flags="i",  type="rast",  input="precip_d",  
                       maps="prec_1d,prec_2d,prec_3d,prec_4d,prec_5d,prec_6d",  
                       start="2000-01-01", increment="3 hours")

        self.assertModule("t.rast.to.rast3",  input="precip_d",  output="precip_d")
        self.runModule("r3.info", map="precip_d")

        tinfo_string="""north=80
                        south=0
                        east=120
                        west=0
                        bottom=36524
                        top=36524.8
                        nsres=10
                        ewres=10
                        tbres=0.125
                        rows=8
                        cols=12
                        depths=6
                        datatype="DCELL"
                        timestamp="1 Jan 2000 00:00:00 / 1 Jan 2000 18:00:00"
                        units="none"
                        vertical_units="hours" """

        self.assertRaster3dFitsInfo(raster="precip_d", reference=tinfo_string, precision=2)

    def otest_minutes(self):
        """Convert STRDS into 3d raster map, granularity 7 days"""

        self.runModule("t.register", flags="i",  type="rast",  input="precip_d",  
                       maps="prec_1d,prec_2d,prec_3d,prec_4d,prec_5d,prec_6d",  
                       start="2000-01-01", increment="17 minutes")

        self.assertModule("t.rast.to.rast3",  input="precip_d",  output="precip_d")
        self.runModule("r3.info", map="precip_d")

        tinfo_string="""north=80
                        south=0
                        east=120
                        west=0
                        bottom=36524
                        top=36524.1
                        nsres=10
                        ewres=10
                        tbres=0.0118056
                        rows=8
                        cols=12
                        depths=6
                        datatype="DCELL"
                        timestamp="1 Jan 2000 00:00:00 / 1 Jan 2000 01:42:00"
                        units="none"
                        vertical_units="minutes" """

        self.assertRaster3dFitsInfo(raster="precip_d", reference=tinfo_string, precision=2)

if __name__ == '__main__':
    from grass.gunittest.main import test
    test()
