#include <stdlib.h>
#include <grass/raster.h>
#include <grass/glocale.h>
#include "local_proto.h"


void rdwr_gridatb(void)
{
    FILE *fp;
    int fd, row, col;
    int adjcellhdval;
    CELL *cell;
    DCELL *dcell;
    FCELL *fcell;
    RASTER_MAP_TYPE data_type;

    fd = Rast_open_cell_old(iname, "");
    if (fd < 0)
	G_fatal_error("%s - could not read", iname);

    data_type = Rast_get_raster_map_type(fd);
    switch (data_type) {
    case CELL_TYPE:
	cell = Rast_allocate_c_raster_buf();
	break;
    case FCELL_TYPE:
	fcell = Rast_allocate_f_raster_buf();
	break;
    case DCELL_TYPE:
	dcell = Rast_allocate_d_raster_buf();
	break;
    }

    Rast_get_cellhd(iname, "", &cellhd);

    adjcellhdval = adjcellhd(&cellhd);
    switch (adjcellhdval) {
    case 1:
	G_fatal_error(_("Setting window header"));
	break;
    case 2:
	G_fatal_error(_("Rows changed"));
	break;
    case 3:
	G_fatal_error(_("Cols changed"));
	break;
    }

    fp = fopen(file, "w");

    fprintf(fp, "%s\n", Rast_get_cell_title(iname, ""));
    fprintf(fp, "%d %d %lf\n", cellhd.cols, cellhd.rows, cellhd.ns_res);

    for (row = 0; row < cellhd.rows; row++) {
	G_percent(row, cellhd.rows, 2);
	switch (data_type) {
	case CELL_TYPE:
	    if (Rast_get_c_raster_row(fd, cell, row) < 0) {
		Rast_close_cell(fd);
		exit(1);
	    }

	    for (col = 0; col < cellhd.cols; col++) {
		if (Rast_is_c_null_value(&cell[col]))
		    fprintf(fp, "  9999.00 ");
		else
		    fprintf(fp, "%9.2f ", (float)cell[col]);
		if (!((col + 1) % 8) || col == cellhd.cols - 1)
		    fprintf(fp, "\n");
	    }
	    break;
	case FCELL_TYPE:
	    if (Rast_get_f_raster_row(fd, fcell, row) < 0) {
		Rast_close_cell(fd);
		exit(1);
	    }

	    for (col = 0; col < cellhd.cols; col++) {
		if (Rast_is_f_null_value(&fcell[col]))
		    fprintf(fp, "  9999.00 ");
		else
		    fprintf(fp, "%9.2f ", (float)fcell[col]);
		if (!((col + 1) % 8) || col == cellhd.cols - 1)
		    fprintf(fp, "\n");
	    }
	    break;
	case DCELL_TYPE:
	    if (Rast_get_d_raster_row(fd, dcell, row) < 0) {
		Rast_close_cell(fd);
		exit(1);
	    }

	    for (col = 0; col < cellhd.cols; col++) {
		if (Rast_is_d_null_value(&dcell[col]))
		    fprintf(fp, "  9999.00 ");
		else
		    fprintf(fp, "%9.2lf ", (double)dcell[col]);
		if (!((col + 1) % 8) || col == cellhd.cols - 1)
		    fprintf(fp, "\n");
	    }
	    break;
	}
    }
    Rast_close_cell(fd);

    return;
}
