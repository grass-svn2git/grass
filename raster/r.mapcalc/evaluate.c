
#include <stdlib.h>
#include <unistd.h>
#ifdef USE_PTHREAD
#include <pthread.h>
#include <signal.h>
#endif

#include <grass/gis.h>
#include <grass/glocale.h>

#include "mapcalc.h"
#include "globals.h"
#include "func_proto.h"

/****************************************************************************/

int current_depth, current_row;
int depths, rows, columns;

/****************************************************************************/

static void initialize(expression * e);
static void evaluate(expression * e);

/****************************************************************************/

static void allocate_buf(expression * e)
{
    e->buf = G_malloc(columns * G_raster_size(e->res_type));
}

static void set_buf(expression * e, void *buf)
{
    e->buf = buf;
}

/****************************************************************************/

static void initialize_constant(expression * e)
{
    allocate_buf(e);
}

static void initialize_variable(expression * e)
{
    set_buf(e, e->data.var.bind->data.bind.val->buf);
}

static void initialize_map(expression * e)
{
    allocate_buf(e);
    e->data.map.idx = open_map(e->data.map.name, e->data.map.mod,
			       e->data.map.row, e->data.map.col);
}

static void initialize_function(expression * e)
{
    int i;

    allocate_buf(e);

    e->data.func.argv = G_malloc((e->data.func.argc + 1) * sizeof(void *));
    e->data.func.argv[0] = e->buf;

    for (i = 1; i <= e->data.func.argc; i++) {
	initialize(e->data.func.args[i]);
	e->data.func.argv[i] = e->data.func.args[i]->buf;
    }
}

static void initialize_binding(expression * e)
{
    initialize(e->data.bind.val);
    set_buf(e, e->data.bind.val->buf);
}

static void initialize(expression * e)
{
    switch (e->type) {
    case expr_type_constant:
	initialize_constant(e);
	break;
    case expr_type_variable:
	initialize_variable(e);
	break;
    case expr_type_map:
	initialize_map(e);
	break;
    case expr_type_function:
	initialize_function(e);
	break;
    case expr_type_binding:
	initialize_binding(e);
	break;
    default:
	G_fatal_error(_("Unknown type: %d"), e->type);
    }
}

/****************************************************************************/

#ifdef USE_PTHREAD

struct worker {
    struct expression *exp;
    pthread_t thread;
    pthread_cond_t cond;
    pthread_mutex_t mutex;
};

static int num_workers;
static struct worker *workers;

static pthread_mutex_t worker_mutex;

static pthread_mutex_t map_mutex;

static void *worker(void *arg)
{
    struct worker *w = arg;

    for (;;) {
	pthread_mutex_lock(&w->mutex);
	while (!w->exp)
	    pthread_cond_wait(&w->cond, &w->mutex);
	evaluate(w->exp);
	pthread_mutex_unlock(&w->mutex);

	w->exp->worker = NULL;
	w->exp = NULL;
    }

    return NULL;
}

static struct worker *get_worker(void)
{
    int i;

    for (i = 0; i < num_workers; i++) {
	struct worker *w = &workers[i];
	if (!w->exp)
	    return w;
    }

    return NULL;
}

static void begin_evaluate(struct expression *e)
{
    struct worker *w;
 
    pthread_mutex_lock(&worker_mutex);
    w = get_worker();

    if (!w) {
	e->worker = NULL;
	pthread_mutex_unlock(&worker_mutex);
	evaluate(e);
	return;
    }

    pthread_mutex_lock(&w->mutex);
    w->exp = e;
    e->worker = w;
    pthread_cond_signal(&w->cond);
    pthread_mutex_unlock(&w->mutex);

    pthread_mutex_unlock(&worker_mutex);
}

static void end_evaluate(struct expression *e)
{
    struct worker *w = e->worker;

    if (!w)
	return;

    pthread_mutex_lock(&w->mutex);
    pthread_mutex_unlock(&w->mutex);
}

