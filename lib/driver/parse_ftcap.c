#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <grass/gis.h>
#include <grass/glocale.h>
#include <grass/fontcap.h>
#include "driverlib.h"

int font_exists(const char *name)
{
    return access(name, R_OK) >= 0;
}

int parse_fontcap_entry(struct GFONT_CAP *e, const char *str)
{
    char name[GNAME_MAX], longname[GNAME_MAX], path[GPATH_MAX], encoding[128];
    int type, index;

    if (sscanf(str, "%[^|]|%[^|]|%d|%[^|]|%d|%[^|]|",
	       name, longname, &type, path, &index, encoding) != 6)
	return 0;

    if (!font_exists(path))
	return 0;

    e->name = G_store(name);
    e->longname = G_store(longname);
    e->type = type;
    e->path = G_store(path);
    e->index = index;
    e->encoding = G_store(encoding);

    return 1;
}

struct GFONT_CAP *parse_fontcap(void)
{
    char *capfile, file[GPATH_MAX];
    char buf[GPATH_MAX];
    FILE *fp;
    int fonts_count = 0;
    struct GFONT_CAP *fonts = NULL;

    fp = NULL;
    if ((capfile = getenv("GRASS_FONT_CAP"))) {
	if ((fp = fopen(capfile, "r")) == NULL)
	    G_warning(_("%s: Unable to read font definition file; use the default"),
		      capfile);
    }
    if (fp == NULL) {
	sprintf(file, "%s/etc/fontcap", G_gisbase());
	if ((fp = fopen(file, "r")) == NULL)
	    G_warning(_("%s: No font definition file"), file);
    }

    if (fp != NULL) {
	while (fgets(buf, sizeof(buf), fp) && !feof(fp)) {
	    struct GFONT_CAP cap;
	    char *p;

	    p = strchr(buf, '#');
	    if (p)
		*p = 0;

	    if (!parse_fontcap_entry(&cap, buf))
		continue;

	    fonts = G_realloc(fonts, (fonts_count + 1) * sizeof(struct GFONT_CAP));
	    fonts[fonts_count++] = cap;
	}

	fclose(fp);
    }

    fonts = G_realloc(fonts, (fonts_count + 1) * sizeof(struct GFONT_CAP));
    fonts[fonts_count].name = NULL;
    fonts[fonts_count].path = NULL;

    return fonts;
}

void free_fontcap(struct GFONT_CAP *ftcap)
{
    int i;

    if (ftcap == NULL)
	return;

    for (i = 0; ftcap[i].name; i++) {
	G_free(ftcap[i].name);
	G_free(ftcap[i].longname);
	G_free(ftcap[i].path);
	G_free(ftcap[i].encoding);
    }

    G_free(ftcap);
}

