#include <grass/gis.h>
#include <grass/gprojects.h>
#include <grass/glocale.h>

#include <gdal.h>
#include <gdal_version.h>
#include "ogr_api.h"

/* define type of input datasource
 * as of GDAL 2.2, all functions having as argument a GDAL/OGR dataset 
 * must use the GDAL version, not the OGR version */
#if GDAL_VERSION_NUM >= 2020000
typedef GDALDatasetH ds_t;
#define ds_getlayerbyindex(ds, i)	GDALDatasetGetLayer((ds), (i))
#define ds_close(ds)			GDALClose(ds)
#else
typedef OGRDataSourceH ds_t;
#define ds_getlayerbyindex(ds, i)	OGR_DS_GetLayer((ds), (i))
#define ds_close(ds)			OGR_DS_Destroy(ds)
#endif

/* get projection info of OGR layer in GRASS format
 * return 0 on success (some non-xy SRS)
 * return 1 if no SRS available
 * return 2 if SRS available but unreadable */
int get_layer_proj(OGRLayerH Ogr_layer, struct Cell_head *cellhd,
		   struct Key_Value **proj_info, struct Key_Value **proj_units,
		   char *geom_col, int verbose)
{
    OGRSpatialReferenceH Ogr_projection;
    char *pszProj4 = NULL;

    Ogr_projection = NULL;
    *proj_info = NULL;
    *proj_units = NULL;
    G_get_window(cellhd);

    /* Fetch input layer projection in GRASS form. */
#if GDAL_VERSION_NUM >= 1110000
    if (geom_col) {
	int igeom;
        OGRGeomFieldDefnH Ogr_geomdefn;
	OGRFeatureDefnH Ogr_featuredefn;
        
        Ogr_featuredefn = OGR_L_GetLayerDefn(Ogr_layer);
        igeom = OGR_FD_GetGeomFieldIndex(Ogr_featuredefn, geom_col);
        if (igeom < 0)
            G_fatal_error(_("Geometry column <%s> not found in input layer <%s>"),
                          geom_col, OGR_L_GetName(Ogr_layer));
        Ogr_geomdefn = OGR_FD_GetGeomFieldDefn(Ogr_featuredefn, igeom);
        Ogr_projection = OGR_GFld_GetSpatialRef(Ogr_geomdefn);
    }
    else {
        Ogr_projection = OGR_L_GetSpatialRef(Ogr_layer);
    }
#else
    Ogr_projection = OGR_L_GetSpatialRef(Ogr_layer);	/* should not be freed later */
#endif

    /* verbose is used only when comparing input SRS to GRASS projection,
     * not when comparing SRS's of several input layers */
    if (GPJ_osr_to_grass(cellhd, proj_info,
			 proj_units, Ogr_projection, 0) < 0) {
	/* TODO: GPJ_osr_to_grass() does not return anything < 0
	 * check with GRASS 6 and GRASS 5 */
	G_warning(_("Unable to convert input layer projection information to "
		   "GRASS format for checking"));
	if (verbose && Ogr_projection != NULL) {
	    char *wkt = NULL;

	    if (OSRExportToPrettyWkt(Ogr_projection, &wkt, FALSE) != OGRERR_NONE) {
		G_warning(_("Can't get WKT parameter string"));
	    }
	    else if (wkt) {
		G_important_message(_("WKT definition:\n%s"), wkt);
	    }
	}

	return 2;
    }
    /* custom checks because if in doubt GPJ_osr_to_grass() returns a 
     * xy CRS */
    if (Ogr_projection == NULL) {
	if (verbose) {
	    G_important_message(_("No OGR projection available for layer <%s>"),
				OGR_L_GetName(Ogr_layer));
	}

	return 1;
    }

    if (!OSRIsProjected(Ogr_projection) && !OSRIsGeographic(Ogr_projection)) {
	G_important_message(_("OGR projection for layer <%s> does not contain a valid SRS"),
			    OGR_L_GetName(Ogr_layer));

	if (verbose) {
	    char *wkt = NULL;

	    if (OSRExportToPrettyWkt(Ogr_projection, &wkt, FALSE) != OGRERR_NONE) {
		G_important_message(_("Can't get WKT parameter string"));
	    }
	    else if (wkt) {
		G_important_message(_("WKT definition:\n%s"), wkt);
	    }
	}

	return 2;
    }

    if (OSRExportToProj4(Ogr_projection, &pszProj4) != OGRERR_NONE) {
	G_important_message(_("OGR projection for layer <%s> can not be converted to proj4"),
			    OGR_L_GetName(Ogr_layer));

	if (verbose) {
	    char *wkt = NULL;

	    if (OSRExportToPrettyWkt(Ogr_projection, &wkt, FALSE) != OGRERR_NONE) {
		G_important_message(_("Can't get WKT-style parameter string"));
	    }
	    else if (wkt) {
		G_important_message(_("WKT-style definition:\n%s"), wkt);
	    }
	}

	return 2;
    }

    return 0;
}