static void init_threads(void)
{
    const char *p = getenv("WORKERS");
    int i;

    pthread_mutex_init(&map_mutex, NULL);

    pthread_mutex_init(&worker_mutex, NULL);

    num_workers = p ? atoi(p) : 8;
    workers = G_calloc(num_workers, sizeof(struct worker));

    for (i = 0; i < num_workers; i++) {
	struct worker *w = &workers[i];
	pthread_mutex_init(&w->mutex, NULL);
	pthread_cond_init(&w->cond, NULL);
	pthread_create(&w->thread, NULL, worker, w);
    }
}

static void end_threads(void)
{
    int i;

    pthread_mutex_destroy(&map_mutex);

    pthread_mutex_destroy(&worker_mutex);

    for (i = 0; i < num_workers; i++) {
	struct worker *w = &workers[i];
	pthread_kill(w->thread, SIGINT);
	pthread_mutex_destroy(&w->mutex);
	pthread_cond_destroy(&w->cond);
    }
}

#endif

/****************************************************************************/

static void evaluate_constant(expression * e)
{
    int *ibuf = e->buf;
    float *fbuf = e->buf;
    double *dbuf = e->buf;
    int i;

    switch (e->res_type) {
    case CELL_TYPE:
	for (i = 0; i < columns; i++)
	    ibuf[i] = e->data.con.ival;
	break;

    case FCELL_TYPE:
	for (i = 0; i < columns; i++)
	    fbuf[i] = e->data.con.fval;
	break;

    case DCELL_TYPE:
	for (i = 0; i < columns; i++)
	    dbuf[i] = e->data.con.fval;
	break;
    default:
	G_fatal_error(_("Invalid type: %d"), e->res_type);
    }
}

static void evaluate_variable(expression * e)
{
    /* this is a no-op */
}

static void evaluate_map(expression * e)
{
#ifdef USE_PTHREAD
    pthread_mutex_lock(&map_mutex);
#endif

    get_map_row(e->data.map.idx,
		e->data.map.mod,
		current_depth + e->data.map.depth,
		current_row + e->data.map.row,
		e->data.map.col, e->buf, e->res_type);

#ifdef USE_PTHREAD
    pthread_mutex_unlock(&map_mutex);
#endif
}

static void evaluate_function(expression * e)
{
    int i;
    int res;

#ifdef USE_PTHREAD
    if (e->data.func.argc > 1 && e->data.func.func != f_eval) {
	for (i = 1; i <= e->data.func.argc; i++)
	    begin_evaluate(e->data.func.args[i]);

	for (i = 1; i <= e->data.func.argc; i++)
	    end_evaluate(e->data.func.args[i]);
    }
    else
#endif
    for (i = 1; i <= e->data.func.argc; i++)
	evaluate(e->data.func.args[i]);

    res = (*e->data.func.func) (e->data.func.argc,
				e->data.func.argt, e->data.func.argv);

    switch (res) {
    case E_ARG_LO:
	G_fatal_error(_("Too few arguments for function '%s'"),
		      e->data.func.name);
	break;
    case E_ARG_HI:
	G_fatal_error(_("Too many arguments for function '%s'"),
		      e->data.func.name);
	break;
    case E_ARG_TYPE:
	G_fatal_error(_("Invalid argument type for function '%s'"),
		      e->data.func.name);
	break;
    case E_RES_TYPE:
	G_fatal_error(_("Invalid return type for function '%s'"),
		      e->data.func.name);
	break;
    case E_INV_TYPE:
	G_fatal_error(_("Unknown type for function '%s'"), e->data.func.name);
	break;
    case E_ARG_NUM:
	G_fatal_error(_("Number of arguments for function '%s'"),
		      e->data.func.name);
	break;
    case E_WTF:
	G_fatal_error(_("Unknown error for function '%s'"),
		      e->data.func.name);
	break;
    }
}

static void evaluate_binding(expression * e)
{
    evaluate(e->data.bind.val);
}

