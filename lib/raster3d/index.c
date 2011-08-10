#include <stdio.h>
#include <stdlib.h>
#include <sys/types.h>
#include <unistd.h>
#include <grass/raster3d.h>
#include "raster3d_intern.h"

/*---------------------------------------------------------------------------*/

static int Rast3d_readIndex(RASTER3D_Map * map)
{
    unsigned char *tmp, *tmp2;
    int dummy1, dummy2, indexLength, tileIndex;
    long indexLast;

    indexLast = lseek(map->data_fd, (long)0, SEEK_END);
    if (indexLast == -1) {
	Rast3d_error("Rast3d_readIndex: can't position file");
	return 0;
    }

    indexLength = indexLast - map->indexOffset;

    if (lseek(map->data_fd, map->indexOffset, SEEK_SET) == -1) {
	Rast3d_error("Rast3d_readIndex: can't position file");
	return 0;
    }

    tmp = Rast3d_malloc(map->indexLongNbytes * map->nTiles);

    if (tmp == NULL) {
	Rast3d_error("Rast3d_readIndex: error in Rast3d_malloc");
	return 0;
    }

    if (indexLength < map->indexLongNbytes * map->nTiles) {	/* RLE encoded? */

	if (indexLength > sizeof(long) * map->nTiles) {
						     /*->index large enough? */
	    tmp2 = Rast3d_malloc(indexLength);
	    if (tmp2 == NULL) {
		Rast3d_error("Rast3d_readIndex: error in Rast3d_malloc");
		return 0;
	    }
	}
	else			/* YES */
	    tmp2 = (unsigned char *)map->index;

	if (read(map->data_fd, tmp2, indexLength) != indexLength) {
	    Rast3d_error("Rast3d_readIndex: can't read file");
	    return 0;
	}

	G_rle_decode(tmp2, tmp, map->indexLongNbytes * map->nTiles, 1,
		     &dummy1, &dummy2);

	if (indexLength > sizeof(long) * map->nTiles)
	    Rast3d_free(tmp2);
    }
    else /* NO RLE */ if (read(map->data_fd, tmp, indexLength) != indexLength) {
	Rast3d_error("Rast3d_readIndex: can't read file");
	return 0;
    }

    Rast3d_longDecode(tmp, map->index, map->nTiles, map->indexLongNbytes);

    for (tileIndex = 0; tileIndex < map->nTiles; tileIndex++)
	if (map->index[tileIndex] == 0)
	    map->index[tileIndex] = -1;

    Rast3d_free(tmp);

    return 1;
}

/*---------------------------------------------------------------------------*/

int Rast3d_flushIndex(RASTER3D_Map * map)
{
    int sizeCompressed, indexLength, tileIndex;
    unsigned char *tmp;
    long ldummy;

    if (!map->hasIndex)
	return 1;

    map->indexOffset = lseek(map->data_fd, (long)0, SEEK_END);
    if (map->indexOffset == -1) {
	Rast3d_error("Rast3d_flushIndex: can't rewind file");
	return 0;
    }

    map->indexNbytesUsed = Rast3d_longEncode(&(map->indexOffset),
					  (unsigned char *)&ldummy, 1);

    tmp = Rast3d_malloc(sizeof(long) * map->nTiles);
    if (tmp == NULL) {
	Rast3d_error("Rast3d_flushIndex: error in Rast3d_malloc");
	return 0;
    }

    for (tileIndex = 0; tileIndex < map->nTiles; tileIndex++)
	if (map->index[tileIndex] == -1)
	    map->index[tileIndex] = 0;

    (void)Rast3d_longEncode(map->index, tmp, map->nTiles);

    sizeCompressed = G_rle_count_only(tmp, sizeof(long) * map->nTiles, 1);

    if (sizeCompressed >= map->nTiles * sizeof(long)) {
	indexLength = map->nTiles * sizeof(long);
	if (write(map->data_fd, tmp, indexLength) != indexLength) {
	    Rast3d_error("Rast3d_flushIndex: can't write file");
	    return 0;
	}
    }
    else {
	indexLength = sizeCompressed;
	G_rle_encode(tmp, (char *)map->index, sizeof(long) * map->nTiles, 1);
	if (write(map->data_fd, map->index, sizeCompressed) != sizeCompressed) {
	    Rast3d_error("Rast3d_flushIndex: can't write file");
	    return 0;
	}
    }

    Rast3d_free(tmp);
    if (!Rast3d_readIndex(map)) {
	Rast3d_error("Rast3d_flushIndex: error in Rast3d_readIndex");
	return 0;
    }

    return 1;
}

/*---------------------------------------------------------------------------*/

static long *cmpIndex;

static int indexSortCompare(const void *a, const void *b)
{
    long offset1, offset2;

    offset1 = cmpIndex[*((const int *)a)];
    offset2 = cmpIndex[*((const int *)b)];

    if (offset1 > offset2)
	return 1;
    if (offset1 < offset2)
	return -1;
    return 0;
}

/*---------------------------------------------------------------------------*/

int Rast3d_initIndex(RASTER3D_Map * map, int hasIndex)
{
    int tile;
    int i0, i1, i2, i3, i4, i5, offset, nofElts;
    int *offsetP;

    map->hasIndex = hasIndex;
    map->index = Rast3d_malloc(sizeof(long) * map->nTiles);
    map->tileLength = Rast3d_malloc(sizeof(int) * map->nTiles);

    if ((map->index == NULL) || (map->tileLength == NULL)) {
	Rast3d_error("Rast3d_initIndex: error in Rast3d_malloc");
	return 0;
    }

    if (map->operation == RASTER3D_WRITE_DATA) {
	for (tile = 0; tile < map->nTiles; tile++)
	    map->index[tile] = -1;
	return 1;
    }

    if (!map->hasIndex) {
	offset = 0;
	for (tile = 0; tile < map->nTiles; tile++) {
	    map->index[tile] = offset * map->numLengthExtern + map->offset;
	    nofElts = Rast3d_computeClippedTileDimensions
		(map, tile, &i0, &i1, &i2, &i3, &i4, &i5);
	    map->tileLength[tile] = nofElts * map->numLengthExtern;
	    offset += nofElts;
	}
	return 1;
    }

    if (!Rast3d_readIndex(map)) {
	Rast3d_error("Rast3d_initIndex: error in Rast3d_readIndex");
	return 0;
    }

    offsetP = Rast3d_malloc(sizeof(int) * map->nTiles);
    if (offsetP == NULL) {
	Rast3d_error("Rast3d_initIndex: error in Rast3d_malloc");
	return 0;
    }

    for (tile = 0; tile < map->nTiles; tile++)
	offsetP[tile] = tile;
    cmpIndex = map->index;
    qsort(offsetP, map->nTiles, sizeof(int), indexSortCompare);

    for (tile = 0; tile < map->nTiles - 1; tile++) {
	if (map->index[offsetP[tile]] == -1) {
	    map->tileLength[offsetP[tile]] = 0;
	    continue;
	}

	map->tileLength[offsetP[tile]] = map->index[offsetP[tile + 1]] -
	    map->index[offsetP[tile]];
    }

    if (map->index[offsetP[map->nTiles - 1]] == -1)
	map->tileLength[offsetP[map->nTiles - 1]] = 0;
    else
	map->tileLength[offsetP[map->nTiles - 1]] =
	    map->indexOffset - map->index[offsetP[map->nTiles - 1]];

    Rast3d_free(offsetP);

    return 1;
}
