
/****************************************************************************
 *
 * MODULE:       i.albedo
 * AUTHOR(S):    Yann Chemin - yann.chemin@gmail.com
 * PURPOSE:      Calculate Broadband Albedo (0.3-3 Micrometers)
 *               from Surface Reflectance (Modis, AVHRR, Landsat, Aster).
 *
 * COPYRIGHT:    (C) 2004-2008 by the GRASS Development Team
 *
 *               This program is free software under the GNU Lesser General Public
 *   	    	 License. Read the file COPYING that comes with GRASS for details.
 *
 *****************************************************************************/


#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <grass/gis.h>
#include <grass/glocale.h>

#define MAXFILES 8

double bb_alb_aster(double greenchan, double nirchan, double swirchan2,
		    double swirchan3, double swirchan5, double swirchan6);
double bb_alb_landsat(double bluechan, double greenchan, double redchan,
		      double nirchan, double chan5, double chan7);
double bb_alb_noaa(double redchan, double nirchan);

double bb_alb_modis(double redchan, double nirchan, double chan3,
		    double chan4, double chan5, double chan6, double chan7);

int main(int argc, char *argv[])
{
    struct Cell_head cellhd;	/*region+header info */

    char *mapset;		/*mapset name */

    int nrows, ncols;

    int row, col;

    struct GModule *module;

    struct Option *input, *output;

    struct Flag *flag1, *flag2, *flag3;

    struct Flag *flag4, *flag5, *flag6;

    struct History history;	/*metadata */

    struct Colors colors;	/*Color rules */

	/************************************/
    /* FMEO Declarations**************** */
    char *name;			/*input raster name */

    char *result;		/*output raster name */

    /*File Descriptors */
    int nfiles;

    int infd[MAXFILES];

    int outfd;

    char **names;

    char **ptr;

    int ok;

    int i = 0, j = 0;

    int modis = 0, aster = 0, avhrr = 0, landsat = 0;

    void *inrast[MAXFILES];

    unsigned char *outrast;

    int data_format;		/* 0=double  1=float  2=32bit signed int  5=8bit unsigned int (ie text) */

    RASTER_MAP_TYPE in_data_type[MAXFILES];	/* 0=numbers  1=text */

    RASTER_MAP_TYPE out_data_type = DCELL_TYPE;

	/************************************/

	/************************************/
    int histogram[100];

    /* Albedo correction coefficients*** */
    double a, b;

	/************************************/

    G_gisinit(argv[0]);

    module = G_define_module();
    module->keywords = _("Albedo,surface reflectance,r.sun");
    module->description =
	_("Broad Band Albedo from Surface Reflectance.\n NOAA AVHRR(n), Modis(m), Landsat(l), Aster(a)\n");

    /* Define the different options */

    input = G_define_standard_option(G_OPT_R_INPUT);
    input->multiple = YES;
    input->description = _("Names of surface reflectance layers");

    output = G_define_standard_option(G_OPT_R_OUTPUT);
    output->description = _("Name of the BB_Albedo layer");

    /* Define the different flags */

    flag1 = G_define_flag();
    flag1->key = _('m');
    flag1->description = _("Modis (7 input bands:1,2,3,4,5,6,7)");

    flag2 = G_define_flag();
    flag2->key = _('n');
    flag2->description = _("NOAA AVHRR (2 input bands:1,2)");

    flag3 = G_define_flag();
    flag3->key = _('l');
    flag3->description = _("Landsat (6 input bands:1,2,3,4,5,7)");

    flag4 = G_define_flag();
    flag4->key = _('a');
    flag4->description = _("Aster (6 input bands:1,3,5,6,8,9)");

    flag5 = G_define_flag();
    flag5->key = _('c');
    flag5->description =
	_("Albedo dry run to calculate some water to beach/sand/desert stretching, a kind of simple atmospheric correction. Agressive mode (Landsat).");

    flag6 = G_define_flag();
    flag6->key = _('d');
    flag6->description =
	_("Albedo dry run to calculate some water to beach/sand/desert stretching, a kind of simple atmospheric correction. Soft mode (Modis).");

    /* FMEO init nfiles */
    nfiles = 1;

	/********************/
    if (G_parser(argc, argv))
	exit(-1);

    ok = 1;
    names = input->answers;
    ptr = input->answers;

    result = output->answer;

    modis = (flag1->answer);
    avhrr = (flag2->answer);
    landsat = (flag3->answer);
    aster = (flag4->answer);

	/***************************************************/
    if (G_legal_filename(result) < 0) {
	G_fatal_error(_("[%s] is an illegal name"), result);
    }

	/***************************************************/

	/***************************************************/
    for (; *ptr != NULL; ptr++) {
	if (nfiles >= MAXFILES)
	    G_fatal_error(_("%s - too many ETa files. Only %d allowed"),
			  G_program_name(), MAXFILES);
	name = *ptr;
	/* find map in mapset */
	mapset = G_find_cell2(name, "");
	if (mapset == NULL) {
	    G_fatal_error(_("cell file [%s] not found"), name);
	    ok = 0;
	}
	if (!ok) {
	    continue;
	}
	infd[nfiles] = G_open_cell_old(name, mapset);
	if (infd[nfiles] < 0) {
	    ok = 0;
	    continue;
	}
	/* Allocate input buffer */
	in_data_type[nfiles] = G_raster_map_type(name, mapset);
	if ((infd[nfiles] = G_open_cell_old(name, mapset)) < 0) {
	    G_fatal_error(_("Cannot open cell file [%s]"), name);
	}
	if ((G_get_cellhd(name, mapset, &cellhd)) < 0) {
	    G_fatal_error(_("Cannot read file header of [%s]"), name);
	}
	inrast[nfiles] = G_allocate_raster_buf(in_data_type[nfiles]);
	nfiles++;
    }
    nfiles--;
    if (nfiles <= 1) {
	G_fatal_error(_("The min specified input map is two (that is NOAA AVHRR)"));
    }

	/***************************************************/
    /* Allocate output buffer, use input map data_type */
    nrows = G_window_rows();
    ncols = G_window_cols();
    outrast = G_allocate_raster_buf(out_data_type);

    /* Create New raster files */
    if ((outfd = G_open_raster_new(result, 1)) < 0) {
	G_fatal_error(_("Could not open <%s>"), result);
    }
    /*START ALBEDO HISTOGRAM STRETCH */
    /*This is correcting contrast for water/sand */
    /*A poor man's atmospheric correction... */
    for (i = 0; i < 100; i++) {
	histogram[i] = 0;
    }
    if (flag5->answer || flag6->answer) {
	DCELL de;

	DCELL d[MAXFILES];

		/****************************/
	/* Process pixels histogram */
	for (row = 0; row < nrows; row++) {
	    G_percent(row, nrows, 2);
	    /* read input map */
	    for (i = 1; i <= nfiles; i++) {
		if ((G_get_raster_row
		     (infd[i], inrast[i], row, in_data_type[i])) < 0) {
		    G_fatal_error(_("Could not read from <%s>"), name);
		}
	    }
	    /*process the data */
	    for (col = 0; col < ncols; col++) {
		for (i = 1; i <= nfiles; i++) {
		    switch (in_data_type[i]) {
		    case CELL_TYPE:
			d[i] = (double)((CELL *) inrast[i])[col];
			break;
		    case FCELL_TYPE:
			d[i] = (double)((FCELL *) inrast[i])[col];
			break;
		    case DCELL_TYPE:
			d[i] = (double)((DCELL *) inrast[i])[col];
			break;
		    }
		}
		if (modis) {
		    de = bb_alb_modis(d[1], d[2], d[3], d[4], d[5], d[6],
				      d[7]);
		}
		else if (avhrr) {
		    de = bb_alb_noaa(d[1], d[2]);
		}
		else if (landsat) {
		    de = bb_alb_landsat(d[1], d[2], d[3], d[4], d[5], d[6]);
		}
		else if (aster) {
		    de = bb_alb_aster(d[1], d[2], d[3], d[4], d[5], d[6]);
		}
		if (G_is_d_null_value(&de)) {
		    /*Do nothing */
		}
		else {
		    int temp;

		    temp = (int)(de * 100);
		    if (temp > 0) {
			histogram[temp] = histogram[temp] + 1.0;
		    }
		}
	    }
	}
	G_message("Histogram of Albedo\n");
	int peak1, peak2, peak3;

	int i_peak1, i_peak2, i_peak3;

	peak1 = 0;
	peak2 = 0;
	peak3 = 0;
	i_peak1 = 0;
	i_peak2 = 0;
	i_peak3 = 0;
	for (i = 0; i < 100; i++) {
	    /*Search for peaks of datasets (1) */
	    if (i <= 10) {
		if (histogram[i] > peak1) {
		    peak1 = histogram[i];
		    i_peak1 = i;
		}
	    }
	    /*Search for peaks of datasets (2) */
	    if (i >= 10 && i <= 30) {
		if (histogram[i] > peak2) {
		    peak2 = histogram[i];
		    i_peak2 = i;
		}
	    }
	    /*Search for peaks of datasets (3) */
	    if (i >= 30) {
		if (histogram[i] > peak3) {
		    peak3 = histogram[i];
		    i_peak3 = i;
		}
	    }
	}
	int bottom1a, bottom1b;

	int bottom2a, bottom2b;

	int bottom3a, bottom3b;

	int i_bottom1a, i_bottom1b;

	int i_bottom2a, i_bottom2b;

	int i_bottom3a, i_bottom3b;

	bottom1a = 100000;
	bottom1b = 100000;
	bottom2a = 100000;
	bottom2b = 100000;
	bottom3a = 100000;
	bottom3b = 100000;
	i_bottom1a = 100;
	i_bottom1b = 100;
	i_bottom2a = 100;
	i_bottom2b = 100;
	i_bottom3a = 100;
	i_bottom3b = 100;
	/* Water histogram lower bound */
	for (i = 0; i < i_peak1; i++) {
	    if (histogram[i] <= bottom1a) {
		bottom1a = histogram[i];
		i_bottom1a = i;
	    }
	}
	/* Water histogram higher bound */
	for (i = i_peak2; i > i_peak1; i--) {
	    if (histogram[i] <= bottom1b) {
		bottom1b = histogram[i];
		i_bottom1b = i;
	    }
	}
	/* Land histogram lower bound */
	for (i = i_peak1; i < i_peak2; i++) {
	    if (histogram[i] <= bottom2a) {
		bottom2a = histogram[i];
		i_bottom2a = i;
	    }
	}
	/* Land histogram higher bound */
	for (i = i_peak3; i > i_peak2; i--) {
	    if (histogram[i] < bottom2b) {
		bottom2b = histogram[i];
		i_bottom2b = i;
	    }
	}
	/* Cloud/Snow histogram lower bound */
	for (i = i_peak2; i < i_peak3; i++) {
	    if (histogram[i] < bottom3a) {
		bottom3a = histogram[i];
		i_bottom3a = i;
	    }
	}
	/* Cloud/Snow histogram higher bound */
	for (i = 100; i > i_peak3; i--) {
	    if (histogram[i] < bottom3b) {
		bottom3b = histogram[i];
		i_bottom3b = i;
	    }
	}
	if (flag5->answer) {
	    G_message("peak1 %d %d\n", peak1, i_peak1);
	    G_message("bottom2b= %d %d\n", bottom2b, i_bottom2b);
	    a = (0.36 - 0.05) / (i_bottom2b / 100.0 - i_peak1 / 100.0);
	    b = 0.05 - a * (i_peak1 / 100.0);
	    G_message("a= %f\tb= %f\n", a, b);
	}
	if (flag6->answer) {
	    G_message("bottom1a %d %d\n", bottom1a, i_bottom1a);
	    G_message("bottom2b= %d %d\n", bottom2b, i_bottom2b);
	    a = (0.36 - 0.05) / (i_bottom2b / 100.0 - i_bottom1a / 100.0);
	    b = 0.05 - a * (i_bottom1a / 100.0);
	    G_message("a= %f\tb= %f\n", a, b);
	}
    }				/*END OF FLAG1 */
    /* End of processing histogram */

	/*******************/
    /* Process pixels */
    for (row = 0; row < nrows; row++) {
	DCELL de;

	DCELL d[MAXFILES];

	G_percent(row, nrows, 2);
	/* read input map */
	for (i = 1; i <= nfiles; i++) {
	    if ((G_get_raster_row(infd[i], inrast[i], row, in_data_type[i])) <
		0) {
		G_fatal_error(_("Could not read from <%s>"), name);
	    }
	}
	/*process the data */
	for (col = 0; col < ncols; col++) {
	    for (i = 1; i <= nfiles; i++) {
		switch (in_data_type[i]) {
		case CELL_TYPE:
		    d[i] = (double)((CELL *) inrast[i])[col];
		    break;
		case FCELL_TYPE:
		    d[i] = (double)((FCELL *) inrast[i])[col];
		    break;
		case DCELL_TYPE:
		    d[i] = (double)((DCELL *) inrast[i])[col];
		    break;
		}
	    }
	    if (modis) {
		de = bb_alb_modis(d[1], d[2], d[3], d[4], d[5], d[6], d[7]);
	    }
	    else if (avhrr) {
		de = bb_alb_noaa(d[1], d[2]);
	    }
	    else if (landsat) {
		de = bb_alb_landsat(d[1], d[2], d[3], d[4], d[5], d[6]);
	    }
	    else if (aster) {
		de = bb_alb_aster(d[1], d[2], d[3], d[4], d[5], d[6]);
	    }
	    if (flag5->answer || flag6->answer) {
		/* Post-Process Albedo */
		de = a * de + b;
	    }
	    ((DCELL *) outrast)[col] = de;
	}
	if (G_put_raster_row(outfd, outrast, out_data_type) < 0)
	    G_fatal_error(_("Cannot write to <%s>"), result);
    }
    for (i = 1; i <= nfiles; i++) {
	G_free(inrast[i]);
	G_close_cell(infd[i]);
    }
    G_free(outrast);
    G_close_cell(outfd);

    /* Color table from 0.0 to 1.0 */
    G_init_colors(&colors);
    G_add_color_rule(0.0, 0, 0, 0, 1.0, 255, 255, 255, &colors);
    /* Metadata */
    G_short_history(result, "raster", &history);
    G_command_history(&history);
    G_write_history(result, &history);

    exit(EXIT_SUCCESS);
}
