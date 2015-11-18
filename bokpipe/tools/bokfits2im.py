#!/usr/bin/env python

import argparse

from bokpipe.bokmkimage import make_fov_image_fromfile

parser = argparse.ArgumentParser()
parser.add_argument("fitsFile",type=str,
                    help="input FITS image")
parser.add_argument("imgFile",type=str,
                    help="output image file")
parser.add_argument("--nbin",type=int,default=1,
                    help="output image file")
parser.add_argument("--coordsys",type=str,default='sky',
                    help="coordinate system")
parser.add_argument("--vmin",type=float,
                    help="minimum range")
parser.add_argument("--vmax",type=float,
                    help="maximum range")
parser.add_argument("--cmap",type=str,
                    help="color map")
args = parser.parse_args()

make_fov_image_fromfile(args.fitsFile,args.imgFile,
                        nbin=args.nbin,coordsys=args.coordsys,
                        vmin=args.vmin,vmax=args.vmax,cmap=args.cmap)

