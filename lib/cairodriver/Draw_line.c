#include "cairodriver.h"

void Cairo_draw_line(double x1, double y1, double x2, double y2)
{
    G_debug(3, "Cairo_draw_line: %f %f %f %f", x1, y1, x2, y2);

    if (x1 == x2 && y1 == y2) {
	/* don't draw degenerate lines */
	G_debug(3, "Skipping zero-length line");
	return;
    }

    cairo_move_to(cairo, x1, y1);
    cairo_line_to(cairo, x2, y2);
    cairo_stroke(cairo);
    modified = 1;
}
