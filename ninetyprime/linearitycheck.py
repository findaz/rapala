#!/usr/bin/env python

import os
import glob
import numpy as np
import fitsio
import matplotlib.pyplot as plt
from matplotlib import ticker
from matplotlib.backends.backend_pdf import PdfPages

try:
	import bokutil
except:
	import sys
	sys.path.append('../bokpipe')
	import bokutil

from bokoscan import BokOverscanSubtract,_convertfitsreg
import bokproc

def init_data_map(datadir,outdir):
	dataMap = {}
	dataMap['outdir'] = outdir
	dataMap['files'] = sorted(glob.glob(datadir+'*.fits') + 
	                          glob.glob(datadir+'*.fits.gz'))
	dataMap['oscan'] = bokutil.FileNameMap(outdir)
	dataMap['proc'] = bokutil.FileNameMap(outdir,'_p')
	dataMap['expTime'] = np.array([fitsio.read_header(f)['EXPTIME']
	                                  for f in dataMap['files']])
	# assume they are all the same
	dataMap['dataSec'] = \
	         _convertfitsreg(fitsio.read_header(
	                                  dataMap['files'][0],'IM4')['DATASEC'])
	return dataMap

def process_data(dataMap,redo=True,withvar=True,oscanims=False,bias2d=False):
	oscanSubtract = BokOverscanSubtract(output_map=dataMap['oscan'],
	                                    overwrite=redo,
		                                write_overscan_image=oscanims,
		                    oscan_cols_file=dataMap['outdir']+'oscan_cols',
		                    oscan_rows_file=dataMap['outdir']+'oscan_rows',
		                                )#method='median_value')
	oscanSubtract.process_files(dataMap['files'])
	if bias2d:
		raise NotImplementedError
		biasStack = bokproc.BokBiasStack(reject=None,
		                                 overwrite=redo,
		                                 with_variance=withvar)
		bias2dFile = dataMap['outdir']+biasname+'.fits'
		biasStack.stack(biasFrames,bias2dFile)
		imProcess = bokproc.BokCCDProcess(bias2dFile,
		                                  output_map=dataMap['proc'])
		imProcess.process_files(flatFrames)

def imstat(dataMap):
	from astropy.stats import sigma_clip
	from scipy.stats import mode,scoreatpercentile
	fnlen = len(os.path.basename(dataMap['files'][0]))
	st = np.zeros(len(dataMap['flatSequence']),
	              dtype=[('file','S%d'%fnlen),
	                     ('expTime','f4'),
	                     ('median','16f4'),
	                     ('mean','16f4'),
	                     ('mode','16f4'),
	                     ('iqr25','16f4'),
	                     ('iqr75','16f4'),
	                     ('iqr10','16f4'),
	                     ('iqr90','16f4')])
	for _i,i in enumerate(dataMap['flatSequence']):
		expTime = dataMap['expTime'][i]
		fn = os.path.basename(dataMap['files'][i])
		fits = fitsio.FITS(dataMap['files'][i])
		print '%s %4.1f  ' % (fn,expTime),
		st['file'][_i] = fn
		st['expTime'][_i] = expTime
		for j,extn in enumerate(['IM%d' % n for n in range(1,17)]):
			pix = sigma_clip(fits[extn].read()[dataMap['statsPix']])
			modeVal,npix = mode(pix,axis=None)
			st['mode'][_i,j] = modeVal
			st['mean'][_i,j] = pix.mean()
			st['median'][_i,j] = np.ma.median(pix)
			st['iqr25'][_i,j] = scoreatpercentile(pix,25)
			st['iqr75'][_i,j] = scoreatpercentile(pix,75)
			st['iqr10'][_i,j] = scoreatpercentile(pix,10)
			st['iqr90'][_i,j] = scoreatpercentile(pix,90)
			print '%5d ' % (modeVal),
		print
	fitsio.write('stats.fits',st,clobber=True)

