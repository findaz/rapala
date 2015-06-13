#!/usr/bin/env python

import os
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import fitsio

import bass
import bokextract

datadir = '/global/scratch2/sd/imcgreer/'
ndwfs_starfile = datadir+'ndwfs/starcat.fits'
bootes_sdss_starfile = datadir+'ndwfs/sdss_bootes_gstars.fits'
cfhtlswide_starfile = datadir+'cfhtls/CFHTLSW3_starcat.fits'
cfhtlsdeep_starfile = datadir+'cfhtls/CFHTLSD3_starcat.fits'

def cfhtw3_tiles(observed=True):
	w3west,w3east = 15*(13.+50/60.), 15*(14+45./60)
	w3south,w3north = 50.7, 56.2
	return bass.region_tiles(w3west,w3east,w3south,w3north,observed=observed)

def ndwfs_tiles(observed=True):
	ndwest,ndeast = 15*14.37, 15*14.62
	ndsouth,ndnorth = 32.5, 36.1
	return bass.region_tiles(ndwest,ndeast,ndsouth,ndnorth,observed=observed)

def panstarrs_md_tiles(observed=True):
	tiles = {}
	for field,ra,dec in [('MD03',130.592,+44.317),
                         ('MD05',161.917,+58.083),
                         ('MD06',185.000,+47.117),
                         ('MD07',213.704,+53.083),
                         ('MD08',242.787,+54.950)]:
		dra = 3.5/np.cos(np.radians(dec))
		tiles[field] = bass.region_tiles(ra-dra,ra+dra,dec-3.5,dec+3.5,
		                                 observed=observed)
	return tiles

def check_fields_list():
	files = [ t['utDate']+'/'+t['fileName']+'.fits.gz'
	                 for tiles in [cfhtw3_tiles(),ndwfs_tiles()] 
	                      for t in tiles ]
	with open('checkfields_tiles.txt','w') as f:
		f.write('\n'.join(sorted(files)))

def srcor(ra1,dec1,ra2,dec2,sep):
	from astropy.coordinates import SkyCoord,match_coordinates_sky
	from astropy import units as u
	c1 = SkyCoord(ra1,dec1,unit=(u.degree,u.degree))
	c2 = SkyCoord(ra2,dec2,unit=(u.degree,u.degree))
	idx,d2d,d3c = match_coordinates_sky(c1,c2)
	ii = np.where(d2d.arcsec < sep)[0]
	return ii,idx[ii]

def srcorXY(x1,y1,x2,y2,maxrad):
	sep = np.sqrt( (x1[:,np.newaxis]-x2[np.newaxis,:])**2 + 
	               (y1[:,np.newaxis]-y2[np.newaxis,:])**2 )
	ii = sep.argmin(axis=1)
	m1 = np.arange(len(x1))
	jj = np.where(sep[m1,ii] < maxrad)[0]
	return m1[jj],ii[jj]

