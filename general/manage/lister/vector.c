#include <stdlib.h>
#include <string.h>
#include <grass/gis.h>
#include <grass/vector.h>

int main(int argc, char *argv[])
{
    int lister();

    G_gisinit(argv[0]);

    if (argc == 1)
	G_list_element("vector", "vector", "", lister);
    else {
	int i;

	for (i = 1; i < argc; ++i)
	    G_list_element("vector", "vector", argv[i], lister);
    }

    exit(0);
}

int lister(char *name, char *mapset, char *title)
{
    struct Map_info Map;

    *title = 0;
    if (*name) {
	Vect_open_old_head(&Map, name, mapset);
	strcpy(title, Vect_get_map_name(&Map));
	Vect_close(&Map);
    }

    return 0;
}