def scaled_histograms(dataMap,nims=None,outfn='pixhist'):
	pdf = PdfPages(outfn+'.pdf')
	for _i,i in enumerate(dataMap['flatSequence']):
		if nims is not None and _i==nims:
			break
		expTime = dataMap['expTime'][i]
		expScale = dataMap['refExpTime'] / expTime
		print dataMap['files'][i]
		fn = os.path.basename(dataMap['files'][i])
		fits = fitsio.FITS(dataMap['files'][i])
		fig = plt.figure(figsize=(8.0,10))
		plt.subplots_adjust(0.08,0.08,0.92,0.92,0.3,0.35)
		for j,extn in enumerate(['IM%d' % n for n in range(1,17)]):
			ax = plt.subplot(8,2,j+1)
			pix = fits[extn].read()[dataMap['statsPix']]
			ax.hist(expScale*pix.flatten(),100,(0,40000),edgecolor='none')
			ax.text(0.05,0.9,extn,va='top',size=9,transform=ax.transAxes)
			ax.set_xlim(0,40000)
			ax.xaxis.set_major_locator(ticker.MultipleLocator(10000))
			ax.xaxis.set_minor_locator(ticker.MultipleLocator(2000))
			ax.yaxis.set_major_locator(ticker.MultipleLocator(50000))
		plt.figtext(0.5,0.99,fn+' exp=%.1f' % expTime,ha='center',va='top')
		pdf.savefig(fig)
		plt.close(fig)
	pdf.close()

def plot_sequence(dataMap,st,imNum):
	expScale = dataMap['refExpTime']/st['expTime']
	seqno = 1 + np.arange(len(st))
	ref = np.isclose(expScale,1.0)
	j = imNum - 1
	plt.figure(figsize=(8,6))
	plt.subplots_adjust(0.11,0.08,0.96,0.95)
	plt.errorbar(seqno[ref],expScale[ref]*st['median'][ref,j],
	                   [expScale[ref]*(st['median']-st['iqr10'])[ref,j],
	                    expScale[ref]*(st['iqr90']-st['median'])[ref,j]],
	             fmt='bs-')
	plt.errorbar(seqno[~ref],expScale[~ref]*st['median'][~ref,j],
	                   [expScale[~ref]*(st['median']-st['iqr10'])[~ref,j],
	                    expScale[~ref]*(st['iqr90']-st['median'])[~ref,j]],
	             fmt='cs-')
	#plt.scatter(seqno,expScale*st['mode'][:,j],marker='+',c='r')
	#plt.scatter(seqno,expScale*st['mean'][:,j],marker='x',c='g')
	plt.xlabel('sequence number')
	plt.ylabel('counts scaled by exp time')
	plt.title('IM%d'%imNum)
	plt.xlim(0.5,len(st)+0.5)

def fit_ref_exposures(dataMap,st,imNum,which='median',doplot=False):
	from scipy.interpolate import UnivariateSpline
	seqno = 1 + np.arange(len(st))
	t = st['expTime']
	ref = np.isclose(t,dataMap['refExpTime'])
	j = imNum - 1
	refCounts = st[which][ref,j][0]
	fit = UnivariateSpline(seqno[ref],refCounts/st[which][ref,j],s=1e-5,k=3)
	if doplot:
		plt.figure()
		plt.subplot(211)
		plt.plot(seqno[ref],st[which][ref,j],'bs-')
		plt.plot(seqno,refCounts/fit(seqno),c='r')
		plt.subplot(212)
		plt.plot(seqno[ref],st[which][ref,j]-refCounts/fit(seqno[ref]),'bs-')
		plt.axhline(0,c='r')
	return fit

