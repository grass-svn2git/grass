#include <grass/dbmi.h>

/* define codes for characteristics of relation between two nearest features */
#define CAT        1		/* category of nearest feature */
#define FROM_X     2		/* x coordinate of nearest point on 'from' feature */
#define FROM_Y     3		/* y coordinate of nearest point on 'from' feature */
#define TO_X       4		/* x coordinate of nearest point on 'to' feature */
#define TO_Y       5		/* y coordinate of nearest point on 'to' feature */
#define FROM_ALONG 6		/* distance to nearest point on 'from' along linear feature */
#define TO_ALONG   7		/* distance to nearest point on 'to' along linear feature */
#define DIST       8		/* minimum distance to nearest feature */
#define TO_ANGLE   9		/* angle of linear feature in nearest point */
#define TO_ATTR   10		/* attribute of nearest feature */
#define END       11		/* end of list */

/* Structure to store info about nearest feature for each category */
typedef struct
{
    int from_cat;		/* category (from) */
    int count;			/* number of features already found */
    int to_cat;			/* category (to) */
    double from_x, from_y, from_z, to_x, to_y, to_z;	/* coordinates of nearest point */
    double from_along, to_along;	/* distance along a linear feature to the nearest point */
    double to_angle;		/* angle of linear feature in nearest point */
    double dist;		/* distance to nearest feature */
} NEAR;

/* Upload and column store */
typedef struct
{
    int upload;			/* code */
    char *column;		/* column name */
} UPLOAD;

/* cmp.c */
int cmp_near(const void *, const void *);
int cmp_near_to(const void *, const void *);
int cmp_exist(const void *, const void *);
/* print.c */
int print_upload(NEAR *, UPLOAD *, int, dbCatValArray *, dbCatVal *);
