/*!
  \file lib/vector/vedit/extend.c

  \brief Vedit library - extend lines (adopted from break.c)

  (C) 2017 by the GRASS Development Team

  This program is free software under the GNU General Public License
  (>=v2).  Read the file COPYING that comes with GRASS for details.

  \author Huidae Cho <grass4u gmail.com>
*/

#include <math.h>
#include <grass/vedit.h>

#define TOL 1e-9

static int extend_lines(struct Map_info *, int, int, int, int, double,
			struct ilist *);
static int find_extended_intersection(double, double, double, double, double,
				      double, double *, double *);

/*!
  \brief Extend lines in given threshold

  \code
  1. Extend first line only
          \                      \
     id1   \             ->       \
                                   \
     id2 ----------            -----+----


  2. Extend both lines
          \                      \
     id1   \             ->       \
                                   \
     id2        ---                 +----


  3. Extend first line when both are on the same line
     id1 ---    --- id2  ->    -----+----


  4. Connect two parallel lines (parallel=1)
     id1 ------                -------
                         ->         /
     id2     ------                +-----


  5. Don't connect two parallel lines (parallel=0)
     id1 ------                ------
                         ->
     id2     ------                ------
  \endcode

  \param Map pointer to Map_info
  \param List list of selected lines
  \param nodes 1 for start node, 2 for end node, other for both
  \param parallel connect parallel lines
  \param thresh threshold value

  \return number of modified lines
 */
int Vedit_extend_lines(struct Map_info *Map, struct ilist *List, int nodes,
		       int parallel, double thresh)
{
    int nlines_modified, extended;
    int i, j, node[2], first_node, n_nodes;
    int line, found;
    double x, y, z;

    struct ilist *List_exclude, *List_found;

    nlines_modified = 0;

    List_exclude = Vect_new_list();
    List_found = Vect_new_list();

    first_node = 0;
    n_nodes = 2;

    switch (nodes) {
	case 1:
	    n_nodes = 1;
	    break;
	case 2:
	    first_node = 1;
	    break;
    }

    /* collect lines to be modified */
    for (i = 0; i < List->n_values; i++) {
	line = List->value[i];

	if (!Vect_line_alive(Map, line))
	    continue;

	if (Vect_get_line_type(Map, line) & GV_POINTS)
	    continue;

	node[0] = node[1] = -1;
	Vect_get_line_nodes(Map, line, &(node[0]), &(node[1]));
	if (node[0] < 0 || node[1] < 0)
	    continue;

	extended = 0;
	Vect_reset_list(List_exclude);
	Vect_list_append(List_exclude, line);
	for (j = first_node; j < n_nodes && !extended; j++) {
	    /* for each line node find lines in threshold */
	    Vect_get_node_coor(Map, node[j], &x, &y, &z);

	    do {
		/* find first nearest line */
		found = Vect_find_line_list(Map, x, y, z,
					    GV_LINES, thresh, WITHOUT_Z,
					    List_exclude, List_found);

		if (found > 0 && Vect_line_alive(Map, found)) {
		    /* try to extend lines (given node) */
		    G_debug(3, "Vedit_extend_lines(): lines=%d,%d", line, found);
		    if (extend_lines(Map, !j, line, found, parallel, thresh,
				     List)) {
			G_debug(3, "Vedit_extend_lines(): lines=%d,%d -> extended",
				line, found);
			nlines_modified += 2;
			extended = 1;
		    }
		}

		Vect_list_append(List_exclude, found);
	    } while(List_found->n_values > 0 && !extended);
	}
    }

    Vect_destroy_list(List_exclude);
    Vect_destroy_list(List_found);

    return nlines_modified;
}