def plot_linearity_curves(dataMap,st,which='median',correct=True,
                          refCor=None,outfn='linearity'):
	seqno = 1 + np.arange(len(st))
	t = st['expTime']
	refExpTime = dataMap['refExpTime']
	ref = np.isclose(t,refExpTime)
	refCorFit = None
	ii = np.arange(len(st))
	# only use the increasing sequence, not the reference exposures
	ii = ii[~ref]
	# skip every other image since they are done in pairs
	ii = ii[::2]
	#
	pdf = PdfPages(outfn+'.pdf')
	for imNum in range(1,17):
		j = imNum - 1
		# correct lamp variation
		if correct:
			if refCor is None:
				fscl_fit = fit_ref_exposures(dataMap,st,imNum,which)
			else:
				if refCorFit is None:
					refCorFit = fit_ref_exposures(dataMap,st,imNum,which)
				fscl_fit = refCorFit
			fscl = fscl_fit(seqno)
		else:
			fscl = np.ones_like(seqno)
		# only fit to unsaturated frames
		try:
			firstsat = np.where(st[which][ii,j] > 55000)[0][0]
		except IndexError:
			firstsat = -1
		fit = np.polyfit(t[ii[:firstsat]],
		                 fscl[ii[:firstsat]]*st[which][ii[:firstsat],j],1)
		fitv = np.polyval(fit,t)
		slope = fit[0] / (st[which][ref,j][0]/refExpTime)
		#
		pltindex = imNum % 4
		if pltindex == 1:
			fig = plt.figure(figsize=(8,10))
			plt.subplots_adjust(0.11,0.08,0.96,0.95,0.25,0.2)
		ax = plt.subplot(4,2,2*(j%4)+1)
		plt.plot(t[ii],fscl[ii]*st[which][ii,j],'bs-')
		plt.xlim(0.5,seqno[-1]+0.5)
		plt.ylim(0,69000)
		plt.ylabel('counts [%s]' % which)
		tt = np.arange(0,t.max()+1)
		plt.plot(tt,np.polyval(fit,tt),c='r')
		plt.text(0.05,0.9,'IM%d'%imNum,va='top',transform=ax.transAxes)
		plt.text(0.95,0.18,r'y = %.1f $\times$ t + %.1f' % tuple(fit),
		         ha='right',va='top',size=9,transform=ax.transAxes)
		plt.text(0.95,0.10,r'y = %.3f $\times$ counts + %.1f' % (slope,fit[1]),
		         ha='right',va='top',size=9,transform=ax.transAxes)
		if pltindex==0:
			plt.xlabel('exptime (s)')
		#
		ax = plt.subplot(4,2,2*(j%4)+2)
		plt.plot(t[ii],100*(fscl[ii]*st[which][ii,j]-fitv[ii])/fitv[ii],'bs-')
		plt.axhline(0,c='r')
		ax.xaxis.set_major_locator(ticker.MultipleLocator(10))
		ax.xaxis.set_minor_locator(ticker.MultipleLocator(2))
		ax.yaxis.set_major_locator(ticker.MultipleLocator(2))
		ax.yaxis.set_minor_locator(ticker.MultipleLocator(0.5))
		plt.ylim(-5,5)
		plt.xlim(0.5,seqno[-1]+0.5)
		if pltindex==0:
			plt.xlabel('exptime (s)')
		plt.ylabel('residual \%')
		if pltindex == 0:
			pdf.savefig(fig)
			plt.close(fig)
	pdf.close()

def get_first_saturated_frame(seq):
	try:
		firstsat = np.where(seq > 55000)[0][0]
	except IndexError:
		firstsat = -1
	return firstsat

def compare_oscan_levels(dataMap,st,imNum1,imNum2):
	files = [ dataMap['oscan'](dataMap['files'][i]) 
	                for i in dataMap['flatSequence'] ]
	oscan1 = np.array([ fitsio.read_header(f,'IM%d'%imNum1)['OSCANMED']
	                      for f in files ])
	oscan2 = np.array([ fitsio.read_header(f,'IM%d'%imNum2)['OSCANMED']
	                      for f in files ])
	seqno = 1 + np.arange(len(st))
	plt.figure()
	ax = plt.subplot(221)
	i1 = get_first_saturated_frame(st['median'][:,imNum1-1])
	plt.scatter(st['median'][:i1,imNum1-1],oscan1[:i1],c='b')
	plt.ylabel('IM%d'%imNum1)
	ax = plt.subplot(222)
	plt.scatter(seqno[:i1],oscan1[:i1],c='b')
	ax = plt.subplot(223)
	i2 = get_first_saturated_frame(st['median'][:,imNum2-1])
	plt.scatter(st['median'][:i2,imNum2-1],oscan2[:i2],c='g')
	plt.ylabel('IM%d'%imNum2)
	ax = plt.subplot(224)
	plt.scatter(seqno[:i2],oscan2[:i2],c='g')

def init_sep29ptc_data_map():
	dataMap = init_data_map(
	      "/home/ian/dev/rapala/bokpipe/scratch/sep29ptcs/ptc/",'sep29ptcs/')
	dataMap['biasFiles'] = [dataMap['files'][0],]
	dataMap['flatSequence'] = range(1,len(dataMap['files']))
	dataMap['statsPix'] = np.s_[20:-20,100:-100]
	dataMap['refExpTime'] = 10.0
	return dataMap
