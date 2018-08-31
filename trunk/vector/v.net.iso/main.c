
/****************************************************************
 * 
 * MODULE:       v.net.iso
 *
 * AUTHOR(S):    Radim Blazek
 *               Stepan Turek <stepan.turek seznam.cz> (turns support)
 *               Markus Metz (costs from/to centers; attributes)
 *                
 * PURPOSE:      Split net to bands between isolines.
 *
 * COPYRIGHT:    (C) 2001-2008,2014,2017 by the GRASS Development Team
 *
 *               This program is free software under the 
 *               GNU General Public License (>=v2). 
 *               Read the file COPYING that comes with GRASS
 *               for details.
 *
 ****************************************************************/
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <grass/gis.h>
#include <grass/vector.h>
#include <grass/dbmi.h>
#include <grass/glocale.h>
#include "alloc.h"

typedef struct
{				/* iso point along the line */
    int iso;			/* index of iso line in iso array of costs */
    double distance;		/* distance along the line from the beginning for both directions */
    int center;			/* nearest center */
} ISOPOINT;

int main(int argc, char **argv)
{
    int i, ret, line, center1, center2;
    int nlines, nnodes, type, ltype, afield, nfield, geo, cat;
    int tfield, tucfield;
    int node1, node2;
    double e1cost, e2cost, n1cost, n2cost, s1cost, s2cost, l, l1;
    struct Option *map, *output, *method_opt;
    struct Option *afield_opt, *nfield_opt, *afcol, *abcol, *ncol, *type_opt,
	*term_opt, *cost_opt, *tfield_opt, *tucfield_opt;
    struct Flag *geo_f, *turntable_f, *ucat_f;
    struct GModule *module;
    struct Map_info Map, Out;
    struct cat_list *catlist;
    CENTER *Centers = NULL;
    int acenters = 0, ncenters = 0;
    NODE *Nodes;
    struct line_cats *Cats, *ICats, *OCats;
    struct line_pnts *Points, *SPoints;
    int graph_version;
    int from_centers;
    int niso, aiso;
    double *iso;
    char **isolbl;
    int npnts1, apnts1 = 0, npnts2, apnts2 = 0;
    ISOPOINT *pnts1 = NULL, *pnts2 = NULL;
    int next_iso;

    /* Attribute table */
    int unique_cats, ucat, ocat, n;
    char buf[2000];
    dbString sql;
    dbDriver *driver;
    struct field_info *Fi;

    /* initialize GIS environment */
    G_gisinit(argv[0]);

    /* initialize module */
    module = G_define_module();
    G_add_keyword(_("vector"));
    G_add_keyword(_("network"));
    G_add_keyword(_("cost allocation"));
    G_add_keyword(_("isolines"));
    module->label = _("Splits subnets for nearest centers by cost isolines.");
    module->description =
	_("Splits net to bands between cost isolines (direction from center). "
	  "Center node must be opened (costs >= 0). "
	  "Costs of center node are used in calculation.");

    map = G_define_standard_option(G_OPT_V_INPUT);
    output = G_define_standard_option(G_OPT_V_OUTPUT);

    method_opt = G_define_option();
    method_opt->key = "method";
    method_opt->type = TYPE_STRING;
    method_opt->required = NO;
    method_opt->options = "from,to";
    method_opt->answer = "from";
    method_opt->description = _("Use costs from centers or costs to centers");
    method_opt->guisection = _("Cost");

    term_opt = G_define_standard_option(G_OPT_V_CATS);
    term_opt->key = "center_cats";
    term_opt->required = YES;
    term_opt->description =
	_("Categories of centers (points on nodes) to which net "
	  "will be allocated, "
	  "layer for this categories is given by nlayer option");

    cost_opt = G_define_option();
    cost_opt->key = "costs";
    cost_opt->type = TYPE_INTEGER;
    cost_opt->multiple = YES;
    cost_opt->required = YES;
    cost_opt->description = _("Costs for isolines");

    afield_opt = G_define_standard_option(G_OPT_V_FIELD);
    afield_opt->key = "arc_layer";
    afield_opt->answer = "1";
    afield_opt->required = YES;
    afield_opt->label = _("Arc layer");

    type_opt = G_define_standard_option(G_OPT_V_TYPE);
    type_opt->key = "arc_type";
    type_opt->options = "line,boundary";
    type_opt->answer = "line,boundary";
    type_opt->required = YES;
    type_opt->label = _("Arc type");

    nfield_opt = G_define_standard_option(G_OPT_V_FIELD);
    nfield_opt->key = "node_layer";
    nfield_opt->answer = "2";
    nfield_opt->required = YES;
    nfield_opt->label = _("Node layer");

    afcol = G_define_standard_option(G_OPT_DB_COLUMN);
    afcol->key = "arc_column";
    afcol->description =
	_("Arc forward/both direction(s) cost column (number)");
    afcol->guisection = _("Cost");

    abcol = G_define_standard_option(G_OPT_DB_COLUMN);
    abcol->key = "arc_backward_column";
    abcol->description = _("Arc backward direction cost column (number)");
    abcol->guisection = _("Cost");

    ncol = G_define_standard_option(G_OPT_DB_COLUMN);
    ncol->key = "node_column";
    ncol->description = _("Node cost column (number)");
    ncol->guisection = _("Cost");

    turntable_f = G_define_flag();
    turntable_f->key = 't';
    turntable_f->description = _("Use turntable");
    turntable_f->guisection = _("Turntable");

    tfield_opt = G_define_standard_option(G_OPT_V_FIELD);
    tfield_opt->key = "turn_layer";
    tfield_opt->answer = "3";
    tfield_opt->label = _("Layer with turntable");
    tfield_opt->description =
	_("Relevant only with -t flag");
    tfield_opt->guisection = _("Turntable");

    tucfield_opt = G_define_standard_option(G_OPT_V_FIELD);
    tucfield_opt->key = "turn_cat_layer";
    tucfield_opt->answer = "4";
    tucfield_opt->label = _("Layer with unique categories used in turntable");
    tucfield_opt->description =
	_("Relevant only with -t flag");
    tucfield_opt->guisection = _("Turntable");

    geo_f = G_define_flag();
    geo_f->key = 'g';
    geo_f->description =
	_("Use geodesic calculation for longitude-latitude locations");

    ucat_f = G_define_flag();
    ucat_f->key = 'u';
    ucat_f->label =
	_("Create unique categories and attribute table");
    ucat_f->description =
	_("Default: one category for each iso-band");

    if (G_parser(argc, argv))
	exit(EXIT_FAILURE);

    Vect_check_input_output_name(map->answer, output->answer, G_FATAL_EXIT);

    Cats = Vect_new_cats_struct();
    ICats = Vect_new_cats_struct();
    OCats = Vect_new_cats_struct();
    Points = Vect_new_line_struct();
    SPoints = Vect_new_line_struct();

    type = Vect_option_to_types(type_opt);

    catlist = Vect_new_cat_list();
    Vect_str_to_cat_list(term_opt->answer, catlist);

    unique_cats = ucat_f->answer;

    /* Iso costs */
    aiso = 1;
    iso = (double *)G_malloc(aiso * sizeof(double));
    isolbl = (char **)G_malloc(aiso * sizeof(char *));
    /* Set first iso to 0 */
    iso[0] = 0;
    niso = 1;
    i = 0;
    while (cost_opt->answers[i]) {
	if (niso == aiso) {
	    aiso += 1;
	    iso = (double *)G_realloc(iso, aiso * sizeof(double));
	    isolbl = (char **)G_realloc(isolbl, aiso * sizeof(char *));
	}
	iso[niso] = atof(cost_opt->answers[i]);
	if (iso[niso] <= 0)
	    G_fatal_error(_("Wrong iso cost: %f"), iso[niso]);

	if (iso[niso] <= iso[niso - 1])
	    G_fatal_error(_("Iso cost: %f less than previous"), iso[niso]);

	isolbl[niso - 1] = NULL;
	G_asprintf(&isolbl[niso - 1], "%g - %g", iso[niso - 1], iso[niso]);

	G_verbose_message(_("Iso cost %d: %f"), niso, iso[niso]);
	niso++;
	i++;
    }

    /* Should not happen: */
    if (niso < 2)
	G_warning(_
		  ("Not enough costs, everything reachable falls to first band"));

    isolbl[niso - 1] = NULL;
    G_asprintf(&isolbl[niso - 1], "> %g", iso[niso - 1]);

    if (geo_f->answer)
	geo = 1;
    else
	geo = 0;

    Vect_set_open_level(2);
    if (Vect_open_old(&Map, map->answer, "") < 0)
	G_fatal_error(_("Unable to open vector map <%s>"), map->answer);

    afield = Vect_get_field_number(&Map, afield_opt->answer);
    nfield = Vect_get_field_number(&Map, nfield_opt->answer);
    tfield = Vect_get_field_number(&Map, tfield_opt->answer);
    tucfield = Vect_get_field_number(&Map, tucfield_opt->answer);

    /* Build graph */
    graph_version = 1;
    from_centers = 1;
    if (method_opt->answer[0] == 't') {
	from_centers = 0;
	if (!turntable_f->answer)
	    graph_version = 2;
    }
    if (turntable_f->answer)
	Vect_net_ttb_build_graph(&Map, type, afield, nfield, tfield, tucfield,
				 afcol->answer, abcol->answer, ncol->answer,
				 geo, 0);
    else
	Vect_net_build_graph(&Map, type, afield, nfield, afcol->answer,
			     abcol->answer, ncol->answer, geo, graph_version);

    nnodes = Vect_get_num_nodes(&Map);
    nlines = Vect_get_num_lines(&Map);

    /* Create list of centers based on list of categories */
    for (i = 1; i <= nlines; i++) {
	int node;

	ltype = Vect_get_line_type(&Map, i);
	if (!(ltype & GV_POINT))
	    continue;

	Vect_read_line(&Map, Points, Cats, i);
	node =
	    Vect_find_node(&Map, Points->x[0], Points->y[0], Points->z[0], 0,
			   0);
	if (!node) {
	    G_warning(_("Point is not connected to the network"));
	    continue;
	}
	if (!(Vect_cat_get(Cats, nfield, &cat)))
	    continue;
	if (Vect_cat_in_cat_list(cat, catlist)) {
	    Vect_net_get_node_cost(&Map, node, &n1cost);
	    if (n1cost == -1) {	/* closed */
		G_warning(_("Center at closed node (costs = -1) ignored"));
	    }
	    else {
		if (acenters == ncenters) {
		    acenters += 1;
		    Centers =
			(CENTER *) G_realloc(Centers,
					     acenters * sizeof(CENTER));
		}
		Centers[ncenters].cat = cat;
		Centers[ncenters].node = node;
		G_debug(2, "center = %d node = %d cat = %d", ncenters,
			node, cat);
		ncenters++;
	    }
	}
    }

    G_message(_("Number of centers: %d (nlayer %d)"), ncenters, nfield);

    if (ncenters == 0)
	G_warning(_("Not enough centers for selected nlayer. Nothing will be allocated."));

    /* alloc and reset space for all nodes */
    if (turntable_f->answer) {
	/* if turntable is used we are looking for lines as destinations, instead of the intersections (nodes) */
	Nodes = (NODE *) G_calloc((nlines * 2 + 2), sizeof(NODE));
	for (i = 2; i <= (nlines * 2 + 2); i++) {
	    Nodes[i].center = -1;/* NOTE: first two items of Nodes are not used */
	}

    }
    else {
	Nodes = (NODE *) G_calloc((nnodes + 1), sizeof(NODE));
	for (i = 1; i <= nnodes; i++) {
	    Nodes[i].center = -1;
	}
    }

    /* Fill Nodes by nearest center and costs from that center */

    if (turntable_f->answer) {
	if (from_centers) {
	    G_message(_("Calculating costs from centers ..."));
	    alloc_from_centers_loop_tt(&Map, Nodes, Centers, ncenters,
				       tucfield);
	}
	else {
	    G_message(_("Calculating costs to centers ..."));
	    alloc_to_centers_loop_tt(&Map, Nodes, Centers, ncenters,
				       tucfield);
	}
    }
    else {
	if (from_centers) {
	    G_message(_("Calculating costs from centers ..."));
	    alloc_from_centers(Vect_net_get_graph(&Map), Nodes, Centers, ncenters);
	}
	else {
	    G_message(_("Calculating costs to centers ..."));
	    alloc_to_centers(Vect_net_get_graph(&Map), Nodes, Centers, ncenters);
	}
    }

    /* Write arcs to new map */
    if (Vect_open_new(&Out, output->answer, Vect_is_3d(&Map)) < 0)
	G_fatal_error(_("Unable to create vector map <%s>"), output->answer);

    Vect_hist_command(&Out);

    Fi = NULL;
    driver = NULL;
    if (unique_cats) {
	/* create attribute table:
	 * cat: new category
	 * ocat: original category in afield
	 * center: nearest center
	 * isonr: iso zone number
	 * isolbl: iso zone label
	 */
	Fi = Vect_default_field_info(&Out, 1, NULL, GV_MTABLE);
	Vect_map_add_dblink(&Out, 1, NULL, Fi->table, GV_KEY_COLUMN, Fi->database,
			    Fi->driver);

	driver = db_start_driver_open_database(Fi->driver, Fi->database);
	if (driver == NULL)
	    G_fatal_error(_("Unable to open database <%s> by driver <%s>"),
			  Fi->database, Fi->driver);
	db_set_error_handler_driver(driver);

	sprintf(buf,
		"create table %s ( %s integer, ocat integer, center integer, isonr integer, "
		"isolbl varchar(255) )",
		Fi->table, GV_KEY_COLUMN);

	db_init_string(&sql);
	db_set_string(&sql, buf);
	G_debug(2, "%s", db_get_string(&sql));

	if (db_execute_immediate(driver, &sql) != DB_OK) {
	    G_fatal_error(_("Unable to create table: '%s'"), db_get_string(&sql));
	}

	if (db_create_index2(driver, Fi->table, GV_KEY_COLUMN) != DB_OK)
	    G_warning(_("Cannot create index"));

	if (db_grant_on_table
	    (driver, Fi->table, DB_PRIV_SELECT, DB_GROUP | DB_PUBLIC) != DB_OK)
	    G_fatal_error(_("Cannot grant privileges on table <%s>"), Fi->table);

	db_begin_transaction(driver);
    }

    G_message(_("Generating isolines..."));
    apnts1 = 1;
    pnts1 = (ISOPOINT *) G_malloc(apnts1 * sizeof(ISOPOINT));
    apnts2 = 1;
    pnts2 = (ISOPOINT *) G_malloc(apnts2 * sizeof(ISOPOINT));
    ucat = 1;
    for (line = 1; line <= nlines; line++) {
	G_percent(line, nlines, 2);

	ltype = Vect_read_line(&Map, Points, ICats, line);
	if (!(ltype & type)) {
	    continue;
	}

	l = Vect_line_length(Points);
	if (l == 0)
	    continue;

	if (unique_cats) {
	    Vect_reset_cats(OCats);
	    for (n = 0; n < ICats->n_cats; n++) {
		if (ICats->field[n] == afield) {
		    Vect_cat_set(OCats, 2, ICats->cat[n]);
		}
	    }
	}

	if (turntable_f->answer) {
	    center1 = Nodes[line * 2].center;
	    center2 = Nodes[line * 2 + 1].center;
	    s1cost = Nodes[line * 2].cost;
	    s2cost = Nodes[line * 2 + 1].cost;
	    n1cost = n2cost = 0;
	}
	else {
	    Vect_get_line_nodes(&Map, line, &node1, &node2);
	    center1 = Nodes[node1].center;
	    center2 = Nodes[node2].center;
	    s1cost = Nodes[node1].cost;
	    s2cost = Nodes[node2].cost;
	    if (s1cost > 0)
		s1cost /= Map.dgraph.cost_multip;
	    if (s2cost > 0)
		s2cost /= Map.dgraph.cost_multip;

	    Vect_net_get_node_cost(&Map, node1, &n1cost);
	    Vect_net_get_node_cost(&Map, node2, &n2cost);
	}

	if (from_centers) {
	    Vect_net_get_line_cost(&Map, line, GV_FORWARD, &e1cost);
	    Vect_net_get_line_cost(&Map, line, GV_BACKWARD, &e2cost);
	}
	else {
	    /* from node to center */
	    Vect_net_get_line_cost(&Map, line, GV_FORWARD, &e2cost);
	    Vect_net_get_line_cost(&Map, line, GV_BACKWARD, &e1cost);
	}

	G_debug(3, "Line %d : length = %f", line, l);
	G_debug(3, "Arc centers: %d %d (nodes: %d %d)", center1, center2,
		node1, node2);

	G_debug(3, "  s1cost = %f n1cost = %f e1cost = %f", s1cost, n1cost,
		e1cost);
	G_debug(3, "  s2cost = %f n2cost = %f e2cost = %f", s2cost, n2cost,
		e2cost);


	/* First check if arc is reachable from at least one side */
	if ((center1 != -1 && n1cost != -1 && e1cost != -1) ||
	    (center2 != -1 && n2cost != -1 && e2cost != -1)) {
	    /* Line is reachable at least from one side */
	    G_debug(3, "  -> arc is reachable");

	    /* Add costs of node to starting costs */
	    if (s1cost >= 0 && n1cost > 0)
		s1cost += n1cost;
	    if (s2cost >= 0 && n2cost > 0)
		s2cost += n2cost;

	    if (e1cost > 0)
		e1cost /= l;
	    if (e2cost > 0)
		e2cost /= l;

	    /* Find points on isolines along the line in both directions, add them to array,
	     *  first point is placed at the beginning/end of line */
	    /* Forward */
	    npnts1 = 0;		/* in case this direction is closed */
	    if (center1 != -1 && n1cost != -1 && e1cost != -1) {
		/* Find iso for beginning of the line */
		next_iso = 0;
		for (i = niso - 1; i >= 0; i--) {
		    if (iso[i] <= s1cost) {
			next_iso = i;
			break;
		    }
		}
		/* Add first */
		pnts1[0].iso = next_iso;
		pnts1[0].distance = 0;
		pnts1[0].center = center1;
		npnts1++;
		next_iso++;

		/* Calculate distances for points along line */
		while (next_iso < niso) {
		    if (e1cost == 0)
			break;	/* Outside line */
		    l1 = (iso[next_iso] - s1cost) / e1cost;
		    if (l1 >= l)
			break;	/* Outside line */

		    if (npnts1 == apnts1) {
			apnts1 += 1;
			pnts1 =
			    (ISOPOINT *) G_realloc(pnts1,
						   apnts1 * sizeof(ISOPOINT));
		    }
		    pnts1[npnts1].iso = next_iso;
		    pnts1[npnts1].distance = l1;
		    pnts1[npnts1].center = center1;
		    G_debug(3,
			    "  forward %d : iso %d : distance %f : cost %f",
			    npnts1, next_iso, l1, iso[next_iso]);
		    npnts1++;
		    next_iso++;
		}
	    }
	    G_debug(3, "  npnts1 = %d", npnts1);

	    /* Backward */
	    npnts2 = 0;
	    if (center2 != -1 && n2cost != -1 && e2cost != -1) {
		/* Find iso for beginning of the line */
		next_iso = 0;
		for (i = niso - 1; i >= 0; i--) {
		    if (iso[i] <= s2cost) {
			next_iso = i;
			break;
		    }
		}
		/* Add first */
		pnts2[0].iso = next_iso;
		pnts2[0].distance = l;
		pnts2[0].center = center2;
		npnts2++;
		next_iso++;

		/* Calculate distances for points along line */
		while (next_iso < niso) {
		    if (e2cost == 0)
			break;	/* Outside line */
		    l1 = (iso[next_iso] - s2cost) / e2cost;
		    if (l1 >= l)
			break;	/* Outside line */

		    if (npnts2 == apnts2) {
			apnts2 += 1;
			pnts2 =
			    (ISOPOINT *) G_realloc(pnts2,
						   apnts2 * sizeof(ISOPOINT));
		    }
		    pnts2[npnts2].iso = next_iso;
		    pnts2[npnts2].distance = l - l1;
		    pnts2[npnts2].center = center2;
		    G_debug(3,
			    "  backward %d : iso %d : distance %f : cost %f",
			    npnts2, next_iso, l - l1, iso[next_iso]);
		    npnts2++;
		    next_iso++;
		}
	    }
	    G_debug(3, "  npnts2 = %d", npnts2);

	    /* Limit number of points by maximum costs in reverse direction, this may remove
	     *  also the first point in one direction, but not in both */
	    /* Forward */
	    if (npnts2 > 0) {
		for (i = 0; i < npnts1; i++) {
		    G_debug(3,
			    "  pnt1 = %d dist1 = %f iso1 = %d max iso2 = %d",
			    i, pnts1[i].distance, pnts1[i].iso,
			    pnts2[npnts2 - 1].iso);
		    if (pnts2[npnts2 - 1].iso < pnts1[i].iso) {
			G_debug(3, "    -> cut here");
			npnts1 = i;
			break;
		    }
		}
	    }
	    G_debug(3, "  npnts1 cut = %d", npnts1);

	    /* Backward */
	    if (npnts1 > 0) {
		for (i = 0; i < npnts2; i++) {
		    G_debug(3,
			    "  pnt2 = %d dist2 = %f iso2 = %d max iso1 = %d",
			    i, pnts2[i].distance, pnts2[i].iso,
			    pnts1[npnts1 - 1].iso);
		    if (pnts1[npnts1 - 1].iso < pnts2[i].iso) {
			G_debug(3, "    -> cut here");
			npnts2 = i;
			break;
		    }
		}
	    }
	    G_debug(3, "  npnts2 cut = %d", npnts2);

	    /* Biggest cost should be equal if exist (npnts > 0). Cut out overlapping segments,
	     *  this can cut only points on line but not first points */
	    if (npnts1 > 1 && npnts2 > 1) {
		while (npnts1 > 1 && npnts2 > 1) {
		    if (pnts1[npnts1 - 1].distance >= pnts2[npnts2 - 1].distance) {	/* overlap */
			npnts1--;
			npnts2--;
		    }
		    else {
			break;
		    }
		}
	    }
	    G_debug(3, "  npnts1 2. cut = %d", npnts1);
	    G_debug(3, "  npnts2 2. cut = %d", npnts2);
	    
	    if (npnts1 > 0 && npnts2 > 0) {
		if (pnts1[npnts1 - 1].center != pnts2[npnts2 - 1].center &&
		    e1cost >= 0 && e2cost >= 0) {

		    if (npnts1 == apnts1) {
			apnts1 += 1;
			pnts1 =
			    (ISOPOINT *) G_realloc(pnts1,
						   apnts1 * sizeof(ISOPOINT));
		    }
		    if (e1cost + e2cost == 0) {
			if (s1cost + s2cost == 0)
			    l1 = l / 2.;
			else
			    l1 = l * s1cost / (s1cost + s2cost);
		    }
		    else
			l1 = (l * e2cost - s1cost + s2cost) / (e1cost + e2cost);
		    if (l1 != pnts1[npnts1 - 1].distance) {
			pnts1[npnts1].distance = l1;
			pnts1[npnts1].iso = pnts2[npnts2 - 1].iso;
			pnts1[npnts1].center = pnts2[npnts2 - 1].center;
			npnts1++;
		    }
		}
	    }

	    /* Now we have points in both directions which may not overlap, npoints in one
	     *  direction may be 0 but not both */

	    /* Join both arrays, iso of point is for next segment (point is at the beginning) */
	    /* In case npnts1 == 0 add point at distance 0 */
	    if (npnts1 == 0) {
		G_debug(3,
			"  npnts1 = 0 -> add first at distance 0, cat = %d",
			pnts2[npnts2 - 1].iso);
		pnts1[0].iso = pnts2[npnts2 - 1].iso;	/* use last point iso in reverse direction */
		pnts1[0].distance = 0;
		pnts1[0].center = pnts2[npnts2 - 1].center;
		npnts1++;
	    }
	    for (i = npnts2 - 1; i >= 0; i--) {
		/* Check if identical */
		if (pnts1[npnts1 - 1].distance == pnts2[i].distance)
		    continue;

		if (npnts1 == apnts1) {
		    apnts1 += 1;
		    pnts1 =
			(ISOPOINT *) G_realloc(pnts1,
					       apnts1 * sizeof(ISOPOINT));
		}
		pnts1[npnts1].iso = pnts2[i].iso - 1;	/* last may be -1, but it is not used */
		pnts1[npnts1].distance = pnts2[i].distance;
		pnts1[npnts1].center = pnts2[i].center;
		npnts1++;
	    }
	    /* In case npnts2 == 0 add point at the end */
	    if (npnts2 == 0) {
		pnts1[npnts1].iso = 0;	/* not used */
		pnts1[npnts1].distance = l;
		pnts1[npnts1].center = center1;
		npnts1++;
	    }

	    /* Create line segments. */
	    for (i = 1; i < npnts1; i++) {
		cat = pnts1[i - 1].iso + 1;
		G_debug(3, "  segment %f - %f cat %d", pnts1[i - 1].distance,
			pnts1[i].distance, cat);
		ret =
		    Vect_line_segment(Points, pnts1[i - 1].distance,
				      pnts1[i].distance, SPoints);
		if (ret == 0) {
		    G_warning(_
			      ("Cannot get line segment, segment out of line"));
		}
		else {
		    Vect_reset_cats(Cats);
		    if (unique_cats) {
			Vect_cat_set(Cats, 1, ucat);
			for (n = 0; n < OCats->n_cats; n++) {
			    Vect_cat_set(Cats, 2, OCats->cat[n]);
			}
			ocat = -1;
			Vect_cat_get(ICats, afield, &ocat);

			sprintf(buf,
				"insert into %s values ( %d, %d, %d, %d, \'%s\')",
				Fi->table, ucat, ocat, Centers[pnts1[i - 1].center].cat,
				pnts1[i - 1].iso + 1, isolbl[pnts1[i - 1].iso]);
			db_set_string(&sql, buf);
			G_debug(3, "%s", db_get_string(&sql));

			if (db_execute_immediate(driver, &sql) != DB_OK) {
			    G_fatal_error(_("Cannot insert new record: %s"),
					  db_get_string(&sql));
			}
			ucat++;
		    }
		    else
			Vect_cat_set(Cats, 1, cat);
		    Vect_write_line(&Out, ltype, SPoints, Cats);
		}
	    }
	}
	else {
	    /* arc is not reachable */
	    G_debug(3, "  -> arc is not reachable");
	    Vect_reset_cats(Cats);
	    if (unique_cats) {
		Vect_cat_set(Cats, 1, ucat);
		for (n = 0; n < OCats->n_cats; n++) {
		    Vect_cat_set(Cats, 2, OCats->cat[n]);
		}
		ocat = -1;
		Vect_cat_get(ICats, afield, &ocat);

		sprintf(buf,
			"insert into %s values ( %d, %d, %d, %d, \'%s\')",
			Fi->table, ucat, ocat, -1, 0, "unreachable");
		db_set_string(&sql, buf);
		G_debug(3, "%s", db_get_string(&sql));

		if (db_execute_immediate(driver, &sql) != DB_OK) {
		    G_fatal_error(_("Cannot insert new record: %s"),
				  db_get_string(&sql));
		}
		ucat++;
	    }
	    Vect_write_line(&Out, ltype, Points, Cats);
	}
    }

    if (unique_cats) {
	db_commit_transaction(driver);
	db_close_database_shutdown_driver(driver);

	Vect_copy_table(&Map, &Out, afield, 2, NULL, GV_MTABLE);
    }

    Vect_build(&Out);

    /* Free, ... */
    G_free(Nodes);
    G_free(Centers);
    Vect_close(&Map);
    Vect_close(&Out);

    exit(EXIT_SUCCESS);
}