def match_objects(objs,tiles):
	objpars = [('g_number','f4'),('g_ra','f8'),('g_dec','f8'),
	           ('g_autoMag','f4'),('g_autoMagErr','f4'),
	           ('g_autoFlux','f4'),('g_autoFluxErr','f4'),
	           ('g_elongation','f4'),('g_ellipticity','f4'),
	           ('g_flags','i4'),('g_fluxRad','f4')]
	tilepars = [('g_utDate','S8'),('g_expTime','f4'),
	            ('g_tileId','i4'),('g_ditherId','i4'),('g_ccdNum','i4')]
	dtype = objs.dtype.descr + objpars + tilepars
	skeys = ['NUMBER','ALPHA_J2000','DELTA_J2000','MAG_AUTO','MAGERR_AUTO',
	         'FLUX_AUTO','FLUXERR_AUTO','ELONGATION','ELLIPTICITY',
	         'FLAGS','FLUX_RADIUS']
	tkeys = ['utDate','expTime','tileId','ditherId']
	matches = []
	for ti,t in enumerate(tiles):
		print 'matching tile %d/%d' % (ti+1,len(tiles))
		for ccdNum in range(1,5):
			catpath = os.path.join(bass.rdxdir,t['utDate'],'ccdproc3',
			                       t['fileName']+'_ccd%d.cat.fits'%ccdNum)
			if not os.path.exists(catpath):
				print ' ... %s does not exist, skipping' % catpath
				continue
			cat = fitsio.read(catpath)
			ii = np.where( (objs['ra']>cat['ALPHA_J2000'].min()+3e-3) &
			               (objs['ra']<cat['ALPHA_J2000'].max()-3e-3) &
			               (objs['dec']>cat['DELTA_J2000'].min()+3e-3) &
			               (objs['dec']<cat['DELTA_J2000'].max()-3e-3) )[0]
			if len(ii)==0:
				continue
			m1,m2 = srcor(objs['ra'][ii],objs['dec'][ii],
			              cat['ALPHA_J2000'],cat['DELTA_J2000'],2.5)
			print '  ccd%d %d/%d' % (ccdNum,len(m1),len(ii)),
			matches.extend( [ tuple(objs[i]) +
			                  tuple([cat[k][j] for k in skeys]) +
			                  tuple([t[k] for k in tkeys]) + (ccdNum,)
			                     for i,j in zip(ii[m1],m2) ] )
			uu = np.delete(np.arange(len(ii)),m1)
			matches.extend( [ tuple(objs[i]) +
			                  tuple([0]*len(skeys)) + 
			                  tuple([t[k] for k in tkeys]) + (ccdNum,)
			                     for i in ii[uu] ] )
		print
	matches = np.array(matches,dtype=dtype)
	print 'finished with ',matches.size
	return matches

def depth_plots(matches,g_ref,gname,bypriority=True):
	#
	m = np.where( (matches['g_autoFlux']>0) & 
	              (matches['g_autoFluxErr']>0) )[0]
	gSNR = matches['g_autoFlux'][m] / matches['g_autoFluxErr'][m]
	if bypriority:
		plt.figure(figsize=(10,8))
		plt.subplots_adjust(0.07,0.07,0.97,0.96,0.27,0.27)
	else:
		plt.figure(figsize=(5,4.5))
		plt.subplots_adjust(0.12,0.12,0.97,0.94)
	for i in range(4):
		if bypriority:
			ax = plt.subplot(2,2,i+1)
		else:
			if i>0: break
			ax = plt.subplot(1,1,i+1)
		if i==0:
			ii = np.where(matches['g_ditherId'][m] > 0)[0]
		else:
			ii = np.where(matches['g_ditherId'][m] == i)[0]
		ax.hexbin(g_ref[m[ii]],np.log10(gSNR[ii]),
		          bins='log',cmap=plt.cm.Blues)
		ax.axhline(np.log10(5.0),c='r',lw=1.3,alpha=0.7)
		ax.set_xlim(17.2,24.5)
		ax.set_ylim(np.log10(2),np.log10(500))
		ax.xaxis.set_minor_locator(ticker.MultipleLocator(0.2))
		ax.yaxis.set_major_locator(ticker.FixedLocator(np.log10(
		      [2,5,10,20,50,100,200])))
		ax.yaxis.set_major_formatter(ticker.FuncFormatter(
		      lambda x,pos: '%d' % np.round(10**x)))
		ax.set_xlabel(gname+'mag')
		ax.set_ylabel('BASS AUTO flux/err')
		if i==0:
			ax.set_title('all tiles')
		else:
			ax.set_title('P%d tiles' % i)
	#
	mbins = np.arange(18.,24.01,0.1)
	plt.figure(figsize=(8,4))
	plt.subplots_adjust(0.07,0.14,0.97,0.97,0.25)
	ax1 = plt.subplot(121)
	ax2 = plt.subplot(122)
	for i in range(4):
		if i==0:
			ii = np.where(matches['g_ditherId'] > 0)[0]
		else:
			if not bypriority: break
			ii = np.where(matches['g_ditherId'] == i)[0]
		jj = np.where(matches['g_autoFluxErr'][ii]>0)[0]
		g5sig = ( matches['g_autoFlux'][ii[jj]]
		          / matches['g_autoFluxErr'][ii[jj]] ) > 5.0
		tot,_ = np.histogram(g_ref[ii],mbins)
		det,_ = np.histogram(g_ref[ii[jj]],mbins)
		det5,_ = np.histogram(g_ref[ii[jj[g5sig]]],mbins)
		ax1.plot(mbins[:-1],det.astype(np.float)/tot,drawstyle='steps-pre',
		         c=['black','blue','green','DarkCyan'][i],lw=1.3,
		         label=['all','P1','P2','P3'][i])
		ax2.plot(mbins[:-1],det5.astype(np.float)/tot,drawstyle='steps-pre',
		         c=['black','blue','green','DarkCyan'][i],lw=1.3,
		         label=['all','P1','P2','P3'][i])
	ax1.set_xlabel(gname+'mag')
	ax2.set_xlabel(gname+'mag')
	ax1.set_ylabel('fraction detected')
	ax2.set_ylabel('fraction detected 5 sig')
	ax1.legend(loc='lower left')



