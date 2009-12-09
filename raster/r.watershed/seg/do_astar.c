#include <grass/gis.h>
#include <grass/glocale.h>
#include "Gwater.h"
#include "do_astar.h"

double get_slope2(CELL, CELL, double);

int do_astar(void)
{
    int doer, count;
    SHORT upr, upc, r = -1, c = -1, ct_dir;
    CELL alt_val, alt_nbr[8], alt_up;
    CELL asp_val;
    char flag_value, is_in_list, is_worked;
    HEAP_PNT heap_p;

    /* sides
     * |7|1|4|
     * |2| |3|
     * |5|0|6|
     */
    int nbr_ew[8] = { 0, 1, 2, 3, 1, 0, 0, 1 };
    int nbr_ns[8] = { 0, 1, 2, 3, 3, 2, 3, 2 };
    double dx, dy, dist_to_nbr[8], ew_res, ns_res;
    double slope[8];
    int skip_diag;

    G_message(_("SECTION 2: A* Search."));

    for (ct_dir = 0; ct_dir < sides; ct_dir++) {
	/* get r, c (r_nbr, c_nbr) for neighbours */
	upr = nextdr[ct_dir];
	upc = nextdc[ct_dir];
	/* account for rare cases when ns_res != ew_res */
	dy = ABS(upr) * window.ns_res;
	dx = ABS(upc) * window.ew_res;
	if (ct_dir < 4)
	    dist_to_nbr[ct_dir] = dx + dy;
	else
	    dist_to_nbr[ct_dir] = sqrt(dx * dx + dy * dy);
    }
    ew_res = window.ew_res;
    ns_res = window.ns_res;

    if (heap_size == 0)
	G_fatal_error(_("No seeds for A* Search"));

    G_debug(1, "heap size %d, points %d", heap_size, do_points);

    count = 0;

    doer = do_points - 1;

    /* A * Search
     * determine downhill path through all not masked cells and
     * set drainage direction */
    while (heap_size > 0) {
	G_percent(count++, do_points, 1);

	/* drop next point from heap */
	heap_p = drop_pt();

	r = heap_p.pnt.r;
	c = heap_p.pnt.c;
	G_debug(3, "heap size %d, r %d, c %d", heap_size, r, c);

	alt_val = heap_p.ele;

	/* check all neighbours, breadth first search */
	for (ct_dir = 0; ct_dir < sides; ct_dir++) {
	    /* get r, c (upr, upc) for this neighbour */
	    upr = r + nextdr[ct_dir];
	    upc = c + nextdc[ct_dir];
	    slope[ct_dir] = alt_nbr[ct_dir] = 0;
	    /* check that upr, upc are within region */
	    if (upr >= 0 && upr < nrows && upc >= 0 && upc < ncols) {
		/* slope */
		bseg_get(&bitflags, &flag_value, upr, upc);
		is_in_list = FLAG_GET(flag_value, INLISTFLAG);
		is_worked = FLAG_GET(flag_value, WORKEDFLAG);
		skip_diag = 0;
		/* avoid diagonal flow direction bias */
		if (!is_worked) {
		    cseg_get(&alt, &alt_up, upr, upc);
		    alt_nbr[ct_dir] = alt_up;
		    slope[ct_dir] =
			get_slope2(alt_val, alt_nbr[ct_dir],
				   dist_to_nbr[ct_dir]);
		    if (ct_dir > 3 && slope[ct_dir] > 0) {
			if (slope[nbr_ew[ct_dir]] > 0) {
			    /* slope to ew nbr > slope to center */
			    if (slope[ct_dir] <
				get_slope2(alt_nbr[nbr_ew[ct_dir]],
					   alt_nbr[ct_dir], ew_res))
				skip_diag = 1;
			}
			if (!skip_diag && slope[nbr_ns[ct_dir]] > 0) {
			    /* slope to ns nbr > slope to center */
			    if (slope[ct_dir] <
				get_slope2(alt_nbr[nbr_ns[ct_dir]],
					   alt_nbr[ct_dir], ns_res))
				skip_diag = 1;
			}
		    }
		}
		/* put neighbour in search list if not yet in */
		bseg_get(&bitflags, &flag_value, upr, upc);
		if (is_in_list == 0 && skip_diag == 0) {
		    cseg_get(&alt, &alt_up, upr, upc);
		    /* flow direction is set here */
		    asp_val = drain[upr - r + 1][upc - c + 1];
		    add_pt(upr, upc, alt_up, asp_val, 0);
		    cseg_put(&asp, &asp_val, upr, upc);
		}
		/* in list, not worked. is it edge ? */
		else if (is_in_list == 1 && is_worked == 0 &&
			 FLAG_GET(flag_value, EDGEFLAG)) {
		    cseg_get(&asp, &asp_val, upr, upc);
		    if (asp_val < 0) {
			/* adjust flow direction for edge cell */
			asp_val = drain[upr - r + 1][upc - c + 1];
			cseg_put(&asp, &asp_val, upr, upc);
			heap_p.pnt.guessed = 1;
		    }
		}
	    }
	}
	cseg_get(&asp, &asp_val, r, c);
	heap_p.pnt.asp = asp_val;
	seg_put(&astar_pts, (char *)&heap_p.pnt, 0, doer);
	doer--;
	bseg_get(&bitflags, &flag_value, r, c);
	FLAG_SET(flag_value, WORKEDFLAG);
	bseg_put(&bitflags, &flag_value, r, c);

    }
    if (doer != -1)
	G_fatal_error(_("bug in A* Search: doer %d heap size %d count %d"),
		      doer, heap_size, count);

    seg_close(&search_heap);

    G_percent(count, do_points, 1);	/* finish it */

    return 0;
}

