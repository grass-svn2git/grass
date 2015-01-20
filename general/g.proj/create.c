#include <errno.h>
#include <string.h>

#include <grass/gis.h>
#include <grass/glocale.h>

#include "local_proto.h"

void create_location(const char *location, const char *epsg)
{
    int ret;

    ret = G_make_location(location, &cellhd, projinfo, projunits);
    if (ret == 0)
	G_message(_("Location <%s> created"), location);
    else if (ret == -1)
	G_fatal_error(_("Unable to create location <%s>: %s"),
                      location, strerror(errno));
    else if (ret == -2)
        G_fatal_error(_("Unable to create projection files: %s"),
		    strerror(errno));
    else
	/* Shouldn't happen */
      G_fatal_error(_("Unable to create location <%s>"), location);

    /* create also PROJ_EPSG */
    if (epsg)
        create_epsg(location, epsg);
        
    G_message(_("You can switch to the new location by\n`%s=%s`"),
	      "g.mapset mapset=PERMANENT location", location);
}

void modify_projinfo()
{
    const char *mapset = G_mapset();
    struct Cell_head old_cellhd;
    
    if (strcmp(mapset, "PERMANENT") != 0)
	G_fatal_error(_("You must select the PERMANENT mapset before updating the "
			"current location's projection (current mapset is <%s>)"),
		      mapset);
    
    /* Read projection information from current location first */
    G_get_default_window(&old_cellhd);
    
    char path[GPATH_MAX];
	
    /* Write out the PROJ_INFO, and PROJ_UNITS if available. */
    if (projinfo != NULL) {
	G_file_name(path, "", "PROJ_INFO", "PERMANENT");
	G_write_key_value_file(path, projinfo);
    }
    
    if (projunits != NULL) {
	G_file_name(path, "", "PROJ_UNITS", "PERMANENT");
	G_write_key_value_file(path, projunits);
    }
    
    if ((old_cellhd.zone != cellhd.zone) ||
	(old_cellhd.proj != cellhd.proj)) {
	/* Recreate the default, and current window files if projection
	 * number or zone have changed */
	G_put_element_window(&cellhd, "", "DEFAULT_WIND");
	G_put_element_window(&cellhd, "", "WIND");
	G_message(_("Default region was updated to the new projection, but if you have "
		    "multiple mapsets `g.region -d` should be run in each to update the "
		    "region from the default"));
    }
    G_important_message(_("Projection information updated"));
}

void create_epsg(const char *location, const char *epsg)
{
    FILE *fp;
    char path[GPATH_MAX];
    
    /* if inputs were not clean it should of failed by now */
    if (location) {
        snprintf(path, sizeof(path), "%s%c%s%c%s%c%s", G_gisdbase(), HOST_DIRSEP, 
                 location, HOST_DIRSEP,
                 "PERMANENT", HOST_DIRSEP, "PROJ_EPSG");
        path[sizeof(path)-1] = '\0';
    }
    else {
        G_file_name(path, "", "PROJ_EPSG", "PERMANENT");
    }
    
    fp = fopen(path, "w");
    if (!fp)
        G_fatal_error(_("Unable to create PROJ_EPSG file: %s"), strerror (errno));
    
#ifdef HAVE_OGR
    fprintf(fp, "epsg: %s\n", epsg);
#endif
    fclose(fp);
}