##############################################################################
#                                                                            #
#                               NDWFS                                        #
#                                                                            #
##############################################################################

def select_ndwfs_stars():
	ndwfsdir = '/global/scratch2/sd/imcgreer/ndwfs/DR3/matchedFITS/'
	dtype = [('number','i4'),('autoMag','3f4'),('autoMagErr','3f4'),
	         ('ra','f8'),('dec','f8'),('rFWHM','f4'),('rClass','f4')]
	starcat = []
	rcols = ['NUMBER','MAG_AUTO','MAGERR_AUTO','ALPHA_J2000','DELTA_J2000',
	         'FWHM_IMAGE','CLASS_STAR']
	cols = ['MAG_AUTO','MAGERR_AUTO']
	for dec1 in range(32,36):
		catfn = lambda b: 'NDWFS_%s_%d_%d_cat_m.fits.gz' % (b,dec1,dec1+1)
		rfits = fitsio.FITS(ndwfsdir+catfn('R'))
		bfits = fitsio.FITS(ndwfsdir+catfn('Bw'))
		ifits = fitsio.FITS(ndwfsdir+catfn('I'))
		w = rfits[1].where('FWHM_IMAGE < 7 && MAG_AUTO < 24.0 && FLAGS == 0')
		print len(w)
		rcat = rfits[1].read(rows=w,columns=rcols)
		bcat = bfits[1].read(rows=w,columns=cols)
		icat = ifits[1].read(rows=w,columns=cols)
		stars = np.empty(len(w),dtype=dtype)
		stars['number'] = rcat['NUMBER']
		stars['ra'] = rcat['ALPHA_J2000']
		stars['dec'] = rcat['DELTA_J2000']
		stars['rFWHM'] = rcat['FWHM_IMAGE']
		stars['rClass'] = rcat['CLASS_STAR']
		for j,cat in enumerate([bcat,rcat,icat]):
			stars['autoMag'][:,j] = cat['MAG_AUTO']
			stars['autoMagErr'][:,j] = cat['MAGERR_AUTO']
		starcat.append(stars)
	starcat = np.concatenate(starcat)
	fitsio.write(ndwfs_starfile,starcat,clobber=True)

def match_ndwfs_stars(matchRad=2.5):
	stars = fitsio.read(ndwfs_starfile)
	tiles = ndwfs_tiles(observed=True)
	matches = match_objects(stars,tiles)
	fitsio.write('ndwfs_match.fits',matches,clobber=True)

def ndwfs_depth():
	ndwfsm = fitsio.read('ndwfs_match.fits')
	Bw = ndwfsm['autoMag'][:,0]
	Bw_minus_R = ndwfsm['autoMag'][:,0] - ndwfsm['autoMag'][:,1]
	NDWFSg = np.choose(Bw_minus_R <= 1.45, 
	                   [ Bw - (0.23*Bw_minus_R + 0.25),
	                     Bw - (0.38*Bw_minus_R + 0.05) ])
	#
	m = np.where( np.all(ndwfsm['autoMag'][:,:2]> 0,axis=1) &
	              np.all(ndwfsm['autoMag'][:,:2]<30,axis=1) )[0]
	depth_plots(ndwfsm[m],NDWFSg[m],'NDWFS g-ish')



##############################################################################
#                                                                            #
#                               CFHTLS                                       #
#                                                                            #
##############################################################################

