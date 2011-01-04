
/***********************************************************************
* MODULE:       R-Tree library 
*              
* AUTHOR(S):    Antonin Guttman - original code
*               Daniel Green (green@superliminal.com) - major clean-up
*                               and implementation of bounding spheres
*               Markus Metz - file-based and memory-based R*-tree
*               
* PURPOSE:      Multidimensional index
*
* COPYRIGHT:    (C) 2001 by the GRASS Development Team
*
*               This program is free software under the GNU General 
* 		Public License (>=v2). Read the file COPYING that comes 
* 		with GRASS for details.
* 
***********************************************************************/

#include <stdio.h>
#include <assert.h>
#include <float.h>
#include "index.h"
#include "card.h"
#include "split.h"

#ifndef DBL_MAX
#define DBL_MAX 1.797693E308  /* DBL_MAX approximation */
#endif

struct Branch BranchBuf[MAXCARD + 1];
int BranchCount;
struct Rect CoverSplit;
RectReal CoverSplitArea;

/* variables for finding a partition */
struct PartitionVars Partitions[1];

/*----------------------------------------------------------------------
| Load branch buffer with branches from full node plus the extra branch.
----------------------------------------------------------------------*/
static void RTreeGetBranches(struct Node *n, struct Branch *b,
			     struct RTree *t)
{
    int i, maxkids = 0;

    if ((n)->level > 0) {
	maxkids = t->nodecard;
	/* load the branch buffer */
	for (i = 0; i < maxkids; i++) {
	    assert(t->valid_child(&(n->branch[i].child)));	/* n should have every entry full */
	    BranchBuf[i] = n->branch[i];
	}
    }
    else {
	maxkids = t->leafcard;
	/* load the branch buffer */
	for (i = 0; i < maxkids; i++) {
	    assert(n->branch[i].child.id);	/* n should have every entry full */
	    BranchBuf[i] = n->branch[i];
	}
    }

    BranchBuf[maxkids] = *b;
    BranchCount = maxkids + 1;

    if (METHOD == 0) { /* quadratic split */
	/* calculate rect containing all in the set */
	CoverSplit = BranchBuf[0].rect;
	for (i = 1; i < maxkids + 1; i++) {
	    CoverSplit = RTreeCombineRect(&CoverSplit, &BranchBuf[i].rect, t);
	}
	CoverSplitArea = RTreeRectSphericalVolume(&CoverSplit, t);
    }

    RTreeInitNode(n, NODETYPE(n->level, t->fd));
}

/*----------------------------------------------------------------------
| Put a branch in one of the groups.
----------------------------------------------------------------------*/
static void RTreeClassify(int i, int group, struct PartitionVars *p,
			  struct RTree *t)
{
    assert(!p->taken[i]);

    p->partition[i] = group;
    p->taken[i] = TRUE;

    if (METHOD == 0) {
	if (p->count[group] == 0)
	    p->cover[group] = BranchBuf[i].rect;
	else
	    p->cover[group] =
		RTreeCombineRect(&BranchBuf[i].rect, &p->cover[group], t);
	p->area[group] = RTreeRectSphericalVolume(&p->cover[group], t);
    }
    p->count[group]++;
}

/***************************************************
 *                                                 *
 *    Toni Guttman's quadratic splitting method    *
 *                                                 *
 ***************************************************/

/*----------------------------------------------------------------------
| Pick two rects from set to be the first elements of the two groups.
| Pick the two that waste the most area if covered by a single
| rectangle.
----------------------------------------------------------------------*/
static void RTreePickSeeds(struct PartitionVars *p, struct RTree *t)
{
    int i, j, seed0 = 0, seed1 = 0;
    RectReal worst, waste, area[MAXCARD + 1];

    for (i = 0; i < p->total; i++)
	area[i] = RTreeRectSphericalVolume(&BranchBuf[i].rect, t);

    worst = -CoverSplitArea - 1;
    for (i = 0; i < p->total - 1; i++) {
	for (j = i + 1; j < p->total; j++) {
	    struct Rect one_rect;

	    one_rect = RTreeCombineRect(&BranchBuf[i].rect,
					&BranchBuf[j].rect, t);
	    waste =
		RTreeRectSphericalVolume(&one_rect, t) - area[i] - area[j];
	    if (waste > worst) {
		worst = waste;
		seed0 = i;
		seed1 = j;
	    }
	}
    }
    RTreeClassify(seed0, 0, p, t);
    RTreeClassify(seed1, 1, p, t);
}