/* compare two heap points */
/* return 1 if a < b else 0 */
int cmp_pnt(HEAP_PNT * a, HEAP_PNT * b)
{
    if (a->ele < b->ele)
	return 1;
    else if (a->ele == b->ele) {
	if (a->added < b->added)
	    return 1;
    }
    return 0;
}

/* add point routine for min heap */
int add_pt(SHORT r, SHORT c, CELL ele, char asp, int is_edge)
{
    HEAP_PNT heap_p;
    char flag_value;

    bseg_get(&bitflags, &flag_value, r, c);
    if (is_edge) {
	FLAG_SET(flag_value, EDGEFLAG);
	heap_p.pnt.guessed = 1;
    }
    else {
	heap_p.pnt.guessed = 0;
    }
    FLAG_SET(flag_value, INLISTFLAG);
    bseg_put(&bitflags, &flag_value, r, c);

    /* add point to next free position */

    heap_size++;

    heap_p.added = nxt_avail_pt;
    heap_p.ele = ele;
    heap_p.pnt.r = r;
    heap_p.pnt.c = c;
    heap_p.pnt.asp = asp;

    nxt_avail_pt++;

    /* sift up: move new point towards top of heap */
    sift_up(heap_size, heap_p);

    return 1;
}

/* drop point routine for min heap */
HEAP_PNT drop_pt(void)
{
    int child, childr, parent;
    int i;
    HEAP_PNT child_p, childr_p, last_p, root_p;

    seg_get(&search_heap, (char *)&last_p, 0, heap_size);
    seg_get(&search_heap, (char *)&root_p, 0, 1);

    /* sift down */
    parent = 1;
    while ((child = GET_CHILD(parent)) < heap_size) {
	/* select child with lower ele, if both are equal, older child
	 * older child is older startpoint for flow path, important */

	seg_get(&search_heap, (char *)&child_p, 0, child);
	if (child < heap_size) {
	    childr = child + 1;
	    i = child + 4;
	    while (childr < i && childr < heap_size) {
		/* get smallest child */
		seg_get(&search_heap, (char *)&childr_p, 0, childr);
		if (cmp_pnt(&childr_p, &child_p)) {
		    child = childr;
		    child_p = childr_p;
		}
		childr++;
	    }
	}

	if (cmp_pnt(&last_p, &child_p)) {
	    break;
	}

	/* move hole down */
	seg_put(&search_heap, (char *)&child_p, 0, parent);
	parent = child;
    }

    seg_put(&search_heap, (char *)&last_p, 0, parent);

    /* the actual drop */
    heap_size--;

    return root_p;
}

/* standard sift-up routine for d-ary min heap */
int sift_up(int start, HEAP_PNT child_p)
{
    int parent, child;		/* parentp, */
    HEAP_PNT heap_p;

    child = start;

    while (child > 1) {
	parent = GET_PARENT(child);
	seg_get(&search_heap, (char *)&heap_p, 0, parent);

	/* push parent point down if child is smaller */
	if (cmp_pnt(&child_p, &heap_p)) {
	    seg_put(&search_heap, (char *)&heap_p, 0, child);
	    child = parent;
	}
	/* no more sifting up, found slot for child */
	else
	    break;
    }

    /* add child to heap */
    seg_put(&search_heap, (char *)&child_p, 0, child);

    return 0;
}

double
get_slope(SHORT r, SHORT c, SHORT downr, SHORT downc, CELL ele, CELL downe)
{
    double slope;

    if (r == downr)
	slope = (ele - downe) / window.ew_res;
    else if (c == downc)
	slope = (ele - downe) / window.ns_res;
    else
	slope = (ele - downe) / diag;
    if (slope < MIN_SLOPE)
	return (MIN_SLOPE);
    return (slope);
}

double get_slope2(CELL ele, CELL up_ele, double dist)
{
    if (ele == up_ele)
	return 0.5 / dist;
    else
	return (double)(up_ele - ele) / dist;
}