def match_cfhtls_stars(matchRad=2.5,survey='wide'):
	if survey=='wide':
		stars = fitsio.read(cfhtlswide_starfile)
		tiles = cfhtw3_tiles(observed=True)
		fname = 'cfhtlswide'
	else:
		stars = fitsio.read(cfhtlsdeep_starfile)
		fname = 'cfhtlsdeep'
	matches = match_objects(stars,tiles)
	fitsio.write('%s_match.fits'%fname,matches,clobber=True)

def cfhtls_depth():
	cfhtlsm = fitsio.read('cfhtlswide_match.fits')
	m = np.where( (cfhtlsm['psfMag'][:,1]> 0) &
	              (cfhtlsm['psfMag'][:,1]<30) )[0]
	depth_plots(cfhtlsm[m],cfhtlsm['psfMag'][m,1],'CFHTLS g',bypriority=False)




##############################################################################
#                                                                            #
#                         Pan-STARRS Medium Deeps                            #
#                                                                            #
##############################################################################

def match_ps1mds(matchRad=2.5):
	raise NotImplementedError
	pstiles = panstarrs_md_tiles(observed=True)
	for field,tiles in pstiles.items():
		stars = fitsio.read(ps1md_starfile(field))
		matches = match_objects(stars,tiles)
		fitsio.write('ps1%s_match.fits'%field,matches,clobber=True)




##############################################################################
#                                                                            #
#                             fake sources                                   #
#                                                                            #
##############################################################################

from astropy.io import fits

def fake_sdss_stars_on_tile(stars,tile,
	                        nresample=200,magrange=(22.0,23.4),
	                        stampSize=25,margin=50,
	                        keepfakes=False,savestars=False):
	pixlo = lambda _x: _x-stampSize/2
	pixhi = lambda _x: _x-stampSize/2 + stampSize
	fakemags = np.zeros(nresample*4,dtype=np.float32)
	fakesnr = -np.ones_like(fakemags)
	for ccdNum in range(1,5):
		catpath = os.path.join(bass.rdxdir,tile['utDate'],'ccdproc3',
		                       tile['fileName']+'_ccd%d.cat.fits'%ccdNum)
		if not os.path.exists(catpath):
			print ' ... %s does not exist, skipping' % catpath
			continue
		cat = fitsio.read(catpath)
		impath = os.path.join(bass.rdxdir,tile['utDate'],'ccdproc3',
		                      tile['fileName']+'_ccd%d.fits'%ccdNum)
		_impath = impath.replace('.fits','_pv.fits')
		fakeim = fits.open(_impath)
		im = fakeim[0].data
		nY,nX = im.shape
		ii = np.where( (stars['ra']>cat['ALPHA_J2000'].min()+3e-3) &
		               (stars['ra']<cat['ALPHA_J2000'].max()-3e-3) &
		               (stars['dec']>cat['DELTA_J2000'].min()+3e-3) &
		               (stars['dec']<cat['DELTA_J2000'].max()-3e-3) )[0]
		if len(ii)==0:
			print 'no stars found on ccd #',ccdNum
			continue
		m1,m2 = srcor(stars['ra'][ii],stars['dec'][ii],
		              cat['ALPHA_J2000'],cat['DELTA_J2000'],2.5)
		jj = np.where(cat['FLAGS'][m2] == 0)[0]
		rindx = np.random.choice(len(jj),size=nresample,replace=True)
		fakemag = magrange[0] + \
		             (magrange[1]-magrange[0])*np.random.random(nresample)
		fscale = 10**(-0.4*(fakemag-stars['psfMag_g'][ii[m1[jj[rindx]]]]))
		print 'matched %d/%d stars, max scale factor %.2e' % \
		        (len(m1),len(ii),fscale.max())
		fakex = np.random.randint(margin,nX-margin,nresample)
		fakey = np.random.randint(margin,nY-margin,nresample)
		for x,y,fx,fy,fscl in zip(np.round(cat['X_IMAGE'][m2[jj[rindx]]]),
		                          np.round(cat['Y_IMAGE'][m2[jj[rindx]]]),
		                          fakex,fakey,fscale):
			stamp = im[pixlo(y):pixhi(y),pixlo(x):pixhi(x)]
			im[pixlo(fy):pixhi(fy),pixlo(fx):pixhi(fx)] += fscl*stamp
		fakeimpath = impath.replace('.fits','_fake.fits')
		fakecatpath = fakeimpath.replace('.fits','.cat.fits')
		fakeim.writeto(fakeimpath,clobber=True)
		bokextract.sextract(fakeimpath,frompv=False,redo=True)
		fakecat = fitsio.read(fakecatpath)
		q1,q2 = srcorXY(fakex,fakey,fakecat['X_IMAGE'],fakecat['Y_IMAGE'],3.0)
		snr = fakecat['FLUX_AUTO'][q2] / fakecat['FLUXERR_AUTO'][q2]
		fakemags[nresample*(ccdNum-1):nresample*ccdNum] = fakemag
		fakesnr[nresample*(ccdNum-1):nresample*ccdNum][q1] = snr
		if True:
			zpt = np.median(cat['MAG_AUTO'][m2[jj]] - stars['psfMag_g'][ii[m1[jj]]])
			zpt -= 25
			foo = np.where(fakemag[q1] < 22.3)[0]
			offset = np.median((-2.5*np.log10(fakecat['FLUX_AUTO'][q2[foo]]) - zpt) - fakemag[q1[foo]])
			print 'fake star mag offset is ',offset
			fakemags[nresample*(ccdNum-1):nresample*ccdNum] += offset
		if False:
			print ' --------- ZERO POINT CHECK -----------'
			print cat['MAG_AUTO'][m2[jj]][:10]
			print -2.5*np.log10(cat['FLUX_AUTO'][m2[jj]])[:10] - zpt
			print stars['psfMag_g'][ii[m1]][:10]
			print ( (-2.5*np.log10(cat['FLUX_AUTO'][m2[jj]])[:10] - zpt) - 
			            stars['psfMag_g'][ii[m1]][:10])
			print -2.5*np.log10(fakecat['FLUX_AUTO'][q2[foo]]) - zpt
			print fakemag[q1[foo]]
			print ( (-2.5*np.log10(fakecat['FLUX_AUTO'][q2[foo]]) - zpt) - 
			         fakemag[q1[foo]] )
			print ( (-2.5*np.log10(fakecat['FLUX_AUTO'][q2[foo]]) - zpt) - 
			         fakemag[q1[foo]] ).mean()
			print snr[foo]
			print 
		if not keepfakes:
			os.unlink(fakeimpath)
			os.unlink(fakecatpath)
		if savestars:
			np.savetxt(fakeimpath.replace('.fits','_stars.dat'),
			   np.vstack([fakemag,fakex,fakey]).transpose(),fmt='%9.3f')
	return fakemags,fakesnr