/****************************************************************************/

static void evaluate(expression * e)
{
    switch (e->type) {
    case expr_type_constant:
	evaluate_constant(e);
	break;
    case expr_type_variable:
	evaluate_variable(e);
	break;
    case expr_type_map:
	evaluate_map(e);
	break;
    case expr_type_function:
	evaluate_function(e);
	break;
    case expr_type_binding:
	evaluate_binding(e);
	break;
    default:
	G_fatal_error(_("Unknown type: %d"), e->type);
    }
}

/****************************************************************************/

static expr_list *exprs;

/****************************************************************************/

static int error_handler(const char *msg, int fatal)
{
    expr_list *l;

    if (!fatal)
	return 0;

    for (l = exprs; l; l = l->next) {
	expression *e = l->exp;
	int fd = e->data.bind.fd;

	if (fd >= 0)
	    unopen_output_map(fd);
    }

    G_unset_error_routine();
    G_fatal_error("%s", msg);
    return 0;
}

static void setup_rand(void)
{
    /* Read PRNG seed from environment variable if available */
    /* GRASS_RND_SEED */
    const char *random_seed = getenv("GRASS_RND_SEED");
    long seed_value;

    if (!random_seed)
	return;

    seed_value = atol(random_seed);
    G_debug(3, "Read random seed from environment: %ld", seed_value);

#if defined(HAVE_DRAND48)
    srand48(seed_value);
#else
    srand((unsigned int)seed_value);
#endif
}

void execute(expr_list * ee)
{
    int verbose = isatty(2);
    expr_list *l;
    int count, n;

    setup_region();
    setup_maps();
    setup_rand();

    exprs = ee;
    G_set_error_routine(error_handler);

    for (l = ee; l; l = l->next) {
	expression *e = l->exp;
	const char *var;

	if (e->type != expr_type_binding && e->type != expr_type_function)
	    G_fatal_error("internal error: execute: invalid type: %d",
			  e->type);

	if (e->type != expr_type_binding)
	    continue;

	var = e->data.bind.var;

	if (!overwrite && check_output_map(var))
	    G_fatal_error(_("output map <%s> exists"), var);
    }

    for (l = ee; l; l = l->next) {
	expression *e = l->exp;
	const char *var;
	expression *val;

	initialize(e);

	if (e->type != expr_type_binding)
	    continue;

	var = e->data.bind.var;
	val = e->data.bind.val;

	e->data.bind.fd = open_output_map(var, val->res_type);
    }

    count = rows * depths;
    n = 0;

#ifdef USE_PTHREAD
    init_threads();
#endif

    for (current_depth = 0; current_depth < depths; current_depth++)
	for (current_row = 0; current_row < rows; current_row++) {
	    if (verbose)
		G_percent(n, count, 2);

	    for (l = ee; l; l = l->next) {
		expression *e = l->exp;
		int fd;

		evaluate(e);

		if (e->type != expr_type_binding)
		    continue;

		fd = e->data.bind.fd;
		put_map_row(fd, e->buf, e->res_type);
	    }

	    n++;
	}

#ifdef USE_PTHREAD
    end_threads();
#endif

    if (verbose)
	G_percent(n, count, 2);

    for (l = ee; l; l = l->next) {
	expression *e = l->exp;
	const char *var;
	expression *val;
	int fd;

	if (e->type != expr_type_binding)
	    continue;

	var = e->data.bind.var;
	val = e->data.bind.val;
	fd = e->data.bind.fd;

	close_output_map(fd);
	e->data.bind.fd = -1;

	if (val->type == expr_type_map) {
	    if (val->data.map.mod == 'M') {
		copy_cats(var, val->data.map.idx);
		copy_colors(var, val->data.map.idx);
	    }

	    copy_history(var, val->data.map.idx);
	}
	else
	    create_history(var, val);
    }

    G_unset_error_routine();
}

/****************************************************************************/