int extend_lines(struct Map_info *Map, int first, int line_from, int line_to,
		 int parallel, double thresh, struct ilist *List)
{
    /* TODO: If line_from extends to the i'th segment of line_to but the
     * line_from node is closest to the j'th segment of line_to, this function
     * wouldn't work because it only checks intersection of the start/end
     * segment of line_from and the closest segment of line_to (i'th segment).
     */
    int line_new;
    int type_from, type_to;
    int n_points, seg, is;
    double x, y, px, py, x1, y1;
    double dist, spdist, lpdist, length;
    double angle_t, angle_f;

    struct line_pnts *Points_from, *Points_to, *Points_final;
    struct line_cats *Cats_from, *Cats_to;

    Points_from = Vect_new_line_struct();
    Points_to = Vect_new_line_struct();
    Points_final = Vect_new_line_struct();
    Cats_from = Vect_new_cats_struct();
    Cats_to = Vect_new_cats_struct();

    type_from = Vect_read_line(Map, Points_from, Cats_from, line_from);
    type_to = Vect_read_line(Map, Points_to, Cats_to, line_to);

    line_new = 0;
    if (!(type_from & GV_LINES) || !(type_to & GV_LINES))
	line_new = -1;

    /* avoid too much indentation */
    do {
	if (line_new == -1)
	    break;

	n_points = Points_from->n_points - 1;

	if (first) {
	    x = Points_from->x[0];
	    y = Points_from->y[0];
	}
	else {
	    x = Points_from->x[n_points];
	    y = Points_from->y[n_points];
	}
	seg = Vect_line_distance(Points_to, x, y, 0.0, WITHOUT_Z,
				 &px, &py, NULL, &dist, &spdist, &lpdist);

	if (!(seg > 0 && dist > 0.0 && (thresh < 0. || dist <= thresh)))
	    break;

	/* lines in threshold */
	length = first ? 0 : Vect_line_length(Points_from);

	/* find angles */
	if (!Vect_point_on_line(Points_from, length, NULL, NULL, NULL, &angle_f,
			       NULL) ||
	    !Vect_point_on_line(Points_to, lpdist, NULL, NULL, NULL, &angle_t,
			       NULL))
	    break;

	/* extend both lines and find intersection */
	if (!find_extended_intersection(x, y, angle_f, px, py, angle_t,
					&x1, &y1)) {
	    if (!parallel)
		break;

	    /* parallel lines */
	    x1 = px;
	    y1 = py;
	    if (first)
		Vect_line_insert_point(Points_from, 0, x1, y1, 0.0);
	    else
		Vect_append_point(Points_from, x1, y1, 0.0);
	} else {
	    /* if intersection point lies on line_from or is beyond threshold,
	     * skip */
	    /* TODO: Get rid of tolerance */
	    if (!Vect_line_distance(Points_from, x1, y1, 0.0, WITHOUT_Z, NULL,
				    NULL, NULL, &dist, NULL, NULL) ||
		dist <= TOL || dist > thresh)
		break;

	    /* lines extended -> extend/split line_to */
	    /* update line_from */
	    if (first) {
		Points_from->x[0] = x1;
		Points_from->y[0] = y1;
	    } else {
		Points_from->x[n_points] = x1;
		Points_from->y[n_points] = y1;
	    }
	}

	line_new = Vect_rewrite_line(Map, line_from, type_from, Points_from,
				     Cats_from);
	/* Vect_list_append(List, line_new); */

	length = Vect_line_length(Points_to);
	Vect_reset_line(Points_final);
	if (lpdist == 0.0) {
	    /* extend line_to start node */
	    Vect_append_point(Points_final, x1, y1, 0.0);
	    for (is = 0; is < Points_to->n_points; is++)
		Vect_append_point(Points_final, Points_to->x[is],
				  Points_to->y[is], Points_to->z[is]);
	    line_new = Vect_rewrite_line(Map, line_to, type_to, Points_final,
					 Cats_to);
	} else if (lpdist == length) {
	    /* extend line_to end node */
	    for (is = 0; is < Points_to->n_points; is++)
		Vect_append_point(Points_final, Points_to->x[is],
				  Points_to->y[is], Points_to->z[is]);
	    Vect_append_point(Points_final, x1, y1, 0.0);
	    line_new = Vect_rewrite_line(Map, line_to, type_to, Points_final,
					 Cats_to);
	} else {
	    /* break line_to */
	    /* update line_to  -- first part */
	    for (is = 0; is < seg; is++)
		Vect_append_point(Points_final, Points_to->x[is],
				  Points_to->y[is], Points_to->z[is]);
	    Vect_append_point(Points_final, x1, y1, 0.0);
	    line_new = Vect_rewrite_line(Map, line_to, type_to, Points_final,
					 Cats_to);
	    /* Vect_list_append(List, line_new); */

	    /* write second part */
	    Vect_reset_line(Points_final);
	    Vect_append_point(Points_final, x1, y1, 0.0);
	    for (is = seg; is < Points_to->n_points; is++)
		Vect_append_point(Points_final, Points_to->x[is],
				  Points_to->y[is], Points_to->z[is]);

	    /* rewrite first part */
	    line_new = Vect_write_line(Map, type_to, Points_final, Cats_to);
	    /* Vect_list_append(List, line_new); */
	}
    } while(0);

    Vect_destroy_line_struct(Points_from);
    Vect_destroy_line_struct(Points_to);
    Vect_destroy_line_struct(Points_final);
    Vect_destroy_cats_struct(Cats_from);
    Vect_destroy_cats_struct(Cats_to);

    return line_new > 0 ? 1 : 0;
}

static int find_extended_intersection(double x1, double y1, double angle1,
				      double x2, double y2, double angle2,
				      double *x, double *y)
{
    double c1, s1, c2, s2, d, a;

    if (fabs(sin(angle1 - angle2)) <= TOL) {
	/* two lines are parallel */
	double angle;

	angle = atan2(y2 - y1, x2 - x1);
	if (fabs(sin(angle - angle1)) <= TOL) {
	    /* they are on the same line */
	    *x = x2;
	    *y = y2;

	    return 1;
	}

	/* two lines don't intersect */
	return 0;
    }

    c1 = cos(angle1);
    s1 = sin(angle1);
    c2 = cos(angle2);
    s2 = sin(angle2);
    d = -c1 * s2 + c2 * s1;
    if (d == 0.0)
	/* shouldn't happen again */
	return 0;

    a = (-s2 * (x2 - x1) + c2 * (y2 - y1)) / d;
    *x = x1 + a * c1;
    *y = y1 + a * s1;

    return 1;
}
