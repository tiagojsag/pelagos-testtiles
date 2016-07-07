import sys
import os.path
import click
import vectortile
import json
import datetime

DATE_FORMAT="%Y-%m-%dT%H:%M:%S"
DEFAULT_EXTENT=1000. * 60. * 60. * 24. * 30
EPOCH=datetime.datetime(1970,1,1)

##############################################################################
# Utility functions
##############################################################################
class SeriesGenerator:
    """Stateful class which generates unique series and seriesgroups. A series
    is an identifier which identifies a group of highly related points which
    belong to a single segment. A seriesgroup is an identifier which identifies
    a group of points belonging to a single vessel."""
    def __init__(self):
        self.series = 0
        self.series_group = 0

    def new_series(self):
         self.series += 1
         return self.series

    def new_series_group(self):
        self.series_group += 1
        return self.series_group

    def current_series_group(self):
        return self.series_group

def datetime2timestamp(d):
    """Converts an actual datetime into linux timestamps, total of seconds
    since the epoch"""
    return (d - EPOCH).total_seconds()

def quadtree2google(key):
    """Converts a microsoft quadtree key into the standard google tile coordinates"""
    key = str(key)
    zoom = len(key)

    x = 0
    for c in key:
        x *= 2
        if c == "1" or c == "3":
            x += 1
    y = 0
    for c in key:
        y *= 2
        if c == "2" or c == "3":
            y += 1

    return ",".join(map(str, [zoom, x, y]))

def ensure_dir(path):
    """Ensures a directory exists, creating it if it doesn't"""
    if not os.path.exists(path):
        os.makedirs(path)

##############################################################################
# File generation functions
##############################################################################
def generate_tile(outdir, series_generator, point_bounds, tile_bounds = None, time_range = None, points = 100):
    """Generates a single tile with vessel points in a given directory for the
    current seriesgroup of the given `series_generator`. The points are
    distributed across the left and lower bounds of the given `point_bounds`
    bounds. The name of the tile is generated from the boundaries defined in
    the given `tile_bounds`. If a `time_range` is given, the tile is temporal
    as well and the range is used in the tile name."""
    # The tile bounds are microsoft's quadtree gridcodes. We transform them to
    # google tile coordinates and use that as the base filename.
    filename = quadtree2google(tile_bounds or point_bounds)

    # If temporal tiling is enabled, we need to include the time range in the
    # filename. Otherwise we compute a default time range to distribute points
    # evenly in time.
    if time_range is None:
        time_range = (0, DEFAULT_EXTENT)
    else:
        filename = "%s,%s;%s" % (time_range[0].strftime("%Y-%m-%dT%H:%M:%S"),
                                 time_range[1].strftime("%Y-%m-%dT%H:%M:%S"),
                                 filename)
        time_range = [datetime2timestamp(x) * 1000 for x in time_range]
    time_len = time_range[1] - time_range[0]

    # We build all the vessel points in the tile by making an L-shaped line
    #in the lower-left corner of the tile.
    bbox = point_bounds.get_bbox()
    data = []
    for idx in xrange(0, points):
        # We need to invert the latitude coordinates as the bounding boxes are
        # inverted in the vectortile library: tile with gridcode 00,
        # corresponding to 2,0,0 has bounding coordinates with latitudes -90 to
        # -45, in the southern hemisphere
        item = {"seriesgroup": series_generator.current_series_group(),
                "series": series_generator.new_series(),
                "longitude": bbox.lonmin,
                "latitude": -(idx * (bbox.latmax - bbox.latmin) / float(points) + bbox.latmin),
                "datetime": time_range[0] + idx * time_len / float(points),
                "weight": 20.0,
                "sog":20,
                "cog": 360.0 * round(8 * idx / float(points)) / 8.0,
                "sigma": 0.0}
        data.append(item)
        item ={"seriesgroup": series_generator.current_series_group(),
               "series": series_generator.new_series(),
               "longitude": idx * (bbox.lonmax - bbox.lonmin) / float(points) + bbox.lonmin,
               "latitude": -bbox.latmin,
               "datetime": time_range[0] + idx * time_len / float(points),
               "weight": 20.0,
               "sog":20,
               "cog": 360.0 * round(8 * idx / float(points)) / 8.0,
               "sigma": 0.0}
        data.append(item)

    # Serialize the data using the vectortile binary format
    with open(os.path.join(outdir, filename), "w") as f:
        f.write(str(vectortile.Tile.fromdata(data, {})))

def generate_info(outdir, series_group):
    """Generate a vessel information file which contains information about a
    single vessel, identified by it's seriesgroup"""
    # Build some sample data for the vessel
    info = {"mmsi": str(series_group),
            "callsign": "SE%s" % series_group,
            "vesselname": ["Oden", "Tor", "Frej", "Loke", "Balder", "Freja", "Mimer"][series_group % 7]}

    # Serialize the data as json
    with open(os.path.join(outdir, "info"), "w") as f:
        f.write(json.dumps(info))