def fake_ndwfs_stars(grange=(16.0,17.0),**kwargs):
	magrange = kwargs.setdefault('magrange',(22.0,23.4))
	nbins = 5
	medges = np.linspace(magrange[0],magrange[1],nbins+1)
	np.random.seed(1)
	stars = fitsio.read('/global/scratch2/sd/imcgreer/ndwfs/sdss_bootes_gstars.fits')
	fakedir = '/global/scratch2/sd/imcgreer/fakes/'
	stars = stars[(stars['psfMag_g']>grange[0])&(stars['psfMag_g']<grange[1])]
	tiles = ndwfs_tiles(observed=True)
	summaryf = open(fakedir+'fakestars_bytile.dat','w')
	summaryf.write('# %4s %1s %8s ' % ('tile','D','utdate'))
	for i in range(nbins):
		summaryf.write('%6.3f ' % ((medges[i]+medges[i+1])/2))
	summaryf.write('\n')
	for ti,tile in enumerate(tiles):
		print 'faking stars in tile %d/%d' % (ti+1,len(tiles))
		mag,snr = fake_sdss_stars_on_tile(stars,tile,**kwargs)
		np.savetxt(fakedir+'fakestars_%05d_%d_%s.dat' % 
		           (tile['tileId'],tile['ditherId'],tile['utDate']),
		           np.vstack([mag,snr]).transpose(),fmt='%8.3f')
		summaryf.write(' %05d %1d %8s ' %
		               (tile['tileId'],tile['ditherId'],tile['utDate']))
		ii = np.digitize(mag,medges)
		# could divide by CCD
		for i in range(nbins):
			jj = np.where(ii==i+1)[0]
			frac = np.sum(snr[jj]>5.0) / float(len(jj))
			summaryf.write('%6.3f ' % frac)
		summaryf.write('\n')
	summaryf.close()




