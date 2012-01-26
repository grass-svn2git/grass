# This is a test to list raster maps of a space time raster dataset

# We need to set a specific region in the
# @preprocess step of this test. We generate
# raster with r.mapcalc and create a space time raster datasets
# The region setting should work for UTM and LL test locations
g.region s=0 n=80 w=0 e=120 b=0 t=50 res=10 res3=10 -p3

mkdir test

r.mapcalc --o expr="prec_1 = rand(0, 550)"
r.mapcalc --o expr="prec_2 = rand(0, 450)"
r.mapcalc --o expr="prec_3 = rand(0, 320)"
r.mapcalc --o expr="prec_4 = rand(0, 510)"
r.mapcalc --o expr="prec_5 = rand(0, 300)"
r.mapcalc --o expr="prec_6 = rand(0, 650)"

n1=`g.tempfile pid=1 -d` 

cat > "${n1}" << EOF
prec_1|2001-01-01|2001-07-01
prec_2|2001-02-01|2001-04-01
prec_3|2001-03-01|2001-04-01
prec_4|2001-04-01|2001-06-01
prec_5|2001-05-01|2001-06-01
prec_6|2001-06-01|2001-07-01
EOF

t.create --o type=strds temporaltype=absolute output=precip_abs1 title="A test with input files" descr="A test with input files"

# The first @test
tr.register -i input=precip_abs1 file="${n1}" start="2001-01-01" increment="1 months"
tr.export input=precip_abs1 output=strds_export.tar.bz2 compression=bzip2 workdir=test

tr.import --o input=strds_export.tar.bz2 output=precip_abs1 extrdir=test\
          -oe title="A test" description="Description of a test"
tr.import --o input=strds_export.tar.bz2 output=precip_abs1 extrdir=test\
          -loe title="A test" description="Description of a test"
tr.import --o input=strds_export.tar.bz2 output=precip_abs1 extrdir=test\
              title="A test" description="Description of a test"
tr.import --o input=strds_export.tar.bz2 output=precip_abs1 extrdir=test\
          -l  title="A test" description="Description of a test"

t.remove type=rast input=prec_1,prec_2,prec_3,prec_4,prec_5,prec_6
t.remove type=strds input=precip_abs1
g.remove rast=prec_1,prec_2,prec_3,prec_4,prec_5,prec_6