/*----------------------------------------------------------------------
| Copy branches from the buffer into two nodes according to the
| partition.
----------------------------------------------------------------------*/
static void RTreeLoadNodes(struct Node *n, struct Node *q,
			   struct PartitionVars *p, struct RTree *t)
{
    int i;

    for (i = 0; i < p->total; i++) {
	assert(p->partition[i] == 0 || p->partition[i] == 1);
	if (p->partition[i] == 0)
	    RTreeAddBranch(&BranchBuf[i], n, NULL, NULL, NULL, NULL, t);
	else if (p->partition[i] == 1)
	    RTreeAddBranch(&BranchBuf[i], q, NULL, NULL, NULL, NULL, t);
    }
}

/*----------------------------------------------------------------------
| Initialize a PartitionVars structure.
----------------------------------------------------------------------*/
void RTreeInitPVars(struct PartitionVars *p, int maxrects, int minfill)
{
    int i;

    p->count[0] = p->count[1] = 0;
    p->cover[0] = p->cover[1] = RTreeNullRect();
    p->area[0] = p->area[1] = (RectReal) 0;
    p->total = maxrects;
    p->minfill = minfill;
    for (i = 0; i < maxrects; i++) {
	p->taken[i] = FALSE;
	p->partition[i] = -1;
    }
}

/*----------------------------------------------------------------------
| Print out data for a partition from PartitionVars struct.
| Unused, for debugging only
----------------------------------------------------------------------*/
static void RTreePrintPVars(struct PartitionVars *p)
{
    int i;

    fprintf(stdout, "\npartition:\n");
    for (i = 0; i < p->total; i++) {
	fprintf(stdout, "%3d\t", i);
    }
    fprintf(stdout, "\n");
    for (i = 0; i < p->total; i++) {
	if (p->taken[i])
	    fprintf(stdout, "  t\t");
	else
	    fprintf(stdout, "\t");
    }
    fprintf(stdout, "\n");
    for (i = 0; i < p->total; i++) {
	fprintf(stdout, "%3d\t", p->partition[i]);
    }
    fprintf(stdout, "\n");

    fprintf(stdout, "count[0] = %d  area = %f\n", p->count[0], p->area[0]);
    fprintf(stdout, "count[1] = %d  area = %f\n", p->count[1], p->area[1]);
    if (p->area[0] + p->area[1] > 0) {
	fprintf(stdout, "total area = %f  effectiveness = %3.2f\n",
		p->area[0] + p->area[1],
		(float)CoverSplitArea / (p->area[0] + p->area[1]));
    }
    fprintf(stdout, "cover[0]:\n");
    RTreePrintRect(&p->cover[0], 0);

    fprintf(stdout, "cover[1]:\n");
    RTreePrintRect(&p->cover[1], 0);
}

/*----------------------------------------------------------------------
| Method #0 for choosing a partition: this is Toni Guttman's quadratic
| split
|
| As the seeds for the two groups, pick the two rects that would waste
| the most area if covered by a single rectangle, i.e. evidently the 
| worst pair to have in the same group. Of the remaining, one at a time 
| is chosen to be put in one of the two groups. The one chosen is the 
| one with the greatest difference in area expansion depending on which
| group - the rect most strongly attracted to one group and repelled
| from the other. If one group gets too full (more would force other 
| group to violate min fill requirement) then other group gets the rest.
| These last are the ones that can go in either group most easily.
----------------------------------------------------------------------*/
static void RTreeMethodZero(struct PartitionVars *p, int minfill,
			    struct RTree *t)
{
    int i;
    RectReal biggestDiff;
    int group, chosen = 0, betterGroup = 0;

    RTreeInitPVars(p, BranchCount, minfill);
    RTreePickSeeds(p, t);