def generate_header(outdir, title, time_min, time_max, temporalExtents=False):
    """Generate a tileset header file, which contains metadata about the tiles
    in the tileset or selection query, such as how to interpret the tiles and
    how to load it."""
    # Build the tileset header. As all the tiles have the same structure, all
    # headers are the same
    header = {"tilesetName": title,
            "colsByName": {"seriesgroup": {"max": 4711.,
                "type": "Float32",
                "min": 0.},
                "series": {"max": 4711.,
                    "type": "Float32",
                    "min": 0.},
                "longitude": {"min": -180.,
                    "max": 180.,
                    "hidden": True,
                    "type": "Float32"},
                "latitude": {"min": -90.,
                    "max": 90.,
                    "hidden": True,
                    "type": "Float32"},
                "datetime": {"min": datetime2timestamp(time_min) * 1000.,
                    "max": datetime2timestamp(time_max) * 1000.,
                    "hidden": True,
                    "type": "Float32"},
                "weight": {"max": 4711.,
                    "type": "Float32",
                    "min": 0.},
                "sog": {"max": 30.,
                    "type": "Float32",
                    "min": 0.},
                "cog": {"max": 360.,
                    "type": "Float32",
                    "min": 0.},
                "sigma": {"max": 4711.,
                    "type": "Float32",
                    "min": 0.}},
                "tilesetVersion": "1",
                "seriesTilesets": True,
                "infoUsesSelection": True,
                "temporalExtents": temporalExtents or None}

    # Serialize the data as json
    with open(os.path.join(outdir, "header"), "w") as f:
        f.write(json.dumps(header))

##############################################################################
# Whole tileset generation
##############################################################################
def generate_tileset(outdir, levels, start, extent, extent_count, point_count):
    series_generator = SeriesGenerator()
    title = os.path.basename(outdir)
    time_min = start
    time_max = datetime.datetime.utcfromtimestamp(datetime2timestamp(start) + (extent_count or 1) * extent / 1000.0)
    ensure_dir(outdir)

    def generate_tiles(bounds, level=0):
        print("Generating tiles for bounds %s at zoom level %s" % (bounds, level))
        series_group = series_generator.new_series_group();
        sub_outdir = os.path.join(outdir, "sub", "seriesgroup=%s" % series_group)
        ensure_dir(sub_outdir)

        generate_header(sub_outdir, "Track for %s" % series_group, time_min, time_max, extent_count is not None)
        generate_info(sub_outdir, series_group)

        if extent_count != None:
            for i in xrange(0, extent_count):
                time_range = (datetime.datetime.utcfromtimestamp(datetime2timestamp(start) + extent * i / 1000.),
                              datetime.datetime.utcfromtimestamp(datetime2timestamp(start) + extent * (i+1) / 1000.))
                generate_tile(outdir, series_generator, bounds, time_range=time_range, points=point_count)
                generate_tile(sub_outdir, series_generator, bounds, vectortile.TileBounds(), time_range=time_range, points=point_count)
        else:
            generate_tile(outdir, series_generator, bounds, points=point_count)
            generate_tile(sub_outdir, series_generator, bounds, vectortile.TileBounds(), points=point_count)

        if ((levels is None or level < levels) and bounds.zoom_level < bounds.maxzoom):
            for child in bounds.get_children():
                generate_tiles(child, level+1)

    generate_tiles(vectortile.TileBounds())
    generate_header(outdir, title, time_min, time_max, extent_count is not None)


##############################################################################
# Entry point
##############################################################################
class TimeType(click.ParamType):
    name = 'time'

    def convert(self, value, param, ctx):
        try:
            return datetime.datetime.strptime(value, DATE_FORMAT)
        except ValueError:
            self.fail('%s is not a valid date' % value, param, ctx)

@click.command()
@click.argument("outdir", metavar="OUTDIR")
@click.option(
    '-l', '--levels', type=click.INT, default=1,
    help="Zoom levels to generate")
@click.option(
    '-c', '--count', type=click.INT, default=100,
    help="Amount of points to generate into each tile. Default 100.")
@click.option(
    '-s', '--temporal-start', type=TimeType(), default=EPOCH.strftime(DATE_FORMAT),
    help="Start timestamps points. Default %s" % EPOCH.strftime(DATE_FORMAT))
@click.option(
    '-e', '--temporal-extent', type=click.FLOAT, default=DEFAULT_EXTENT,
    help="Length of each extent. Default %s" % DEFAULT_EXTENT)
@click.option(
    '-E', '--temporal-extent-count', type=click.INT, default=None,
    help="Number of extents. A non-temporaly tiled tileset is generated if not specified.")
@click.pass_context
def main(ctx, outdir, levels, count, temporal_start, temporal_extent, temporal_extent_count):
    print("Generating tileset with the following parameters")
    print("  Zoom levels: %s" % levels)
    print("  Point count: %s" % count)
    print("  Temporal start: %s" % temporal_start)
    print("  Temporal extent: %s" % temporal_extent)
    print("  Temporal extent count: %s" % temporal_extent_count)
    print("")
    generate_tileset(outdir, levels, temporal_start, temporal_extent, temporal_extent_count, count)

if __name__ == "__main__":
    main()

