
/****************************************************************************
 *
 * MODULE:       r.in.poly
 * AUTHOR(S):    Michael Shapiro, CERL (original contributor)
 * PURPOSE:      creates GRASS binary raster maps from ASCII files
 * COPYRIGHT:    (C) 1999-2006 by the GRASS Development Team
 *
 *               This program is free software under the GNU General Public
 *               License (>=v2). Read the file COPYING that comes with GRASS
 *               for details.
 *
 *****************************************************************************/
#include <stdlib.h>
#include <grass/gis.h>
#include <grass/glocale.h>
#include "local_proto.h"


int main(int argc, char *argv[])
{
    struct GModule *module;
    struct Option *input, *output, *title, *rows;
    int n;

    G_gisinit(argv[0]);

    module = G_define_module();
    module->keywords = _("raster, import");
    module->description =
	_("Creates raster maps from ASCII polygon/line/point data files.");


    input = G_define_standard_option(G_OPT_F_INPUT);

    output = G_define_standard_option(G_OPT_R_OUTPUT);

    title = G_define_option();
    title->key = "title";
    title->key_desc = "phrase";
    title->type = TYPE_STRING;
    title->required = NO;
    title->description = _("Title for resultant raster map");

    rows = G_define_option();
    rows->key = "rows";
    rows->type = TYPE_INTEGER;
    rows->required = NO;
    rows->description = _("Number of rows to hold in memory");
    rows->answer = "4096";

    if (G_parser(argc, argv))
	exit(EXIT_FAILURE);


    sscanf(rows->answer, "%d", &n);
    if (n < 1)
	G_fatal_error(_("Minimum number of rows to hold in memory is 1"));

    /* otherwise get complaints about window changes */
    G_suppress_warnings(1);

    exit(poly_to_rast(input->answer, output->answer, title->answer, n));
}
