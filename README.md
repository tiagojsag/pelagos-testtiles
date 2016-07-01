# Pelagos testtiles

This repository contains some scripts to generate some test tiles using the
vectortile library.

## Prerequisites

We use docker to bundle all dependencies required to run the project, so you
will need that installed.

Once you have docker, you need to build the docker image from the provided
dockerfile and tag it with a name you'll use to run the application. To do
that, run this from the project root:

```
docker build -t [NAME] .
```

## Usage

To run the generator script, you need to use your built docker image name:

```
docker run -it --rm -v $PWD:/app [NAME] python testtiles/generator.py --help
```

Follow the command help to generate tiles as you need. For example, to generate
tiles in the directory data up to zoom level 4, with 100 points per tile, you
can do this:

```
docker run -it --rm -v $PWD:/app [NAME] python testtiles/generator.py data -l 4 -c 100
```

See the generator help for additional information on the parameters we support.