    while (p->count[0] + p->count[1] < p->total
	   && p->count[0] < p->total - p->minfill
	   && p->count[1] < p->total - p->minfill) {
	biggestDiff = (RectReal) - 1.;
	for (i = 0; i < p->total; i++) {
	    if (!p->taken[i]) {
		struct Rect *r, rect_0, rect_1;
		RectReal growth0, growth1, diff;

		r = &BranchBuf[i].rect;
		rect_0 = RTreeCombineRect(r, &p->cover[0], t);
		rect_1 = RTreeCombineRect(r, &p->cover[1], t);
		growth0 = RTreeRectSphericalVolume(&rect_0, t) - p->area[0];
		growth1 = RTreeRectSphericalVolume(&rect_1, t) - p->area[1];
		diff = growth1 - growth0;
		if (diff >= 0)
		    group = 0;
		else {
		    group = 1;
		    diff = -diff;
		}

		if (diff > biggestDiff) {
		    biggestDiff = diff;
		    chosen = i;
		    betterGroup = group;
		}
		else if (diff == biggestDiff &&
			 p->count[group] < p->count[betterGroup]) {
		    chosen = i;
		    betterGroup = group;
		}
	    }
	}
	RTreeClassify(chosen, betterGroup, p, t);
    }

    /* if one group too full, put remaining rects in the other */
    if (p->count[0] + p->count[1] < p->total) {
	if (p->count[0] >= p->total - p->minfill)
	    group = 1;
	else
	    group = 0;
	for (i = 0; i < p->total; i++) {
	    if (!p->taken[i])
		RTreeClassify(i, group, p, t);
	}
    }

    assert(p->count[0] + p->count[1] == p->total);
    assert(p->count[0] >= p->minfill && p->count[1] >= p->minfill);
}

/**********************************************************************
 *                                                                    *
 *           Norbert Beckmann's R*-tree splitting method              *
 *                                                                    *
 **********************************************************************/

/*----------------------------------------------------------------------
| swap branches
----------------------------------------------------------------------*/
static void RTreeSwapBranches(struct Branch *a, struct Branch *b)
{
    struct Branch c;

    c = *a;
    *a = *b;
    *b = c;
}

/*----------------------------------------------------------------------
| compare branches for given rectangle side
| return 1 if a > b
| return 0 if a == b
| return -1 if a < b
----------------------------------------------------------------------*/
static int RTreeCompareBranches(struct Branch *a, struct Branch *b, int side)
{
    if (a->rect.boundary[side] > b->rect.boundary[side])
	return 1;
    else if (a->rect.boundary[side] < b->rect.boundary[side])
	return -1;

    /* boundaries are equal */
    return 0;
}

/*----------------------------------------------------------------------
| check if BranchBuf is sorted along given axis (dimension)
----------------------------------------------------------------------*/
static int RTreeBranchBufIsSorted(int first, int last, int side)
{
    int i;

    for (i = first; i < last; i++) {
	if (RTreeCompareBranches(&(BranchBuf[i]), &(BranchBuf[i + 1]), side)
	    == 1)
	    return 0;
    }

    return 1;
}

