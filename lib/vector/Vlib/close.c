/*!
   \file lib/vector/Vlib/close.c

   \brief Vector library - Close vector map

   Higher level functions for reading/writing/manipulating vectors.

   (C) 2001-2009, 2011 by the GRASS Development Team

   This program is free software under the GNU General Public License
   (>=v2). Read the file COPYING that comes with GRASS for details.

   \author Original author CERL, probably Dave Gerdes or Mike Higgins.
   \author Update to GRASS 5.7 Radim Blazek and David D. Gray.
   \author Update to GRASS 7 Martin Landa <landa.martin gmail.com>
 */

#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <unistd.h>
#include <grass/vector.h>
#include <grass/glocale.h>

static int clo_dummy()
{
    return -1;
}

#if !defined HAVE_OGR || !defined HAVE_POSTGRES
static int format()
{
    G_fatal_error(_("Requested format is not compiled in this version"));
    return 0;
}
#endif

static int (*Close_array[][2]) () = {
    {
    clo_dummy, V1_close_nat}
#ifdef HAVE_OGR
    , {
    clo_dummy, V1_close_ogr}
    , {
    clo_dummy, V1_close_ogr}
#else
    , {
    clo_dummy, format}
    , {
    clo_dummy, format}
#endif
#ifdef HAVE_POSTGRES
    , {
    clo_dummy, V1_close_pg}
#else
    , {
    clo_dummy, format}
#endif
};

/*!
   \brief Close vector map

   \param Map pointer to Map_info

   \return 0 on success
   \return non-zero on error
 */
int Vect_close(struct Map_info *Map)
{
    struct Coor_info CInfo;

    G_debug(1, "Vect_close(): name = %s, mapset = %s, format = %d, level = %d",
	    Map->name, Map->mapset, Map->format, Map->level);

    /* Store support files for vector maps in the current mapsset if
       in write mode on level 2 */
    if (strcmp(Map->mapset, G_mapset()) == 0 &&
	Map->support_updated &&
	Map->plus.built == GV_BUILD_ALL) {
	char buf[GPATH_MAX];
	char file_path[GPATH_MAX];

	/* Delete old support files if available */
	sprintf(buf, "%s/%s", GV_DIRECTORY, Map->name);

	G_file_name(file_path, buf, GV_TOPO_ELEMENT, G_mapset());
	if (access(file_path, F_OK) == 0)	/* file exists? */
	    unlink(file_path);

	G_file_name(file_path, buf, GV_SIDX_ELEMENT, G_mapset());
	if (access(file_path, F_OK) == 0)	/* file exists? */
	    unlink(file_path);

	G_file_name(file_path, buf, GV_CIDX_ELEMENT, G_mapset());
	if (access(file_path, F_OK) == 0)	/* file exists? */
	    unlink(file_path);

	if (Map->format == GV_FORMAT_OGR ||
	    Map->format == GV_FORMAT_POSTGIS) {
	    G_file_name(file_path, buf, GV_FIDX_ELEMENT, G_mapset());
	    if (access(file_path, F_OK) == 0)	/* file exists? */
		unlink(file_path);
	}
	
	Vect_coor_info(Map, &CInfo);
	Map->plus.coor_size = CInfo.size;
	Map->plus.coor_mtime = CInfo.mtime;

	/* write out topo file */
	Vect_save_topo(Map);

	/* write out sidx file */
	Map->plus.Spidx_new = TRUE;
	Vect_save_sidx(Map);

	/* write out cidx file */
	Vect_cidx_save(Map);
	
	/* write out fidx file */
	if (Map->format == GV_FORMAT_OGR)
	    V2_close_ogr(Map);
	else if (Map->format == GV_FORMAT_POSTGIS)
	    V2_close_pg(Map);
    }
    else {
	/* spatial index must also be closed when opened with topo but
	 * not modified */
	/* NOTE: also close sidx for GV_FORMAT_OGR if not direct OGR access */
	if (Map->format != GV_FORMAT_OGR_DIRECT &&
	    Map->plus.Spidx_built == TRUE &&
	    Map->plus.built == GV_BUILD_ALL)
	    fclose(Map->plus.spidx_fp.file);
    }

    if (Map->level == 2 && Map->plus.release_support) {
	G_debug(1, "free topology");
	dig_free_plus(&(Map->plus));

	G_debug(1, "free spatial index");
	dig_spidx_free(&(Map->plus));

	G_debug(1, "free category index");
	dig_cidx_free(&(Map->plus));

    }

    if (Map->format == GV_FORMAT_NATIVE) {
	G_debug(1, "close history file");
	if (Map->hist_fp != NULL)
	    fclose(Map->hist_fp);
    }

    /* Close level 1 files / data sources if not head_only */
    if (!Map->head_only) {
	if (((*Close_array[Map->format][1]) (Map)) != 0) {
	    G_warning(_("Unable to close vector <%s>"),
		      Vect_get_full_name(Map));
	    return 1;
	}
    }

    G_free(Map->name);
    G_free(Map->mapset);
    G_free(Map->location);
    G_free(Map->gisdbase);
    
    Map->open = VECT_CLOSED_CODE;

    return 0;
}
