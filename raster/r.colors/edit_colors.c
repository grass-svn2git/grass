/****************************************************************************
 *
 * MODULE:       r.colors
 *
 * AUTHOR(S):    Michael Shapiro - CERL
 *               David Johnson
 *               Support for 3D rasters by Soeren Gebbert
 *
 * PURPOSE:      Allows creation and/or modification of the color table
 *               for a raster map layer.
 *
 * COPYRIGHT:    (C) 2006-2008, 2010-2011 by the GRASS Development Team
 *
 *               This program is free software under the GNU General Public
 *               License (>=v2). Read the file COPYING that comes with GRASS
 *               for details.
 *
 ***************************************************************************/

#include <stdlib.h>
#include <string.h>
#include <sys/types.h>
#include "local_proto.h"


struct colordesc
{
    char *name;
    char *desc;
    char *type;
};

int cmp_clrname(const void *a, const void *b)
{
    struct colordesc *ca = (struct colordesc *) a;
    struct colordesc *cb = (struct colordesc *) b;

    return (strcmp(ca->name, cb->name));
}

int edit_colors(int argc, char **argv, int type, const char *maptype,
		const char* Maptype)
{
    int overwrite;
    int is_from_stdin;
    int remove;
    int have_colors;
    int i;
    struct Colors colors, colors_tmp;
    struct Cell_stats statf;
    int have_stats = 0;
    struct FPRange range;
    DCELL min, max;
    const char *name = NULL, *mapset = NULL;
    const char *style = NULL, *cmap = NULL, *cmapset = NULL;
    const char *rules = NULL, *file = NULL;
    int has_cell_type = 0;
    int has_fcell_type = 0;
    struct GModule *module;
    struct maps_info input_maps;
    int stat = -1;

    struct {
        struct Flag *r, *w, *l, *d, *g, *a, *n, *e;
    } flag; 

    struct {
        struct Option *maps, *colr, *rast, *volume, *rules, *file;
    } opt;
    
    G_gisinit(argv[0]);

    module = G_define_module();
    
    if (type == RASTER3D_TYPE) {
	G_add_keyword(_("raster3d"));
        module->description =
            _("Creates/modifies the color table associated with a 3D raster map.");
    } else {
	G_add_keyword(_("raster"));
        module->description =
            _("Creates/modifies the color table associated with a raster map.");
    }
    G_add_keyword(_("color table"));

    if (type == RASTER3D_TYPE) {
        opt.maps = G_define_standard_option(G_OPT_R3_MAPS);
    } else {
        opt.maps = G_define_standard_option(G_OPT_R_MAPS);
    }
    opt.maps->required = NO;
    opt.maps->guisection = _("Map");

    opt.file = G_define_standard_option(G_OPT_F_INPUT);
    opt.file->key = "file";
    opt.file->required = NO;
    opt.file->label =
        _("Input file with one map name per line");
    opt.file->description =
        _("Input map names can be defined in an input file in case a large"
        		" amount of maps must be specified. This option is mutual"
        		" exclusive to the map option.");
    opt.file->required = NO;
    opt.file->guisection = _("Map");

    opt.colr = G_define_standard_option(G_OPT_M_COLR);
    opt.colr->guisection = _("Define");

    opt.rast = G_define_standard_option(G_OPT_R_INPUT);
    opt.rast->key = "raster";
    opt.rast->required = NO;
    opt.rast->description =
        _("Raster map from which to copy color table");
    opt.rast->guisection = _("Define");

    opt.volume = G_define_standard_option(G_OPT_R3_INPUT);
    opt.volume->key = "raster_3d";
    opt.volume->required = NO;
    opt.volume->description =
        _("3D raster map from which to copy color table");
    opt.volume->guisection = _("Define");

    opt.rules = G_define_standard_option(G_OPT_F_INPUT);
    opt.rules->key = "rules";
    opt.rules->required = NO;
    opt.rules->label = _("Path to rules file");
    opt.rules->description = _("\"-\" to read rules from stdin");
    opt.rules->guisection = _("Define");

    flag.r = G_define_flag();
    flag.r->key = 'r';
    flag.r->description = _("Remove existing color table");
    flag.r->guisection = _("Remove");

    flag.w = G_define_flag();
    flag.w->key = 'w';
    flag.w->description =
        _("Only write new color table if it does not already exist");
    flag.w->guisection = _("Define");

    flag.l = G_define_flag();
    flag.l->key = 'l';
    flag.l->description = _("List available rules then exit");
    flag.l->suppress_required = YES;
    flag.l->guisection = _("Print");

    flag.d = G_define_flag();
    flag.d->key = 'd';
    flag.d->label = _("List available rules with description then exit");
    flag.d->description = _("If a color rule is given, only this rule is listed");
    flag.d->suppress_required = YES;
    flag.d->guisection = _("Print");

    flag.n = G_define_flag();
    flag.n->key = 'n';
    flag.n->description = _("Invert colors");
    flag.n->guisection = _("Define");

    flag.g = G_define_flag();
    flag.g->key = 'g';
    flag.g->description = _("Logarithmic scaling");
    flag.g->guisection = _("Define");

    flag.a = G_define_flag();
    flag.a->key = 'a';
    flag.a->description = _("Logarithmic-absolute scaling");
    flag.a->guisection = _("Define");

    flag.e = G_define_flag();
    flag.e->key = 'e';
    flag.e->description = _("Histogram equalization");
    flag.e->guisection = _("Define");

    G_option_exclusive(opt.maps, opt.file, flag.l, NULL);
    G_option_required(opt.maps, opt.file, flag.l, flag.d, NULL);
    G_option_exclusive(opt.rast, opt.volume, NULL);
    G_option_required(opt.rast, opt.volume, opt.colr, opt.rules, flag.r, flag.l, flag.d, NULL);
    G_option_exclusive(opt.colr, opt.rules, opt.rast, opt.volume, NULL);
    G_option_exclusive(flag.g, flag.a, NULL);

    if (G_parser(argc, argv))
        exit(EXIT_FAILURE);

    if (flag.l->answer) {
	G_list_color_rules(stdout);
        return EXIT_SUCCESS;
    }

    if (flag.d->answer) {
	char path[GPATH_MAX];
	FILE *fp;
	int ncolors;
	struct colordesc *colordesc;
	char **cnames;

	/* load color rules */
	G_snprintf(path, GPATH_MAX, "%s/etc/colors", G_gisbase());

	ncolors = 0;
	cnames = G_ls2(path, &ncolors);
	colordesc = G_malloc(ncolors * sizeof(struct colordesc));
	for (i = 0; i < ncolors; i++) {
	    char buf[1024];
	    double rmin, rmax;
	    int first;
	    int cisperc;

	    colordesc[i].name = G_store(cnames[i]);
	    colordesc[i].desc = NULL;
	    
	    /* open color rule file */
	    G_snprintf(path, GPATH_MAX, "%s/etc/colors/%s", G_gisbase(),
	               colordesc[i].name);
	    fp = fopen(path, "r");
	    if (!fp)
		G_fatal_error(_("Unable to open color rule"));
	    
	    /* scan all lines */
	    first = 1;
	    rmin = rmax = 0;
	    cisperc = 0;
	    while (G_getl2(buf, sizeof(buf), fp)) {
		char value[80], color[80];
		double x;
		char c;

		G_strip(buf);

		if (*buf == '\0')
		    continue;
		if (*buf == '#')
		    continue;

		if (sscanf(buf, "%s %[^\n]", value, color) != 2)
		    continue;

		if (G_strcasecmp(value, "default") == 0) {
		    continue;
		}

		if (G_strcasecmp(value, "nv") == 0) {
		    continue;
		}

		if (sscanf(value, "%lf%c", &x, &c) == 2 && c == '%') {
		    cisperc = 1;
		    break;
		}
		if (sscanf(value, "%lf", &x) == 1) {
		    if (first) {
			first = 0;
			rmin = rmax = x;
		    }
		    else {
			if (rmin > x)
			    rmin = x;
			if (rmax < x)
			    rmax = x;
		    }
		}
	    }
	    fclose(fp);

	    if (cisperc)
		colordesc[i].type = G_store(_("relative, percent of map range"));
	    else {
		G_snprintf(buf, sizeof(buf) - 1, _("absolute, %g to %g"), rmin, rmax);
		colordesc[i].type = G_store(buf);
	    }
	}
	
	qsort(colordesc, ncolors, sizeof(struct colordesc), cmp_clrname);

	/* load color descriptions */
	G_snprintf(path, GPATH_MAX, "%s/etc/colors.desc", G_gisbase());
	fp = fopen(path, "r");
	if (!fp)
	    G_fatal_error(_("Unable to open color descriptions"));

	for (;;) {
	    char buf[1024];
            char tok_buf[1024];
	    char *cname, *cdesc;
            int ntokens;
            char **tokens;
	    struct colordesc csearch, *cfound;

	    if (!G_getl2(buf, sizeof(buf), fp))
		break;
            strcpy(tok_buf, buf);
            tokens = G_tokenize(tok_buf, ":");
            ntokens = G_number_of_tokens(tokens);
	    if (ntokens != 2)
		continue;

	    cname = G_chop(tokens[0]);
	    cdesc = G_chop(tokens[1]);
	    
	    csearch.name = cname;
	    cfound = bsearch(&csearch, colordesc, ncolors,
	                     sizeof(struct colordesc), cmp_clrname);

	    if (cfound) {
		cfound->desc = G_store(cdesc);
	    }
	    G_free_tokens(tokens);
	}
	fclose(fp);

	if (opt.colr->answer) {
	    struct colordesc csearch, *cfound;

	    csearch.name = opt.colr->answer;
	    cfound = bsearch(&csearch, colordesc, ncolors,
	                     sizeof(struct colordesc), cmp_clrname);

	    if (cfound) {
		if (cfound->desc) {
		    fprintf(stdout, "%s: %s (%s)\n", cfound->name,
			    cfound->desc, cfound->type);
		}
		else {
		    fprintf(stdout, "%s: (%s)\n", cfound->name,
			    cfound->type);
		}
	    }
	}
	else {
	    for (i = 0; i < ncolors; i++) {
		if (colordesc[i].desc) {
		    fprintf(stdout, "%s: %s (%s)\n", colordesc[i].name,
			    colordesc[i].desc, colordesc[i].type);
		}
		else {
		    fprintf(stdout, "%s: (%s)\n", colordesc[i].name,
			    colordesc[i].type);
		}
	    }
	}

        return EXIT_SUCCESS;
    }

    overwrite = !flag.w->answer;
    remove = flag.r->answer;
    style = opt.colr->answer;
    rules = opt.rules->answer;
    file = opt.file->answer;

    if (opt.rast->answer)
        cmap = opt.rast->answer;
    if (opt.volume->answer)
        cmap = opt.volume->answer;

    is_from_stdin = rules && strcmp(rules, "-") == 0;
    if (is_from_stdin)
        rules = NULL;

    /* Read the map names from the infile */
    if (file) {
	FILE *in;
	int num_maps = 0;
	int max_maps = 0;

	in = fopen(file, "r");
	if (!in)
		G_fatal_error(_("Unable to open %s file <%s>"), maptype, file);

	input_maps.names = (char **)G_calloc(100, sizeof(char *));
	input_maps.mapsets = (char **)G_calloc(100, sizeof(char *));
	input_maps.map_types = (int*)G_calloc(100, sizeof(int));
	input_maps.min = (DCELL*)G_calloc(100, sizeof(DCELL));
	input_maps.max = (DCELL*)G_calloc(100, sizeof(DCELL));

	for (;;) {
	    char buf[GNAME_MAX]; /* Name */

	    if (!G_getl2(buf, sizeof(buf), in))
		break;

	    name = G_chop(buf);

	    /* Ignore empty lines */
	    if (!*name)
		continue;

	    /* Reallocate memory */
	    if (num_maps >= max_maps) {
		max_maps += 100;
		input_maps.names = (char **)G_realloc(input_maps.names, max_maps * sizeof(char *));
		input_maps.mapsets = (char **)G_realloc(input_maps.mapsets, max_maps * sizeof(char *));
		input_maps.map_types = (int*)G_realloc(input_maps.map_types, max_maps * sizeof(int));
		input_maps.min = (DCELL*)G_realloc(input_maps.min, max_maps * sizeof(DCELL));
		input_maps.max = (DCELL*)G_realloc(input_maps.max, max_maps * sizeof(DCELL));
	    }

	    /* Store the map name */
	    input_maps.names[num_maps] = G_store(name);

	    /* Switch between raster and volume */
	    if (type == RASTER3D_TYPE) {
		input_maps.mapsets[num_maps] = G_store(G_find_raster3d(input_maps.names[num_maps], ""));
	    }
	    else {
		input_maps.mapsets[num_maps] = G_store(G_find_raster2(input_maps.names[num_maps], ""));
	    }
	    if (input_maps.mapsets[num_maps] == NULL)
		G_fatal_error(_("%s map <%s> not found"), Maptype, input_maps.names[num_maps]);

	    num_maps++;
	}

        if (num_maps < 1)
            G_fatal_error(_("No %s map name found in input file <%s>"), maptype, file);

	input_maps.num = num_maps;

        fclose(in);
    }
    else if (opt.maps->answer) {
	input_maps.num = 0;
	while (opt.maps->answers[input_maps.num]) {
		input_maps.num++;
	}
	input_maps.names = (char **)G_calloc(input_maps.num, sizeof(char *));
	input_maps.mapsets = (char **)G_calloc(input_maps.num, sizeof(char *));
	input_maps.map_types = (int*)G_calloc(input_maps.num, sizeof(int));
	input_maps.min = (DCELL*)G_calloc(input_maps.num, sizeof(DCELL));
	input_maps.max = (DCELL*)G_calloc(input_maps.num, sizeof(DCELL));

	for (i = 0; i < input_maps.num; i++) {
		input_maps.names[i] = G_store(opt.maps->answers[i]);

	    /* Switch between raster and volume */
	    if (type == RASTER3D_TYPE) {
		input_maps.mapsets[i] = G_store(G_find_raster3d(input_maps.names[i], ""));
	    }
	    else {
		input_maps.mapsets[i] = G_store(G_find_raster2(input_maps.names[i], ""));
	    }
	    if (input_maps.mapsets[i] == NULL)
		G_fatal_error(_("%s map <%s> not found"), Maptype, input_maps.names[i]);
	}
    }

    if (remove) {
    	for (i = 0; i < input_maps.num; i++) {
	    name = input_maps.names[i];
	    mapset = input_maps.mapsets[i];

	    if (type == RASTER3D_TYPE) {
		    stat = Rast3d_remove_color(name);
	    } else {
		    stat = Rast_remove_colors(name, mapset);
	    }
	    if (stat < 0)
		    G_fatal_error(_("Unable to remove color table of %s map <%s>"), maptype, name);
	    if (stat == 0)
		    G_warning(_("Color table of %s map <%s> not found"), maptype, name);
    	}
        return EXIT_SUCCESS;
    }

    G_suppress_warnings(TRUE);

    for (i = 0; i < input_maps.num; i++) {
	name = input_maps.names[i];
	mapset = input_maps.mapsets[i];

	if (type == RASTER3D_TYPE) {
	    have_colors = Rast3d_read_colors(name, mapset, &colors);
	}
	else {
	    have_colors = Rast_read_colors(name, mapset, &colors);
	}
	/*
	  if (have_colors >= 0)
	  Rast_free_colors(&colors);
	 */

	if (have_colors > 0 && !overwrite) {
	    G_fatal_error(_("Color table exists for %s map <%s>. Exiting."), maptype, name);
	}
    }

    G_suppress_warnings(FALSE);

    has_fcell_type = 0;
    has_cell_type = 0;
    min = max = 0;
    for (i = 0; i < input_maps.num; i++) {
	name = input_maps.names[i];
	mapset = input_maps.mapsets[i];

	if (type == RASTER3D_TYPE) {
	    input_maps.map_types[i] = 1; /* 3D raster maps are always floating point */
	    has_fcell_type = 1;
	    Rast3d_read_range(name, mapset, &range);
	}
	else {
	    input_maps.map_types[i] = Rast_map_is_fp(name, mapset);
	    if(input_maps.map_types[i] == 1)
		has_fcell_type = 1;
	    else
		has_cell_type = 1;

	    Rast_read_fp_range(name, mapset, &range);
	}

	if (i > 0) {
	    if(has_fcell_type && has_cell_type) {
		G_fatal_error("Input maps must have the same cell type. "
				"Mixing of integer and floating point maps is not supported.");
	    }
	}

	Rast_get_fp_range_min_max(&range, &input_maps.min[i], &input_maps.max[i]);

	/* Compute min, max of all maps*/
	if (i == 0) {
	    min = input_maps.min[i];
	    max = input_maps.max[i];
	}
	else {
	    if(input_maps.min[i] < min)
		min = input_maps.min[i];
	    if(input_maps.max[i] > max)
		max = input_maps.max[i];
	}
    }

    if (is_from_stdin) {
        if (!read_color_rules(stdin, &colors, min, max, has_fcell_type))
            exit(EXIT_FAILURE);
    }
    else if (style) {
        /* 
         * here the predefined color-table color-styles are created by GRASS library calls. 
         */
        if (strcmp(style, "random") == 0) {
            if (has_fcell_type)
                G_fatal_error(_("Color table 'random' is not supported for floating point %s map"), maptype);
            Rast_make_random_colors(&colors, (CELL) min, (CELL) max);
        }
	else if (strcmp(style, "grey.eq") == 0) {
            if (has_fcell_type)
                G_fatal_error(_("Color table 'grey.eq' is not supported for floating point %s map"), maptype);
            if (!have_stats)
                have_stats = get_stats(&input_maps, &statf);
            Rast_make_histogram_eq_colors(&colors, &statf);
        }
	else if (strcmp(style, "grey.log") == 0) {
            if (has_fcell_type)
                G_fatal_error(_("Color table 'grey.log' is not supported for floating point %s map"), maptype);
            if (!have_stats)
                have_stats = get_stats(&input_maps, &statf);
            Rast_make_histogram_log_colors(&colors, &statf, (CELL) min,
                                           (CELL) max);
        }
	else if (G_find_color_rule(style))
            Rast_make_fp_colors(&colors, style, min, max);
        else
            G_fatal_error(_("Unknown color request '%s'"), style);
    }
    else if (rules) {
        if (!Rast_load_fp_colors(&colors, rules, min, max)) {
            /* for backwards compatibility try as std name; remove for GRASS 7 */
            char path[GPATH_MAX];

            /* don't bother with native dirsep as not needed for backwards compatibility */
            G_snprintf(path, GPATH_MAX, "%s/etc/colors/%s", G_gisbase(), rules);

            if (!Rast_load_fp_colors(&colors, path, min, max))
                G_fatal_error(_("Unable to load rules file <%s>"), rules);
        }
    }
    else {
        /* use color from another map (cmap) */
        if (opt.rast->answer) {
            cmapset = G_find_raster2(cmap, "");
            if (cmapset == NULL)
                G_fatal_error(_("Raster map <%s> not found"), cmap);

            if (Rast_read_colors(cmap, cmapset, &colors) < 0)
                G_fatal_error(_("Unable to read color table for raster map <%s>"), cmap);
        }
	else {
            cmapset = G_find_raster3d(cmap, "");
            if (cmapset == NULL)
                G_fatal_error(_("3D raster map <%s> not found"), cmap);

            if (Rast3d_read_colors(cmap, cmapset, &colors) < 0)
                G_fatal_error(_("Unable to read color table for 3D raster map <%s>"), cmap);
        }
    }

    if (has_fcell_type)
        Rast_mark_colors_as_fp(&colors);

    if (flag.n->answer)
        Rast_invert_colors(&colors);

    if (flag.e->answer) {
        if (has_fcell_type && !has_cell_type) {
            struct FP_stats fpstats;

            get_fp_stats(&input_maps, &fpstats, min, max, flag.g->answer, flag.a->answer, type);
            Rast_histogram_eq_fp_colors(&colors_tmp, &colors, &fpstats);
        }
	else {
            if (!have_stats)
                have_stats = get_stats(&input_maps, &statf);
            Rast_histogram_eq_colors(&colors_tmp, &colors, &statf);
        }
        colors = colors_tmp;
    }

    if (flag.g->answer) {
        Rast_log_colors(&colors_tmp, &colors, 100);
        colors = colors_tmp;
    }

    if (flag.a->answer) {
        Rast_abs_log_colors(&colors_tmp, &colors, 100);
        colors = colors_tmp;
    }

    for (i = 0; i < input_maps.num; i++) {
	name = input_maps.names[i];
	mapset = input_maps.mapsets[i];

	if (input_maps.map_types[i])
	    Rast_mark_colors_as_fp(&colors);
	if (type == RASTER3D_TYPE) {
	    Rast3d_write_colors(name, mapset, &colors);
	}
	else {
	    Rast_write_colors(name, mapset, &colors);
	}
	G_message(_("Color table for %s map <%s> set to '%s'"), maptype, name,
		  is_from_stdin ? "rules" : style ? style : rules ? rules :
		  cmap);
    }

    exit(EXIT_SUCCESS);
}
