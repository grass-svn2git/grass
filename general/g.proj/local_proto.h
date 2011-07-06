#include <grass/config.h>

extern struct Key_Value *projinfo, *projunits;
extern struct Cell_head cellhd;

/* input.c */
void input_currloc(void);
#ifdef HAVE_OGR
int input_wkt(char *);
int input_proj4(char *);
int input_epsg(int);
int input_georef(char *);
#endif

/* output.c */
void print_projinfo(int);
void print_datuminfo(void);
void print_proj4(int);
#ifdef HAVE_OGR
void print_wkt(int, int);
#endif

/* datumtrans.c */
int set_datumtrans(int, int);

/* create.c */
void create_location(char *);
void modify_projinfo();
