
#include <stdlib.h>
#include <math.h>

#include <grass/gis.h>
#include "globals.h"
#include "expression.h"
#include "func_proto.h"

/**********************************************************************
asin(x)  range [-90,90]

  if floating point exception occurs during the evaluation of asin(x)
  the result is NULL

  note: result is in degrees
**********************************************************************/

#define RADIANS_TO_DEGREES (180.0 / M_PI)

int f_asin(int argc, const int *argt, void **args)
{
    DCELL *res = args[0];
    DCELL *arg1 = args[1];
    int i;

    if (argc < 1)
	return E_ARG_LO;
    if (argc > 1)
	return E_ARG_HI;

    if (argt[0] != DCELL_TYPE)
	return E_RES_TYPE;

    if (argt[1] != DCELL_TYPE)
	return E_ARG_TYPE;

    for (i = 0; i < columns; i++)
	if (IS_NULL_D(&arg1[i]))
	    SET_NULL_D(&res[i]);
	else {
	    floating_point_exception = 0;
	    res[i] = RADIANS_TO_DEGREES * asin(arg1[i]);
	    if (floating_point_exception)
		SET_NULL_D(&res[i]);
	}

    return 0;
}
