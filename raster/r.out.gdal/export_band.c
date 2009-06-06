
/****************************************************************************
*
* MODULE:       r.out.gdal
* AUTHOR(S):    Vytautas Vebra <olivership@gmail.com>
* PURPOSE:      Exports GRASS raster to GDAL suported formats;
*               based on GDAL library.
*
* COPYRIGHT:    (C) 2006-2009 by the GRASS Development Team
*
*               This program is free software under the GNU General Public
*   	    	License (>=v2). Read the file COPYING that comes with GRASS
*   	    	for details.
*
*****************************************************************************/

#include <grass/gis.h>
#include <grass/glocale.h>

#include "cpl_string.h"
#include "gdal.h"
#include "local_proto.h"

int exact_range_check(double, double, GDALDataType, const char *);

/* actual raster band export
 * returns 0 on success
 * -1 on raster data read/write error
 * -2 if given nodata value was present in data
 * -3 if selected GDAL datatype could not hold all values
 * */
int export_band(GDALDatasetH hMEMDS, GDALDataType export_datatype, int band,
		const char *name, const char *mapset,
		struct Cell_head *cellhead, RASTER_MAP_TYPE maptype,
		double nodataval, const char *nodatakey,
		int suppress_main_colortable, int default_nodataval)
{

    struct Colors sGrassColors;
    GDALColorTableH hCT;
    int iColor;
    int bHaveMinMax;
    double dfCellMin;
    double dfCellMax;
    struct FPRange sRange;
    int fd;
    int cols = cellhead->cols;
    int rows = cellhead->rows;
    int ret = 0;

    /* Open GRASS raster */
    fd = G_open_cell_old(name, mapset);
    if (fd < 0) {
	G_warning(_("Unable to open raster map <%s>"), name);
	return -1;
    }

    /* Get raster band  */
    GDALRasterBandH hBand = GDALGetRasterBand(hMEMDS, band);

    if (hBand == NULL) {
	G_warning(_("Unable to get raster band"));
	return -1;
    }

    /* Get min/max values. */
    if (G_read_fp_range(name, mapset, &sRange) == -1) {
	bHaveMinMax = FALSE;
    }
    else {
	bHaveMinMax = TRUE;
	G_get_fp_range_min_max(&sRange, &dfCellMin, &dfCellMax);
    }

    /* suppress useless warnings */
    CPLPushErrorHandler(CPLQuietErrorHandler);
    GDALSetRasterColorInterpretation(hBand, GPI_RGB);
    CPLPopErrorHandler();

    /* use default color rules if no color rules are given */
    if (G_read_colors(name, mapset, &sGrassColors) >= 0) {
	int maxcolor, i;
	CELL min, max;
	char key[200], value[200];
	int rcount;

	G_get_color_range(&min, &max, &sGrassColors);
	if (bHaveMinMax) {
	    if (max < dfCellMax) {
		maxcolor = max;
	    }
	    else {
		maxcolor = (int)ceil(dfCellMax);
	    }
	    if (maxcolor > GRASS_MAX_COLORS) {
		maxcolor = GRASS_MAX_COLORS;
		G_warning("Too many values, color table cut to %d entries",
			  maxcolor);
	    }
	}
	else {
	    if (max < GRASS_MAX_COLORS) {
		maxcolor = max;
	    }
	    else {
		maxcolor = GRASS_MAX_COLORS;
		G_warning("Too many values, color table set to %d entries",
			  maxcolor);
	    }
	}

	rcount = G_colors_count(&sGrassColors);

	G_debug(3, "dfCellMin: %f, dfCellMax: %f, maxcolor: %d", dfCellMin,
		dfCellMax, maxcolor);

	if (!suppress_main_colortable) {
	    hCT = GDALCreateColorTable(GPI_RGB);

	    for (iColor = 0; iColor <= maxcolor; iColor++) {
		int nRed, nGreen, nBlue;
		GDALColorEntry sColor;

		if (G_get_color
		    (iColor, &nRed, &nGreen, &nBlue, &sGrassColors)) {
		    sColor.c1 = nRed;
		    sColor.c2 = nGreen;
		    sColor.c3 = nBlue;
		    sColor.c4 = 255;

		    G_debug(3,
			    "G_get_color: Y, rcount %d, nRed %d, nGreen %d, nBlue %d",
			    rcount, nRed, nGreen, nBlue);
		    GDALSetColorEntry(hCT, iColor, &sColor);
		}
		else {
		    sColor.c1 = 0;
		    sColor.c2 = 0;
		    sColor.c3 = 0;
		    sColor.c4 = 0;

		    G_debug(3,
			    "G_get_color: N, rcount %d, nRed %d, nGreen %d, nBlue %d",
			    rcount, nRed, nGreen, nBlue);
		    GDALSetColorEntry(hCT, iColor, &sColor);
		}
	    }

	    GDALSetRasterColorTable(hBand, hCT);
	}

	if (rcount > 0) {
	    /* Create metadata entries for color table rules */
	    sprintf(value, "%d", rcount);
	    GDALSetMetadataItem(hBand, "COLOR_TABLE_RULES_COUNT", value,
				NULL);
	}

	/* Add the rules in reverse order */
	/* This can cause a GDAL warning with many rules, something like
	 * Warning 1: Lost metadata writing to GeoTIFF ... too large to fit in tag. */
	for (i = rcount - 1; i >= 0; i--) {
	    DCELL val1, val2;
	    unsigned char r1, g1, b1, r2, g2, b2;

	    G_get_f_color_rule(&val1, &r1, &g1, &b1, &val2, &r2, &g2, &b2,
			       &sGrassColors, i);


	    sprintf(key, "COLOR_TABLE_RULE_RGB_%d", rcount - i - 1);
	    sprintf(value, "%e %e %d %d %d %d %d %d", val1, val2, r1, g1, b1,
		    r2, g2, b2);
	    GDALSetMetadataItem(hBand, key, value, NULL);
	}
    }

    /* Create GRASS raster buffer */
    void *bufer = G_allocate_raster_buf(maptype);

    if (bufer == NULL) {
	G_warning(_("Unable to allocate buffer for reading raster map"));
	return -1;
    }
    char *nulls = (char *)G_malloc(cols);

    if (nulls == NULL) {
	G_warning(_("Unable to allocate buffer for reading raster map"));
	return -1;
    }

    /* Copy data form GRASS raster to GDAL raster */
    int row, col;
    int n_nulls = 0, nodatavalmatch = 0;

    dfCellMin = TYPE_FLOAT64_MAX;
    dfCellMax = TYPE_FLOAT64_MIN;

    /* Better use selected GDAL datatype instead of 
     * the best match with GRASS raster map types ? */

    if (maptype == FCELL_TYPE) {

	/* Source datatype understandable by GDAL */
	GDALDataType datatype = GDT_Float32;
	FCELL fnullval = (FCELL) nodataval;

	G_debug(1, "FCELL nodata val: %f", fnullval);

	for (row = 0; row < rows; row++) {

	    if (G_get_raster_row(fd, bufer, row, maptype) < 0) {
		G_warning(_("Unable to read raster map <%s> row %d"),
			  name, row);
		return -1;
	    }
	    G_get_null_value_row(fd, nulls, row);
	    for (col = 0; col < cols; col++)
		if (nulls[col]) {
		    ((FCELL *) bufer)[col] = fnullval;
		    if (n_nulls == 0) {
			GDALSetRasterNoDataValue(hBand, nodataval);
		    }
		    n_nulls++;
		}
		else {
		    if (((FCELL *) bufer)[col] == fnullval) {
			nodatavalmatch = 1;
		    }
		    if (dfCellMin > ((FCELL *) bufer)[col])
			dfCellMin = ((FCELL *) bufer)[col];
		    if (dfCellMax < ((FCELL *) bufer)[col])
			dfCellMax = ((FCELL *) bufer)[col];
		}

	    if (GDALRasterIO
		(hBand, GF_Write, 0, row, cols, 1, bufer, cols, 1, datatype,
		 0, 0) >= CE_Failure) {
		G_warning(_("Unable to write GDAL raster file"));
		return -1;
	    }
	    G_percent(row + 1, rows, 2);
	}
    }
    else if (maptype == DCELL_TYPE) {

	GDALDataType datatype = GDT_Float64;
	DCELL dnullval = (DCELL) nodataval;

	G_debug(1, "DCELL nodata val: %f", dnullval);

	for (row = 0; row < rows; row++) {

	    if (G_get_raster_row(fd, bufer, row, maptype) < 0) {
		G_warning(_("Unable to read raster map <%s> row %d"),
			  name, row);
		return -1;
	    }
	    G_get_null_value_row(fd, nulls, row);
	    for (col = 0; col < cols; col++)
		if (nulls[col]) {
		    ((DCELL *) bufer)[col] = dnullval;
		    if (n_nulls == 0) {
			GDALSetRasterNoDataValue(hBand, nodataval);
		    }
		    n_nulls++;
		}
		else {
		    if (((DCELL *) bufer)[col] == dnullval) {
			nodatavalmatch = 1;
		    }
		    if (dfCellMin > ((DCELL *) bufer)[col])
			dfCellMin = ((DCELL *) bufer)[col];
		    if (dfCellMax < ((DCELL *) bufer)[col])
			dfCellMax = ((DCELL *) bufer)[col];
		}

	    if (GDALRasterIO
		(hBand, GF_Write, 0, row, cols, 1, bufer, cols, 1, datatype,
		 0, 0) >= CE_Failure) {
		G_warning(_("Unable to write GDAL raster file"));
		return -1;
	    }
	    G_percent(row + 1, rows, 2);
	}
    }
    else {

	GDALDataType datatype = GDT_Int32;
	CELL inullval = (CELL) nodataval;

	G_debug(1, "CELL nodata val: %d", inullval);

	for (row = 0; row < rows; row++) {

	    if (G_get_raster_row(fd, bufer, row, maptype) < 0) {
		G_warning(_("Unable to read raster map <%s> row %d"),
			  name, row);
		return -1;
	    }
	    G_get_null_value_row(fd, nulls, row);
	    for (col = 0; col < cols; col++)
		if (nulls[col]) {
		    ((CELL *) bufer)[col] = inullval;
		    if (n_nulls == 0) {
			GDALSetRasterNoDataValue(hBand, nodataval);
		    }
		    n_nulls++;
		}
		else {
		    if (((CELL *) bufer)[col] == inullval) {
			nodatavalmatch = 1;
		    }
		    if (dfCellMin > ((CELL *) bufer)[col])
			dfCellMin = ((CELL *) bufer)[col];
		    if (dfCellMax < ((CELL *) bufer)[col])
			dfCellMax = ((CELL *) bufer)[col];
		}

	    if (GDALRasterIO
		(hBand, GF_Write, 0, row, cols, 1, bufer, cols, 1, datatype,
		 0, 0) >= CE_Failure) {
		G_warning(_("Unable to write GDAL raster file"));
		return -1;
	    }
	    G_percent(row + 1, rows, 2);
	}
    }

    /* can the GDAL datatype hold the data range to be exported ? */
    /* f-flag does not override */
    if (exact_range_check(export_datatype, dfCellMin, dfCellMax, name)) {
	G_warning("Raster export results in data loss.");
	ret = -3;
    }

    /* a default nodata value was used and NULL cells were present */
    if (n_nulls && default_nodataval) {
	if (maptype == CELL_TYPE)
	    G_important_message(_("Input raster map contains cells with NULL-value (no-data). "
				 "The value %d was used to represent no-data values in the input map. "
				 "You can specify a nodata value with the %s option."),
				(int)nodataval, nodatakey);
	else
	    G_important_message(_("Input raster map contains cells with NULL-value (no-data). "
				 "The value %f was used to represent no-data values in the input map. "
				 "You can specify a nodata value with the %s option."),
				nodataval, nodatakey);
    }

    /* the nodata value was present in the exported data */
    if (nodatavalmatch && n_nulls) {
	/* default nodataval didn't work */
	if (default_nodataval) {
	    G_warning(_("The default nodata value is present in raster"
			"band <%s> and would lead to data loss. Please specify a "
			"custom nodata value with the %s parameter."),
		      name, nodatakey);
	}
	/* user-specified nodataval didn't work */
	else {
	    G_warning(_("The given nodata value is present in raster"
			"band <%s> and would lead to data loss. Please specify a "
			"different nodata value with the %s parameter."),
		      name, nodatakey);
	}
	ret = -2;
    }

    return ret;
}

