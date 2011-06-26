
/****************************************************************************
 *
 * MODULE:       r.colors
 *
 * AUTHOR(S):    Michael Shapiro - CERL
 *               David Johnson
 *
 * PURPOSE:      Allows creation and/or modification of the color table
 *               for a raster map layer.
 *
 * COPYRIGHT:    (C) 2006 by the GRASS Development Team
 *
 *               This program is free software under the GNU General Public
 *               License (>=v2). Read the file COPYING that comes with GRASS
 *               for details.
 *
 ***************************************************************************/

#ifndef __LOCAL_PROTO_H__
#define __LOCAL_PROTO_H__

#include <grass/gis.h>
#include <grass/raster.h>
#include <grass/glocale.h>
#include <grass/G3d.h>

#define RASTER_TYPE   1
#define RASTER3D_TYPE 2

/* stats.c */
int get_stats(const char *, const char *, struct Cell_stats *);
void get_fp_stats(const char *name, const char *mapset,
		  struct FP_stats *statf,
		  DCELL min, DCELL max, int geometric, int geom_abs, int);

/* edit_colors.c */
int edit_colors(int, char **, int, const char *, const char*);

/* rules.c */
int read_color_rules(FILE *, struct Colors *, DCELL, DCELL, int);

#endif /* __LOCAL_PROTO_H__ */
