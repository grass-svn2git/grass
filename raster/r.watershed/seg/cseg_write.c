#include <grass/gis.h>
#include <grass/raster.h>
#include <grass/segment.h>
#include "cseg.h"

static char *me = "cseg_write_cell";

int cseg_write_cellfile(CSEG * cseg, char *map_name)
{
    int map_fd;
    int row, nrows;
    CELL *buffer;

    map_fd = Rast_open_c_new(map_name);
    nrows = G_window_rows();
    buffer = Rast_allocate_c_buf();
    segment_flush(&(cseg->seg));
    for (row = 0; row < nrows; row++) {
	G_percent(row, nrows, 1);
	segment_get_row(&(cseg->seg), buffer, row);
	if (Rast_put_row(map_fd, buffer, CELL_TYPE) < 0) {
	    G_free(buffer);
	    Rast_unopen(map_fd);
	    G_warning("%s(): unable to write new map layer [%s], row %d",
		      me, map_name, row);
	    return -2;
	}
    }
    G_percent(row, nrows, 1);    /* finish it */
    G_free(buffer);
    Rast_close(map_fd);
    return 0;
}