/*----------------------------------------------------------------------
| partition BranchBuf for quicksort along given axis (dimension)
----------------------------------------------------------------------*/
static int RTreePartitionBranchBuf(int first, int last, int side)
{
    int pivot, mid = (first + last) / 2;
    int larger, smaller;

    if (last - first == 1) {	/* only two items in list */
	if (RTreeCompareBranches
	    (&(BranchBuf[first]), &(BranchBuf[last]), side) == 1) {
	    RTreeSwapBranches(&(BranchBuf[first]), &(BranchBuf[last]));
	}
	return last;
    }

    /* larger of two */
    if (RTreeCompareBranches(&(BranchBuf[first]), &(BranchBuf[mid]), side)
	== 1) {
	larger = pivot = first;
	smaller = mid;
    }
    else {
	larger = pivot = mid;
	smaller = first;
    }

    if (RTreeCompareBranches(&(BranchBuf[larger]), &(BranchBuf[last]), side)
	== 1) {
	/* larger is largest, get the larger of smaller and last */
	if (RTreeCompareBranches
	    (&(BranchBuf[smaller]), &(BranchBuf[last]), side) == 1) {
	    pivot = smaller;
	}
	else {
	    pivot = last;
	}
    }

    if (pivot != last) {
	RTreeSwapBranches(&(BranchBuf[pivot]), &(BranchBuf[last]));
    }

    pivot = first;

    while (first < last) {
	if (RTreeCompareBranches
	    (&(BranchBuf[first]), &(BranchBuf[last]), side) != 1) {
	    if (pivot != first) {
		RTreeSwapBranches(&(BranchBuf[pivot]), &(BranchBuf[first]));
	    }
	    pivot++;
	}
	++first;
    }

    if (pivot != last) {
	RTreeSwapBranches(&(BranchBuf[pivot]), &(BranchBuf[last]));
    }

    return pivot;
}

/*----------------------------------------------------------------------
| quicksort BranchBuf along given side
----------------------------------------------------------------------*/
static void RTreeQuicksortBranchBuf(int side)
{
    int pivot, first, last;
    int s_first[MAXCARD + 1], s_last[MAXCARD + 1], stacksize;

    s_first[0] = 0;
    s_last[0] = BranchCount - 1;

    stacksize = 1;

    /* use stack */
    while (stacksize) {
	stacksize--;
	first = s_first[stacksize];
	last = s_last[stacksize];
	if (first < last) {
	    if (!RTreeBranchBufIsSorted(first, last, side)) {

		pivot = RTreePartitionBranchBuf(first, last, side);

		s_first[stacksize] = first;
		s_last[stacksize] = pivot - 1;
		stacksize++;

		s_first[stacksize] = pivot + 1;
		s_last[stacksize] = last;
		stacksize++;
	    }
	}
    }
}

