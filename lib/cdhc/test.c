#include <stdio.h>
#include <stdlib.h>
#include <grass/gis.h>
#include <grass/cdhc.h>


int main(int argc, char **argv)
{
    double z[1000];
    double *w;
    int n = 0;

    while (scanf("%lf", &z[n++]) != EOF) ;
    n--;

    fprintf(stdout, "TESTS:\n");
    fprintf(stdout, "N:							%d\n", n);

    fprintf(stdout, "Moments \\sqrt{b_1} and b_2: ");
    w = omnibus_moments(z, n);
    fprintf(stdout, "%g %g\n", w[0], w[1]);

    fprintf(stdout, "Geary's a-statistic & an approx. normal:		");
    w = geary_test(z, n);
    fprintf(stdout, "%g %g\n", w[0], w[1]);

    fprintf(stdout, "Extreme normal deviates:				");
    w = extreme(z, n);
    fprintf(stdout, "%g %g\n", w[0], w[1]);

    fprintf(stdout, "D'Agostino's D & an approx. normal:			");
    w = dagostino_d(z, n);
    fprintf(stdout, "%g %g\n", w[0], w[1]);

    fprintf(stdout, "Kuiper's V (regular & modified for normality):		");
    w = kuipers_v(z, n);
    fprintf(stdout, "%g %g\n", w[1], w[0]);

    fprintf(stdout, "Watson's U^2 (regular & modified for normality):	");
    w = watson_u2(z, n);
    fprintf(stdout, "%g %g\n", w[1], w[0]);

    fprintf(stdout, "Durbin's Exact Test (modified Kolmogorov):		");
    w = durbins_exact(z, n);
    fprintf(stdout, "%g\n", w[0]);

    fprintf(stdout,
	    "Anderson-Darling's A^2 (regular & modified for normality):	");
    w = anderson_darling(z, n);
    fprintf(stdout, "%g %g\n", w[1], w[0]);

    fprintf(stdout,
	    "Cramer-Von Mises W^2(regular & modified for normality):	");
    w = cramer_von_mises(z, n);
    fprintf(stdout, "%g %g\n", w[1], w[0]);

    fprintf(stdout,
	    "Kolmogorov-Smirnov's D (regular & modified for normality):	");
    w = kolmogorov_smirnov(z, n);
    fprintf(stdout, "%g %g\n", w[1], w[0]);

    fprintf(stdout, "Chi-Square stat (equal probability classes) and d.f.:	");
    w = chi_square(z, n);
    fprintf(stdout, "%g %d\n", w[0], (int)w[1]);
    if (n > 50) {
	G_warning("Shapiro-Wilk's W cannot be used for n > 50");
	if (n < 99)
	    G_message("Use Weisberg-Binghams's W''");
    }
    else {
	fprintf(stdout, "Shapiro-Wilk W:						");
	w = shapiro_wilk(z, n);
	fprintf(stdout, "%g\n", w[0]);
    }

    if (n > 99 || n < 50)
	G_warning
	    ("Weisberg-Bingham's W'' cannot be used for n < 50 or n > 99");
    else {
	fprintf(stdout, "Weisberg-Bingham's W'':			");
	w = weisberg_bingham(z, n);
	fprintf(stdout, "%g\n", w[0]);
    }

    if (n > 2000)
	G_warning("Royston only extended Shapiro-Wilk's W up to n = 2000");
    else {
	fprintf(stdout, "Shapiro-Wilk W'':					");
	w = royston(z, n);
	fprintf(stdout, "%g\n", w[0]);
    }

    fprintf(stdout, "Kotz' T'_f (Lognormality vs. Normality):		");
    w = kotz_families(z, n);
    fprintf(stdout, "%g\n", w[0]);

    return EXIT_SUCCESS;
}
