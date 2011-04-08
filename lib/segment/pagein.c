
/**
 * \file pagein.c
 *
 * \brief Segment page-in routines.
 *
 * This program is free software under the GNU General Public License
 * (>=v2). Read the file COPYING that comes with GRASS for details.
 *
 * \author GRASS GIS Development Team
 *
 * \date 2005-2009
 */

#include <stdio.h>
#include <unistd.h>
#include <string.h>
#include <errno.h>
#include <grass/gis.h>
#include <grass/segment.h>


/**
 * \fn int segment_pagein (SEGMENT *SEG, int n)
 *
 * \brief Segment pagein.
 *
 * Finds <b>n</b> in the segment file, <b>seg</b>, and selects it as the 
 * current segment.
 *
 * \param[in] seg segment
 * \param[in] n segment number
 * \return 1 if successful
 * \return -1 if unable to seek or read segment file
 */

int segment_pagein(SEGMENT * SEG, int n)
{
    int cur;
    int read_result;

    /* is n the current segment? */
    if (n == SEG->scb[SEG->cur].n)
	return SEG->cur;

    /* segment n is in memory ? */

    if (SEG->load_idx[n] >= 0) {
	cur = SEG->load_idx[n];

	if (SEG->scb[cur].age != SEG->youngest) {
	    /* splice out */
	    SEG->scb[cur].age->younger->older = SEG->scb[cur].age->older;
	    SEG->scb[cur].age->older->younger = SEG->scb[cur].age->younger;
	    /* splice in */
	    SEG->scb[cur].age->younger = SEG->youngest->younger;
	    SEG->scb[cur].age->older = SEG->youngest;
	    SEG->scb[cur].age->older->younger = SEG->scb[cur].age;
	    SEG->scb[cur].age->younger->older = SEG->scb[cur].age;
	    /* make it youngest */
	    SEG->youngest = SEG->scb[cur].age;
	}

	return SEG->cur = cur;
    }

    /* find a slot to use to hold segment */
    if (!SEG->nfreeslots) {
	/* use oldest segment */
	SEG->oldest = SEG->oldest->younger;
	cur = SEG->oldest->cur;
	SEG->oldest->cur = -1;

	/* unload segment */
	if (SEG->scb[cur].n >= 0) {
	    SEG->load_idx[SEG->scb[cur].n] = -1;

	    /* write it out if dirty */
	    if (SEG->scb[cur].dirty) {
		if (segment_pageout(SEG, cur) < 0)
		    return -1;
	    }
	}
    }
    else {
	/* free slots left */
	cur = SEG->freeslot[--SEG->nfreeslots];
    }

    /* read in the segment */
    SEG->scb[cur].n = n;
    SEG->scb[cur].dirty = 0;
    segment_seek(SEG, SEG->scb[cur].n, 0);

    read_result = read(SEG->fd, SEG->scb[cur].buf, SEG->size);
    if (read_result != SEG->size) {
	G_debug(2, "segment_pagein: read_result=%d  SEG->size=%d",
		read_result, SEG->size);

	if (read_result < 0)
	    G_warning("segment_pagein: %s", strerror(errno));
	else if (read_result == 0)
	    G_warning("segment_pagein: read EOF");
	else
	    G_warning
		("segment_pagein: short count during read(), got %d, expected %d",
		 read_result, SEG->size);

	return -1;
    }

    /* add loaded segment to index */
    SEG->load_idx[n] = cur;

    /* make it youngest segment */
    SEG->youngest = SEG->youngest->younger;
    SEG->scb[cur].age = SEG->youngest;
    SEG->youngest->cur = cur;

    return SEG->cur = cur;
}
