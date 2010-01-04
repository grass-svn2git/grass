#include <stdlib.h>
#include <string.h>
#include "Gwater.h"
#include <grass/gis.h>
#include <grass/raster.h>
#include <grass/glocale.h>

int ele_round(double);

int init_vars(int argc, char *argv[])
{
    SHORT r, c;
    int ele_fd, fd, wat_fd;
    int seg_rows, seg_cols, num_cseg_total, num_open_segs, num_open_array_segs;

    /* int page_block, num_cseg; */
    int max_bytes;
    CELL *buf, alt_value, asp_value, block_value;
    char worked_value, flag_value;
    DCELL wat_value;
    DCELL dvalue;
    WAT_ALT wa;
    char MASK_flag;
    void *elebuf, *ptr, *watbuf, *watptr;
    int ele_map_type, wat_map_type;
    size_t ele_size, wat_size;
    CELL cellone = 1;
    int ct_dir, r_nbr, c_nbr;

    G_gisinit(argv[0]);
    ele_flag = wat_flag = asp_flag = pit_flag = run_flag = ril_flag = 0;
    st_flag = bas_flag = seg_flag = haf_flag = arm_flag = dis_flag = 0;
    ob_flag = sl_flag = sg_flag = ls_flag = er_flag = bas_thres = 0;
    nxt_avail_pt = 0;
    /* dep_flag = 0; */
    max_length = d_zero = 0.0;
    d_one = 1.0;
    ril_value = -1.0;
    /* dep_slope = 0.0; */
    max_bytes = 0;
    sides = 8;
    mfd = 1;
    c_fac = 5;
    abs_acc = 0;
    ele_scale = 1;
    segs_mb = 300;
    /* scan options */
    for (r = 1; r < argc; r++) {
	if (sscanf(argv[r], "elevation=%s", ele_name) == 1)
	    ele_flag++;
	else if (sscanf(argv[r], "accumulation=%s", wat_name) == 1)
	    wat_flag++;
	else if (sscanf(argv[r], "drainage=%s", asp_name) == 1)
	    asp_flag++;
	else if (sscanf(argv[r], "depression=%s", pit_name) == 1)
	    pit_flag++;
	else if (sscanf(argv[r], "threshold=%d", &bas_thres) == 1) ;
	else if (sscanf(argv[r], "max_slope_length=%lf", &max_length) == 1) ;
	else if (sscanf(argv[r], "basin=%s", bas_name) == 1)
	    bas_flag++;
	else if (sscanf(argv[r], "stream=%s", seg_name) == 1)
	    seg_flag++;
	else if (sscanf(argv[r], "half_basin=%s", haf_name) == 1)
	    haf_flag++;
	else if (sscanf(argv[r], "flow=%s", run_name) == 1)
	    run_flag++;
	else if (sscanf(argv[r], "ar=%s", arm_name) == 1)
	    arm_flag++;
	/* slope length
	else if (sscanf(argv[r], "slope_length=%s", sl_name) == 1)
	    sl_flag++; */
	else if (sscanf(argv[r], "slope_steepness=%s", sg_name) == 1)
	    sg_flag++;
	else if (sscanf(argv[r], "length_slope=%s", ls_name) == 1)
	    ls_flag++;
	else if (sscanf(argv[r], "blocking=%s", ob_name) == 1)
	    ob_flag++;
	else if (sscanf(argv[r], "memory=%lf", &segs_mb) == 1) ;
	else if (sscanf(argv[r], "disturbed_land=%s", ril_name) == 1) {
	    if (sscanf(ril_name, "%lf", &ril_value) == 0) {
		ril_value = -1.0;
		ril_flag++;
	    }
	}
	/* slope deposition
	else if (sscanf (argv[r], "sd=%[^\n]", dep_name) == 1) dep_flag++; */
	else if (sscanf(argv[r], "-%d", &sides) == 1) {
	    if (sides != 4)
		usage(argv[0]);
	}
	else if (sscanf(argv[r], "convergence=%d", &c_fac) == 1) ;
	else if (strcmp(argv[r], "-s") == 0)
	    mfd = 0;
	else if (strcmp(argv[r], "-a") == 0)
	    abs_acc = 1;
	else
	    usage(argv[0]);
    }
    /* check options */
    if (mfd == 1 && (c_fac < 1 || c_fac > 10)) {
	G_fatal_error("Convergence factor must be between 1 and 10.");
    }
    if ((ele_flag != 1)
	||
	((arm_flag == 1) &&
	 ((bas_thres <= 0) || ((haf_flag != 1) && (bas_flag != 1))))
	||
	((bas_thres <= 0) &&
	 ((bas_flag == 1) || (seg_flag == 1) || (haf_flag == 1) ||
	  (sl_flag == 1) || (sg_flag == 1) || (ls_flag == 1)))
	)
	usage(argv[0]);
    tot_parts = 4;
    if (sl_flag || sg_flag || ls_flag)
	er_flag = 1;
    /* do RUSLE */
    if (er_flag)
	tot_parts++;
    /* do stream extraction */
    if (er_flag || seg_flag || bas_flag || haf_flag) {
	st_flag = 1;
	/* separate stream extraction only needed for MFD */
	if (mfd)
	    tot_parts++;
    }
    /* define basins */
    if (seg_flag || bas_flag || haf_flag)
	tot_parts++;

    G_message(_("SECTION 1 beginning: Initiating Variables. %d sections total."),
	      tot_parts);

    this_mapset = G_mapset();
    /* for sd factor
       if (dep_flag)        {
       if (sscanf (dep_name, "%lf", &dep_slope) != 1)       {
       dep_flag = -1;
       }
       }
     */
    G_get_set_window(&window);
    nrows = G_window_rows();
    ncols = G_window_cols();
    if (max_length <= d_zero)
	max_length = 10 * nrows * window.ns_res + 10 * ncols * window.ew_res;
    if (window.ew_res < window.ns_res)
	half_res = .5 * window.ew_res;
    else
	half_res = .5 * window.ns_res;
    diag = sqrt(window.ew_res * window.ew_res +
		window.ns_res * window.ns_res);
    if (sides == 4)
	diag *= 0.5;

    /* segment parameters: one size fits all. Fine tune? */
    /* Segment rows and cols: 64 */
    /* 1 segment open for all data structures used in A* Search: 0.18 MB */
    /* is really 0.22 MB but search heap holds max 5% of all points
     * i.e. we will probably never need all open segments for search heap
     */

    seg_rows = SROW;
    seg_cols = SCOL;

    if (segs_mb < 3.0) {
	segs_mb = 300;
	G_warning(_("Maximum memory to be used was smaller than 3 MB,"
	            " set to default = 300 MB."));
    }

    num_open_segs = segs_mb / 0.18;

    G_debug(1, "segs MB: %.0f", segs_mb);
    G_debug(1, "region rows: %d", nrows);
    G_debug(1, "seg rows: %d", seg_rows);
    G_debug(1, "region cols: %d", ncols);
    G_debug(1, "seg cols: %d", seg_cols);

    num_cseg_total = nrows / SROW + 1;
    G_debug(1, "   row segments:\t%d", num_cseg_total);

    num_cseg_total = ncols / SCOL + 1;
    G_debug(1, "column segments:\t%d", num_cseg_total);

    num_cseg_total = (ncols / seg_cols + 1) * (nrows / seg_rows + 1);
    G_debug(1, " total segments:\t%d", num_cseg_total);
    G_debug(1, "  open segments:\t%d", num_open_segs);

    /* nonsense to have more segments open than exist */
    if (num_open_segs > num_cseg_total)
	num_open_segs = num_cseg_total;
    G_debug(1, "  open segments after adjusting:\t%d", num_open_segs);

    if (num_cseg_total * 0.18 < 1024.0)
	G_verbose_message(_("Will need up to %.2f MB of disk space"), num_cseg_total * 0.18);
    else
	G_verbose_message(_("Will need up to %.2f GB (%.2f MB) of disk space"),
	           (num_cseg_total * 0.18) / 1024.0, num_cseg_total * 0.18);

    if (er_flag) {
	cseg_open(&r_h, seg_rows, seg_cols, num_open_segs);
	cseg_read_cell(&r_h, ele_name, "");
    }
    
    /* read elevation input and mark NULL/masked cells */

    /* scattered access: alt, watalt, listflag, asp */
    cseg_open(&alt, seg_rows, seg_cols, num_open_segs);
    seg_open(&watalt, nrows, ncols, seg_rows, seg_cols, num_open_segs, sizeof(WAT_ALT));
    bseg_open(&bitflags, seg_rows, seg_cols, num_open_segs);
    cseg_open(&asp, seg_rows, seg_cols, num_open_segs);

    /* open elevation input */
    ele_fd = Rast_open_old(ele_name, "");

    ele_map_type = Rast_get_map_type(ele_fd);
    ele_size = Rast_cell_size(ele_map_type);
    elebuf = Rast_allocate_buf(ele_map_type);

    if (ele_map_type == FCELL_TYPE || ele_map_type == DCELL_TYPE)
	ele_scale = 1000; 	/* should be enough to do the trick */

    /* initial flow accumulation */
    if (run_flag) {
	wat_fd = Rast_open_old(run_name, "");

	wat_map_type = Rast_get_map_type(ele_fd);
	wat_size = Rast_cell_size(ele_map_type);
	watbuf = Rast_allocate_buf(ele_map_type);
    }
    else {
	watbuf = watptr = NULL;
	wat_fd = wat_size = wat_map_type = -1;
    }

    /* read elevation input and mark NULL/masked cells */
    G_message("SECTION 1a: Mark masked and NULL cells");
    MASK_flag = 0;
    do_points = nrows * ncols;
    for (r = 0; r < nrows; r++) {
	G_percent(r, nrows, 1);
	Rast_get_row(ele_fd, elebuf, r, ele_map_type);
	ptr = elebuf;

	if (run_flag) {
	    Rast_get_row(wat_fd, watbuf, r, wat_map_type);
	    watptr = watbuf;
	}
	
	for (c = 0; c < ncols; c++) {

	    flag_value = 0;

	    /* check for masked and NULL cells */
	    if (Rast_is_null_value(ptr, ele_map_type)) {
		FLAG_SET(flag_value, NULLFLAG);
		FLAG_SET(flag_value, INLISTFLAG);
		FLAG_SET(flag_value, WORKEDFLAG);
		Rast_set_c_null_value(&alt_value, 1);
		/* flow accumulation */
		Rast_set_d_null_value(&wat_value, 1);
		do_points--;
	    }
	    else {
		if (ele_map_type == CELL_TYPE) {
		    alt_value = *((CELL *)ptr);
		}
		else if (ele_map_type == FCELL_TYPE) {
		    dvalue = *((FCELL *)ptr);
		    dvalue *= ele_scale;
		    alt_value = ele_round(dvalue);
		}
		else if (ele_map_type == DCELL_TYPE) {
		    dvalue = *((DCELL *)ptr);
		    dvalue *= ele_scale;
		    alt_value = ele_round(dvalue);
		}

		/* flow accumulation */
		if (run_flag) {
		    if (Rast_is_null_value(watptr, wat_map_type)) {
			wat_value = 0;    /* ok ? */
		    }
		    else {
			if (wat_map_type == CELL_TYPE) {
			    wat_value = *((CELL *)ptr);
			}
			else if (wat_map_type == FCELL_TYPE) {
			    wat_value = *((FCELL *)ptr);
			}
			else if (ele_map_type == DCELL_TYPE) {
			    wat_value = *((DCELL *)ptr);
			}
		    }
		}
		else {
		    wat_value = 1;
		}

	    }
	    cseg_put(&alt, &alt_value, r, c);
	    wa.wat = wat_value;
	    wa.ele = alt_value;
	    seg_put(&watalt, (char *)&wa, r, c);

	    if (flag_value)
		bseg_put(&bitflags, &flag_value, r, c);
	    
	    if (er_flag) {
		cseg_put(&r_h, &alt_value, r, c);
	    }
	    ptr = G_incr_void_ptr(ptr, ele_size);
	    if (run_flag) {
		watptr = G_incr_void_ptr(watptr, wat_size);
	    }
	}
    }
    G_percent(nrows, nrows, 1);    /* finish it */
    Rast_close(ele_fd);
    G_free(elebuf);
    
    if (run_flag) {
	Rast_close(wat_fd);
	G_free(watbuf);
    }

    if (do_points < nrows * ncols)
	MASK_flag = 1;
    
    /* depression: drainage direction will be set to zero later */
    if (pit_flag) {
	fd = Rast_open_old(pit_name, "");
	buf = Rast_allocate_c_buf();
	for (r = 0; r < nrows; r++) {
	    G_percent(r, nrows, 1);
	    Rast_get_c_row(fd, buf, r);
	    for (c = 0; c < ncols; c++) {
		asp_value = buf[c];
		if (!Rast_is_c_null_value(&asp_value) && asp_value) {
		    cseg_put(&asp, &cellone, r, c);
		    bseg_get(&bitflags, &flag_value, r, c);
		    FLAG_SET(flag_value, PITFLAG);
		    bseg_put(&bitflags, &flag_value, r, c);
		}
	    }
	}
	G_percent(nrows, nrows, 1);    /* finish it */
	Rast_close(fd);
	G_free(buf);
    }

    /* do RUSLE */
    if (er_flag) {
	if (ob_flag) {
	    fd = Rast_open_old(ob_name, "");
	    buf = Rast_allocate_c_buf();
	    for (r = 0; r < nrows; r++) {
		G_percent(r, nrows, 1);
		Rast_get_c_row(fd, buf, r);
		for (c = 0; c < ncols; c++) {
		    block_value = buf[c];
		    if (!Rast_is_c_null_value(&block_value) && block_value) {
			bseg_get(&bitflags, &flag_value, r, c);
			FLAG_SET(flag_value, RUSLEBLOCKFLAG);
			bseg_put(&bitflags, &flag_value, r, c);
		    }
		}
	    }
	    G_percent(nrows, nrows, 1);    /* finish it */
	    Rast_close(fd);
	    G_free(buf);
	}

	if (ril_flag) {
	    dseg_open(&ril, 1, seg_rows * seg_cols, num_open_segs);
	    dseg_read_cell(&ril, ril_name, "");
	}
	
	/* dseg_open(&slp, SROW, SCOL, num_open_segs); */

	    dseg_open(&s_l, seg_rows, seg_cols, num_open_segs);
	if (sg_flag)
	    dseg_open(&s_g, 1, seg_rows * seg_cols, num_open_segs);
	if (ls_flag)
	    dseg_open(&l_s, 1, seg_rows * seg_cols, num_open_segs);
    }

    G_debug(1, "open segments for A* points");
    /* rounded down power of 2 */
    seg_cols = (int) (pow(2, (int)(log(num_open_segs / 8.0) / log(2) + 0.1)) + 0.1);
    num_open_array_segs = num_open_segs / seg_cols;
    /* n cols in segment */
    seg_cols *= seg_rows * seg_rows;
    /* n segments in row */
    num_cseg_total = do_points / seg_cols;
    if (do_points % seg_cols > 0)
	num_cseg_total++;
    /* no need to have more segments open than exist */
    if (num_open_array_segs > num_cseg_total)
	num_open_array_segs = num_cseg_total;

    if (num_open_array_segs > 4)
	num_open_array_segs = 4;
    
    seg_open(&astar_pts, 1, do_points, 1, seg_cols, num_open_array_segs,
	     sizeof(POINT));

    /* one-based d-ary search_heap with astar_pts */
    G_debug(1, "open segments for A* search heap");
    /* rounded down power of 2 */
    seg_cols = (int) (pow(2, (int)(log(num_open_segs / 8.0) / log(2) + 0.1)) + 0.1);
    num_open_array_segs = num_open_segs / seg_cols;
    /* n cols in segment */
    seg_cols *= seg_rows * seg_rows;
    /* n segments in row */
    num_cseg_total = (do_points + 1) / seg_cols;
    if ((do_points + 1) % seg_cols > 0)
	num_cseg_total++;
    /* no need to have more segments open than exist */
    if (num_open_array_segs > num_cseg_total)
	num_open_array_segs = num_cseg_total;

    G_debug(1, "A* search heap open segments %d, target 8", num_open_array_segs);
    /* the search heap will not hold more than 5% of all points at any given time ? */
    /* chances are good that the heap will fit into one large segment */
    seg_open(&search_heap, 1, do_points + 1, 1, seg_cols,
	     num_open_array_segs, sizeof(HEAP_PNT));

    G_message(_("SECTION 1b: Determining Offmap Flow."));

    /* heap is empty */
    heap_size = 0;

    first_astar = first_cum = -1;

    if (MASK_flag) {
	for (r = 0; r < nrows; r++) {
	    G_percent(r, nrows, 1);
	    for (c = 0; c < ncols; c++) {
		bseg_get(&bitflags, &flag_value, r, c);
		if (!FLAG_GET(flag_value, NULLFLAG)) {
		    if (er_flag)
			dseg_put(&s_l, &half_res, r, c);
		    cseg_get(&asp, &asp_value, r, c);
		    if (r == 0 || c == 0 || r == nrows - 1 ||
			c == ncols - 1 || asp_value != 0) {
			/* dseg_get(&wat, &wat_value, r, c); */
			seg_get(&watalt, (char *)&wa, r, c);
			wat_value = wa.wat;
			if (wat_value > 0) {
			    wat_value = -wat_value;
			    /* dseg_put(&wat, &wat_value, r, c); */
			    wa.wat = wat_value;
			    seg_put(&watalt, (char *)&wa, r, c);
			}
			/* set depression */
			if (asp_value) {
			    asp_value = 0;
			    if (wat_value < 0) {
				wat_value = -wat_value;
				/* dseg_put(&wat, &wat_value, r, c); */
				wa.wat = wat_value;
				seg_put(&watalt, (char *)&wa, r, c);
			    }
			}
			else if (r == 0)
			    asp_value = -2;
			else if (c == 0)
			    asp_value = -4;
			else if (r == nrows - 1)
			    asp_value = -6;
			else if (c == ncols - 1)
			    asp_value = -8;
			if (-1 == cseg_put(&asp, &asp_value, r, c))
			    exit(EXIT_FAILURE);
			/* cseg_get(&alt, &alt_value, r, c); */
			alt_value = wa.ele;
			add_pt(r, c, alt_value, asp_value, 1);
		    }
		    else {
			seg_get(&watalt, (char *)&wa, r, c);
			for (ct_dir = 0; ct_dir < sides; ct_dir++) {
			    /* get r, c (r_nbr, c_nbr) for neighbours */
			    r_nbr = r + nextdr[ct_dir];
			    c_nbr = c + nextdc[ct_dir];

			    bseg_get(&bitflags, &worked_value, r_nbr, c_nbr);
			    if (FLAG_GET(worked_value, NULLFLAG)) {
				asp_value = -1 * drain[r - r_nbr + 1][c - c_nbr + 1];
				add_pt(r, c, wa.ele, asp_value, 1);
				cseg_put(&asp, &asp_value, r, c);
				wat_value = wa.wat;
				if (wat_value > 0) {
				    wa.wat = -wat_value;
				    seg_put(&watalt, (char *)&wa, r, c);
				}
				break;
			    }
			}
		    }
		}  /* end non-NULL cell */
	    }  /* end column */
	}
    }
    else {
	for (r = 0; r < nrows; r++) {
	    G_percent(r, nrows, 1);
	    for (c = 0; c < ncols; c++) {
		/* bseg_put(&worked, &zero, r, c); */
		if (er_flag)
		    dseg_put(&s_l, &half_res, r, c);
		cseg_get(&asp, &asp_value, r, c);
		if (r == 0 || c == 0 || r == nrows - 1 ||
		    c == ncols - 1 || asp_value != 0) {
		    seg_get(&watalt, (char *)&wa, r, c);
		    wat_value = wa.wat;
		    if (wat_value > 0) {
			wat_value = -wat_value;
			wa.wat = wat_value;
			seg_put(&watalt, (char *)&wa, r, c);
		    }
		    /* set depression */
		    if (asp_value) {
			asp_value = 0;
			if (wat_value < 0) {
			    wat_value = -wat_value;
			    wa.wat = wat_value;
			    seg_put(&watalt, (char *)&wa, r, c);
			}
		    }
		    else if (r == 0)
			asp_value = -2;
		    else if (c == 0)
			asp_value = -4;
		    else if (r == nrows - 1)
			asp_value = -6;
		    else if (c == ncols - 1)
			asp_value = -8;
		    if (-1 == cseg_put(&asp, &asp_value, r, c))
			exit(EXIT_FAILURE);
		    /* cseg_get(&alt, &alt_value, r, c); */
		    add_pt(r, c, wa.ele, asp_value, 1);
		}
	    }
	}
    }
    G_percent(r, nrows, 1);	/* finish it */

    return 0;
}

int ele_round(double x)
{
    int n;

    if (x >= 0.0)
	n = x + .5;
    else {
	n = -x + .5;
	n = -n;
    }

    return n;
}