/*----------------------------------------------------------------------
| Method #1 for choosing a partition: this is the R*-tree method
|
| Pick the axis with the smallest margin increase (keep rectangles 
| square).
| Along the chosen split axis, choose the distribution with the mimimum 
| overlap-value. Resolve ties by choosing the distribution with the
| mimimum area-value.
| If one group gets too full (more would force other group to violate min
| fill requirement) then other group gets the rest.
| These last are the ones that can go in either group most easily.
----------------------------------------------------------------------*/
static void RTreeMethodOne(struct PartitionVars *p, int minfill,
                           int maxkids, struct RTree *t)
{
    int i, j, k, l, s;
    int axis = 0, best_axis = 0, side = 0, best_side[NUMDIMS];
    int best_cut[NUMDIMS];
    RectReal margin, smallest_margin = 0;
    struct Rect *r1, *r2, testrect1, testrect2, upperrect, orect;
    int minfill1 = minfill - 1;
    RectReal overlap, vol, smallest_overlap = -1, smallest_vol = -1;

    RTreeInitPVars(p, BranchCount, minfill);

    margin = DBL_MAX;

    /* choose split axis */
    /* For each dimension, sort rectangles first by lower boundary then
     * by upper boundary. Get the smallest margin. */
    for (i = 0; i < t->ndims; i++) {
	axis = i;
	best_cut[i] = 0;
	best_side[i] = 0;

	smallest_overlap = DBL_MAX;
	smallest_vol = DBL_MAX;

	/* first lower then upper bounds for each axis */
	for (s = 0; s < 2; s++) {
	    RTreeQuicksortBranchBuf(i + s * NUMDIMS);

	    side = s;

	    testrect1 = BranchBuf[0].rect;
	    upperrect = BranchBuf[maxkids].rect;

	    for (j = 1; j < minfill1; j++) {
		r1 = &BranchBuf[j].rect;
		testrect1 = RTreeCombineRect(&testrect1, r1, t);
		r2 = &BranchBuf[maxkids - j].rect;
		upperrect = RTreeCombineRect(&upperrect, r2, t);
	    }
	    r2 = &BranchBuf[maxkids - minfill1].rect;
	    upperrect = RTreeCombineRect(&upperrect, r2, t);

	    /* check distributions for this axis, adhere the minimum node fill */
	    for (j = minfill1; j < BranchCount - minfill; j++) {

		r1 = &BranchBuf[j].rect;
		testrect1 = RTreeCombineRect(&testrect1, r1, t);

		testrect2 = upperrect;
		for (k = j + 1; k < BranchCount - minfill; k++) {
		    r2 = &BranchBuf[k].rect;
		    testrect2 = RTreeCombineRect(&testrect2, r2, t);
		}

		/* the margin is the sum of the lengths of the edges of a rectangle */
		margin =
		    RTreeRectMargin(&testrect1, t) +
		    RTreeRectMargin(&testrect2, t);

		/* remember best axis */
		if (margin <= smallest_margin) {
		    smallest_margin = margin;
		    best_axis = i;
		}

		/* remember best distribution for this axis */

		/* overlap size */
		overlap = 1;

		for (k = 0; k < t->ndims; k++) {
		    /* no overlap */
		    if (testrect1.boundary[k] > testrect2.boundary[k + NUMDIMS] ||
			testrect1.boundary[k + NUMDIMS] < testrect2.boundary[k]) {
			overlap = 0;
			break;
		    }
		    /* get overlap */
		    else {
			if (testrect1.boundary[k] > testrect2.boundary[k])
			    orect.boundary[k] = testrect1.boundary[k];
			else
			    orect.boundary[k] = testrect2.boundary[k];

			l = k + NUMDIMS;
			if (testrect1.boundary[l] < testrect2.boundary[l])
			    orect.boundary[l] = testrect1.boundary[l];
			else
			    orect.boundary[l] = testrect2.boundary[l];
		    }
		}
		if (overlap)
		    overlap = RTreeRectVolume(&orect, t);

		vol =
		    RTreeRectVolume(&testrect1, t) +
		    RTreeRectVolume(&testrect2, t);

		/* get best cut for this axis */
		if (overlap <= smallest_overlap) {
		    smallest_overlap = overlap;
		    smallest_vol = vol;
		    best_cut[i] = j;
		    best_side[i] = s;
		}
		else if (overlap == smallest_overlap) {
		    /* resolve ties by minimum volume */
		    if (vol <= smallest_vol) {
			smallest_vol = vol;
			best_cut[i] = j;
			best_side[i] = s;
		    }
		}
	    }    /* end of distribution check */
	}    /* end of side check */
    }    /* end of axis check */

    /* Use best distribution to classify branches */
    if (best_axis != axis || best_side[best_axis] != side)
	RTreeQuicksortBranchBuf(best_axis + best_side[best_axis] * NUMDIMS);

    best_cut[best_axis]++;

    for (i = 0; i < best_cut[best_axis]; i++)
	RTreeClassify(i, 0, p, t);

    for (i = best_cut[best_axis]; i < BranchCount; i++)
	RTreeClassify(i, 1, p, t);

    assert(p->count[0] + p->count[1] == p->total);
    assert(p->count[0] >= p->minfill && p->count[1] >= p->minfill);
}

/*----------------------------------------------------------------------
| Split a node.
| Divides the nodes branches and the extra one between two nodes.
| Old node is one of the new ones, and one really new one is created.
| May use quadratic split or R*-tree split.
----------------------------------------------------------------------*/
void RTreeSplitNode(struct Node *n, struct Branch *b, struct Node *nn,
		    struct RTree *t)
{
    struct PartitionVars *p;
    int level;

    /* load all the branches into a buffer, initialize old node */
    level = n->level;
    RTreeGetBranches(n, b, t);

    /* find partition */
    p = &Partitions[0];
    
    if (METHOD == 1) /* R* split */
	RTreeMethodOne(p, MINFILL(level, t), MAXKIDS(level, t), t);
    else
	RTreeMethodZero(p, MINFILL(level, t), t);

    /*
     * put branches from buffer into 2 nodes
     * according to chosen partition
     */
    (nn)->level = n->level = level;
    RTreeLoadNodes(n, nn, p, t);
    assert(n->count + nn->count == p->total);
}