int exact_range_check(double min, double max, GDALDataType datatype,
		      const char *name)
{

    switch (datatype) {
    case GDT_Byte:
	if (min < TYPE_BYTE_MIN || max > TYPE_BYTE_MAX) {
	    G_warning(_("Selected GDAL datatype does not cover data range."));
	    G_warning(_("GDAL datatype: %s, range: %d - %d"),
		      GDALGetDataTypeName(datatype), TYPE_BYTE_MIN,
		      TYPE_BYTE_MAX);
	    G_warning(_("Raster map <%s> range: %f - %f"), name, min, max);
	    return 1;
	}
	else
	    return 0;

    case GDT_UInt16:
	if (min < TYPE_UINT16_MIN || max > TYPE_UINT16_MAX) {
	    G_warning(_("Selected GDAL datatype does not cover data range."));
	    G_warning(_("GDAL datatype: %s, range: %d - %d"),
		      GDALGetDataTypeName(datatype), TYPE_UINT16_MIN,
		      TYPE_UINT16_MAX);
	    G_warning(_("Raster map <%s> range: %f - %f"), name, min, max);
	    return 1;
	}
	else
	    return 0;

    case GDT_Int16:
    case GDT_CInt16:
	if (min < TYPE_INT16_MIN || max > TYPE_INT16_MAX) {
	    G_warning(_("Selected GDAL datatype does not cover data range."));
	    G_warning(_("GDAL datatype: %s, range: %d - %d"),
		      GDALGetDataTypeName(datatype), TYPE_INT16_MIN,
		      TYPE_INT16_MAX);
	    G_warning(_("Raster map <%s> range: %f - %f"), name, min, max);
	    return 1;
	}
	else
	    return 0;

    case GDT_Int32:
    case GDT_CInt32:
	if (min < TYPE_INT32_MIN || max > TYPE_INT32_MAX) {
	    G_warning(_("Selected GDAL datatype does not cover data range."));
	    G_warning(_("GDAL datatype: %s, range: %d - %d"),
		      GDALGetDataTypeName(datatype), TYPE_INT32_MIN,
		      TYPE_INT32_MAX);
	    G_warning(_("Raster map <%s> range: %f - %f"), name, min, max);
	    return 1;
	}
	else
	    return 0;

    case GDT_UInt32:
	if (min < TYPE_UINT32_MIN || max > TYPE_UINT32_MAX) {
	    G_warning(_("Selected GDAL datatype does not cover data range."));
	    G_warning(_("GDAL datatype: %s, range: %u - %u"),
		      GDALGetDataTypeName(datatype), TYPE_UINT32_MIN,
		      TYPE_UINT32_MAX);
	    G_warning(_("Raster map <%s> range: %f - %f"), name, min, max);
	    return 1;
	}
	else
	    return 0;

    case GDT_Float32:
    case GDT_CFloat32:
	if (min < TYPE_FLOAT32_MIN || max > TYPE_FLOAT32_MAX) {
	    G_warning(_("Selected GDAL datatype does not cover data range."));
	    G_warning(_("GDAL datatype: %s, range: %f - %f"),
		      GDALGetDataTypeName(datatype), TYPE_FLOAT32_MIN,
		      TYPE_FLOAT32_MAX);
	    G_warning(_("Raster map <%s> range: %f - %f"), name, min, max);
	    return 1;
	}
	else
	    return 0;

    case GDT_Float64:
    case GDT_CFloat64:
	/* not possible because DCELL is FLOAT64, not 128bit floating point, but anyway... */
	if (min < TYPE_FLOAT64_MIN || max > TYPE_FLOAT64_MAX) {
	    G_warning(_("Selected GDAL datatype does not cover data range."));
	    G_warning(_("GDAL datatype: %s, range: %f - %f"),
		      GDALGetDataTypeName(datatype), TYPE_FLOAT64_MIN,
		      TYPE_FLOAT64_MAX);
	    G_warning(_("Raster map <%s> range: %f - %f"), name, min, max);
	    return 1;
	}
	else
	    return 0;

    default:
	return 0;
    }
}