def get_phototiles_info():
	import boklog
	logs = boklog.load_Bok_logs('./logs/')
	tiledb = bass.load_tiledb()
	ccdNum = 1
	photinfof = open('photo_tiles_info.txt','w')
	photinfof.write('# %6s %10s %7s %7s %7s %10s %8s %7s\n' %
	       ('UTD','file','airmass','E(B-V)','FWHMpix','skyADU','zpt','texp'))
	for ti,tiles in enumerate([cfhtw3_tiles(),ndwfs_tiles()]):
		if ti==0:
			refcat = fitsio.read(cfhtlswide_starfile)
			ii = np.where((refcat['psfMag'][:,1]>17) & 
			              (refcat['psfMag'][:,1]<18.5))[0]
			ref_ra = refcat['ra'][ii]
			ref_dec = refcat['dec'][ii]
			ref_mag = refcat['psfMag'][ii,1]
		else:
			refcat = fitsio.read(bootes_sdss_starfile)
			ii = np.where((refcat['psfMag_g']>16) & 
			              (refcat['psfMag_g']<18.5))[0]
			ref_ra = refcat['ra'][ii]
			ref_dec = refcat['dec'][ii]
			ref_mag = refcat['psfMag_g'][ii]
		for tj,t in enumerate(tiles):
			if t['ditherId'] != 1:
				continue
			# get E(B-V) from tile database
			tid = np.array([int(tid) for tid in tiledb['TID']])
			ebv = tiledb['EBV'][tid==t['tileId']][0]
			# get conditions (airmass,exptime) from observing logs
			try:
				i = np.where(logs[t['utDate']]['fileName']==t['fileName'])[0][0]
			except:
				continue
			airmass = logs[t['utDate']]['airmass'][i]
			exptime = logs[t['utDate']]['expTime'][i]
			# get sky value in ADU from FITS headers
			impath = os.path.join(bass.rdxdir,t['utDate'],'ccdproc3',
			                      t['fileName']+'_ccd%d.fits'%ccdNum)
			h = fitsio.read_header(impath)
			sky = h['SKYVAL']
			# get FWHM and zero point from catalogs
			catpath = os.path.join(bass.rdxdir,t['utDate'],'ccdproc3',
			                       t['fileName']+'_ccd%d.cat.fits'%ccdNum)
			cat = fitsio.read(catpath)
			ii = np.where( (ref_ra>cat['ALPHA_J2000'].min()+3e-3) &
			               (ref_ra<cat['ALPHA_J2000'].max()-3e-3) &
			               (ref_dec>cat['DELTA_J2000'].min()+3e-3) &
			               (ref_dec<cat['DELTA_J2000'].max()-3e-3) )[0]
			if len(ii)==0:
				continue
			m1,m2 = srcor(ref_ra[ii],ref_dec[ii],
			              cat['ALPHA_J2000'],cat['DELTA_J2000'],2)
			if len(m1)==0:
				continue
			m1 = ii[m1]
			ii = np.where(cat['FLAGS'][m2]==0)[0]
			m1,m2 = m1[ii],m2[ii]
			if len(m1)<5:
				continue
			print len(ii),' stars on tile ',t['utDate'],t['fileName']
			fwhm = np.median(cat['FWHM_IMAGE'][m2])
			zpt = 25 - np.median(cat['MAG_AUTO'][m2] - ref_mag[m1]) - \
			         2.5*np.log10(exptime)
			photinfof.write('%8s %10s %7.2f %7.3f %7.2f %10.2f %8.3f %7.1f\n' %
			     (t['utDate'],t['fileName'],airmass,ebv,fwhm,sky,zpt,exptime))
	photinfof.close()

if __name__=='__main__':
	import sys
	if sys.argv[1]=='match_ndwfs':
		match_ndwfs_stars()
	elif sys.argv[1]=='match_cfhtlswide':
		print 'here'
		match_cfhtls_stars(survey='wide')
	elif sys.argv[1]=='fake_ndwfs':
		fake_ndwfs_stars()
	elif sys.argv[1]=='photo_info':
		get_phototiles_info()