/* keep in sync with r.in.gdal, r.external, v.in.ogr */
void check_projection(struct Cell_head *cellhd, char *dsn, int layer, char *geom_col,
                      char *outloc, int create_only, int override,
		      int check_only)
{
    struct Cell_head loc_wind;
    struct Key_Value *proj_info = NULL, *proj_units = NULL;
    struct Key_Value *loc_proj_info = NULL, *loc_proj_units = NULL;
    char error_msg[8096];
    int proj_trouble;
    ds_t hDS;
    OGRLayerH Ogr_layer;

    /* open OGR DSN (v.external does not open the datasource itself */
    hDS = NULL;
    if (strlen(dsn) > 0) {
#if GDAL_VERSION_NUM >= 2020000
	hDS = GDALOpenEx(dsn, GDAL_OF_VECTOR, NULL, NULL, NULL);
#else
	hDS = OGROpen(dsn, FALSE, NULL);
#endif
    }
    if (hDS == NULL)
	G_fatal_error(_("Unable to open data source <%s>"), dsn);

    /* Get first layer to be imported to use for projection check */
    Ogr_layer = ds_getlayerbyindex(hDS, layer);

    /* -------------------------------------------------------------------- */
    /*      Fetch the projection in GRASS form.                             */
    /* -------------------------------------------------------------------- */
    proj_info = NULL;
    proj_units = NULL;

    /* proj_trouble:
     * 0: valid srs
     * 1: no srs, default to xy
     * 2: unreadable srs, default to xy
     */

    /* Projection only required for checking so convert non-interactively */
    proj_trouble = get_layer_proj(Ogr_layer, cellhd, &proj_info, &proj_units,
		   geom_col, 1);

    /* -------------------------------------------------------------------- */
    /*      Do we need to create a new location?                            */
    /* -------------------------------------------------------------------- */
    if (outloc != NULL) {
	/* do not create a xy location because this can mean that the
	 * real SRS has not been recognized or is missing */ 
	if (proj_trouble) {
	    G_fatal_error(_("Unable to convert input map projection to GRASS "
			    "format; cannot create new location."));
	}
	else {
            if (0 != G_make_location(outloc, cellhd,
                                     proj_info, proj_units)) {
                G_fatal_error(_("Unable to create new location <%s>"),
                              outloc);
            }
	    G_message(_("Location <%s> created"), outloc);

	    G_unset_window();	/* new location, projection, and window */
	    G_get_window(cellhd);
	}

        /* If create only, clean up and exit here */
        if (create_only) {
	    ds_close(hDS);
            exit(EXIT_SUCCESS);
        }
    }
    else {
	int err = 0;
        void (*msg_fn)(const char *, ...);

	if (check_only && override) {
	    /* can't check when over-riding check */
	    override = 0;
	}

	if (proj_trouble == 2) {
	    strcpy(error_msg, _("Unable to convert input map projection information "
		                "to GRASS format."));
            if (override) {
                msg_fn = G_warning;
	    }
            else {
                msg_fn = G_fatal_error;
		ds_close(hDS);
	    }
            msg_fn(error_msg);
            if (!override) {
                exit(EXIT_FAILURE);
	    }
	}

	/* -------------------------------------------------------------------- */
	/*      Does the projection of the current location match the           */
	/*      dataset?                                                        */
	/* -------------------------------------------------------------------- */
	G_get_default_window(&loc_wind);
	/* fetch LOCATION PROJ info */
	if (loc_wind.proj != PROJECTION_XY) {
	    loc_proj_info = G_get_projinfo();
	    loc_proj_units = G_get_projunits();
	}

	if (override) {
	    cellhd->proj = loc_wind.proj;
	    cellhd->zone = loc_wind.zone;
	    G_message(_("Over-riding projection check"));
	}
	else if (loc_wind.proj != cellhd->proj
		 || (err =
		     G_compare_projections(loc_proj_info, loc_proj_units,
					   proj_info, proj_units)) != 1) {
	    int i_value;

	    strcpy(error_msg,
		   _("Projection of dataset does not"
		     " appear to match current location.\n\n"));

	    /* TODO: output this info sorted by key: */
	    if (loc_wind.proj != cellhd->proj || err != -2) {
		/* error in proj_info */
		if (loc_proj_info != NULL) {
		    strcat(error_msg, _("Location PROJ_INFO is:\n"));
		    for (i_value = 0; i_value < loc_proj_info->nitems;
			 i_value++)
			sprintf(error_msg + strlen(error_msg), "%s: %s\n",
				loc_proj_info->key[i_value],
				loc_proj_info->value[i_value]);
		    strcat(error_msg, "\n");
		}

		if (proj_info != NULL) {
		    strcat(error_msg, _("Dataset PROJ_INFO is:\n"));
		    for (i_value = 0; i_value < proj_info->nitems; i_value++)
			sprintf(error_msg + strlen(error_msg), "%s: %s\n",
				proj_info->key[i_value],
				proj_info->value[i_value]);
		    strcat(error_msg, "\nERROR: ");
		    switch (err) {
		    case -1:
			strcat(error_msg, "proj\n");
			break;
		    case -2:
			strcat(error_msg, "units\n");
			break;
		    case -3:
			strcat(error_msg, "datum\n");
			break;
		    case -4:
			strcat(error_msg, "ellps, a, es\n");
			break;
		    case -5:
			strcat(error_msg, "zone\n");
			break;
		    case -6:
			strcat(error_msg, "south\n");
			break;
		    case -7:
			strcat(error_msg, "x_0\n");
			break;
		    case -8:
			strcat(error_msg, "y_0\n");
			break;
		    case -9:
			strcat(error_msg, "lon_0\n");
			break;
		    case -10:
			strcat(error_msg, "lat_0\n");
			break;
		    case -11:
			strcat(error_msg, "lat_1, lat2\n");
			break;
		    }
		}
		else {
		    strcat(error_msg, _("Dataset PROJ_INFO is:\n"));
		    if (cellhd->proj == PROJECTION_XY)
			sprintf(error_msg + strlen(error_msg),
				"Dataset proj = %d (unreferenced/unknown)\n",
				cellhd->proj);
		    else if (cellhd->proj == PROJECTION_LL)
			sprintf(error_msg + strlen(error_msg),
				"Dataset proj = %d (lat/long)\n",
				cellhd->proj);
		    else if (cellhd->proj == PROJECTION_UTM)
			sprintf(error_msg + strlen(error_msg),
				"Dataset proj = %d (UTM), zone = %d\n",
				cellhd->proj, cellhd->zone);
		    else
			sprintf(error_msg + strlen(error_msg),
				"Dataset proj = %d (unknown), zone = %d\n",
				cellhd->proj, cellhd->zone);
		}
	    }
	    else {
		/* error in proj_units */
		if (loc_proj_units != NULL) {
		    strcat(error_msg, "Location PROJ_UNITS is:\n");
		    for (i_value = 0; i_value < loc_proj_units->nitems;
			 i_value++)
			sprintf(error_msg + strlen(error_msg), "%s: %s\n",
				loc_proj_units->key[i_value],
				loc_proj_units->value[i_value]);
		    strcat(error_msg, "\n");
		}

		if (proj_units != NULL) {
		    strcat(error_msg, "Dataset PROJ_UNITS is:\n");
		    for (i_value = 0; i_value < proj_units->nitems; i_value++)
			sprintf(error_msg + strlen(error_msg), "%s: %s\n",
				proj_units->key[i_value],
				proj_units->value[i_value]);
		}
	    }
	    strcat(error_msg,
		   _("\nIn case of no significant differences in the projection definitions,"
		     " use the -o flag to ignore them and use"
		     " current location definition.\n"));
	    strcat(error_msg,
		   _("Consider generating a new location from the input dataset using "
		    "the 'location' parameter.\n"));

	    if (check_only)
		msg_fn = G_message;
	    else
		msg_fn = G_fatal_error;
	    msg_fn(error_msg);
	    if (check_only) {
		exit(EXIT_FAILURE);
	    }
	}
	else {
	    if (check_only)
		msg_fn = G_message;
	    else
		msg_fn = G_verbose_message;            
	    msg_fn(_("Projection of input dataset and current location "
		     "appear to match"));
	    if (check_only) {
		ds_close(hDS);
		exit(EXIT_SUCCESS);
	    }
	}
    }
    ds_close(hDS);
}
