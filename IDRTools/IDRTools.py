import os
import numpy as np
import cPickle as pickle
from astropy.io import fits
from sncosmo import Model, get_source
from astropy.cosmology import Planck15 as cosmo
from IPython import embed

"""
A bunch of handy utilities for working with the Nearby Supernova Factory
Internal Data Release.
"""

IDR_dir = '/Users/samdixon/repos/IDRTools/ALLEG2a_SNeIa'
META = os.path.join(IDR_dir, 'META.pkl')

C = 2.99792458e10
PLANCK = 6.62607e-27

meta = pickle.load(open(META, 'rb'))


class Dataset(object):

    def __init__(self, data=meta, subset='training'):
        self.data = {}
        if subset is not None:
            for k, v in data.iteritems():
                k = k.replace('.', '_')
                k = k.replace('-', '_')
                if v['idr.subset'] in subset:
                    self.data[k] = v
        else:
            self.data = data
        self.sne_names = self.data.keys()
        self.sne = [Supernova(self.data, name) for name in self.sne_names]
        for k in self.data.iterkeys():
            setattr(self, k, Supernova(self.data, k))

    def random_sn(self, n=1):
        """
        Returns a random list of supernovae of length n
        """
        if n == 1:
            return np.random.choice(self.sne, 1)[0]
        else:
            return np.random.choice(self.sne, size=n, replace=False)


class Supernova(object):

    def __init__(self, dataset, name):
        data = dataset[name]
        for k, v in data.iteritems():
            k = k.replace('.', '_')
            setattr(self, k, v)
        setattr(self, 'hr', self.get_hr()[0])
        setattr(self, 'hr_err', self.get_hr()[1])
        setattr(self, 'distmod', self.get_distmod()[0])
        setattr(self, 'distmod_err', self.get_distmod()[1])
        self.spectra = [Spectrum(dataset, name, obs) for obs in self.spectra.iterkeys()]
        # Sort spectra by SALT2 phase
        self.spectra = sorted(self.spectra, key=lambda x: x.salt2_phase)

    def spec_nearest_max(self, phase=0):
        """
        Returns the spectrum object for the observation closest to B-band max.
        """
        min_phase = min(np.abs(s.salt2_phase-phase) for s in self.spectra)
        return [s for s in self.spectra if np.abs(s.salt2_phase-phase) == min_phase][0]

    def lc(self, filter_name):
        """
        Finds the light curve in some SNf filter using synthetic photometry.
        """
        phase = [spec.salt2_phase for spec in self.spectra]
        mag = [spec.snf_magnitude(filter_name) for spec in self.spectra]
        return phase, mag

    def salt2_model_fluxes(self):
        """
        Creates the SALT2 model spectra flux based on the fit parameters.
        """
        source = get_source('SALT2', version='2.4')
        model = Model(source=source)
        model.set(z=0, t0=0, x0=self.salt2_X0, x1=self.salt2_X1, c=self.salt2_Color)
        wave = np.arange(3272, 9200, 2)
        measured_phases = [spec.salt2_phase for spec in self.spectra]
        phases = np.linspace(min(measured_phases), max(measured_phases), 100)
        fluxes = model.flux(phases, wave)
        return phases, wave, fluxes

    def salt2_model_lc(self, filter_name):
        """
        Creates the SALT2 model light curve based on the fit parameters.
        """
        phases, wave, fluxes = self.salt2_model_fluxes()
        filter_edges = {'u' : (3300., 4102.),
                        'b' : (4102., 5100.),
                        'v' : (5200., 6289.),
                        'r' : (6289., 7607.),
                        'i' : (7607., 9200.)}
        min_wave, max_wave = filter_edges[filter_name]
        mag = []
        for flux in fluxes:
            ref_flux = 3.631e-20 * C * 1e8 / wave**2
            flux_sum = np.sum((flux * wave * 2 / PLANCK / C)[(wave > min_wave) & (wave < max_wave)])
            ref_flux_sum = np.sum((ref_flux * wave * 2 / PLANCK / C)[(wave > min_wave) & (wave < max_wave)])
            mag.append(-2.5*np.log10(flux_sum/ref_flux_sum))
        return phases, mag

    def get_distmod(self):
        """
        Return the distance modulus from the SALT2 parameters.
        """
        MB, alpha, beta = -19.155510156376913, 0.15336666476334873, 2.7111339334687163  # Obtained from emcee fit (see Brian's code)
        dMB, dalpha, dbeta = 0.019457765851807848, 0.020340953530227517, 0.13066032343415704
        mu = self.salt2_RestFrameMag_0_B - MB + alpha * self.salt2_X1 - beta * self.salt2_Color
        dmu = np.sqrt(self.salt2_RestFrameMag_0_B_err**2+dMB**2+dalpha**2*self.salt2_X1**2+alpha**2*self.salt2_X1_err**2+beta**2*self.salt2_Color_err**2+dbeta**2+self.salt2_Color**2)
        return mu, dmu

    def get_hr(self):
        """
        Return the Hubble residual from the SALT2 parameters.
        """
        mu, dmu = self.get_distmod()
        cosmo_mu = cosmo.distmod(self.salt2_Redshift).value
        return mu-cosmo_mu, dmu


class Spectrum(object):
    def __init__(self, dataset, name, obs):
        self.sn_data = dataset[name]
        data = dataset[name]['spectra'][obs]
        for k, v in data.iteritems():
            k = k.replace('.', '_')
            setattr(self, k, v)

    def merged_spec(self):
        """
        Returns the merged spectrum from the IDR FITS files.
        """
        path = os.path.join(IDR_dir, self.idr_spec_merged)
        f = fits.open(path)
        head = f[0].header
        flux = f[0].data
        err = f[1].data
        f.close()
        start = head['CRVAL1']
        end = head['CRVAL1']+head['CDELT1']*len(flux)
        npts = len(flux)+1
        wave = np.linspace(start, end, npts)[:-1]
        return wave, flux, err

    def rf_spec(self):
        """
        Returns the restframe spectrum from the IDR FITS files.
        """
        path = os.path.join(IDR_dir, self.idr_spec_restframe)
        f = fits.open(path)
        head = f[0].header
        flux = f[0].data
        err = f[1].data
        f.close()
        start = head['CRVAL1']
        end = head['CRVAL1']+head['CDELT1']*len(flux)
        npts = len(flux)+1
        wave = np.linspace(start, end, npts)[:-1]
        #Flux is scaled by a relative distance factor to z=0.05 and multiplied by 1e15
        dl = (1 + self.sn_data['host.zhelio']) * cosmo.comoving_transverse_distance(self.sn_data['host.zcmb']).value
        dlref = cosmo.luminosity_distance(0.05).value
        flux = flux / ((1+self.sn_data['host.zhelio'])/(1+0.05) * (dl/dlref)**2 * 1e15)
        err = err / ((1+self.sn_data['host.zhelio'])/(1+0.05) * (dl/dlref)**2 * 1e15)**2
        return wave, flux, err

    def salt2_model_fluxes(self):
        """
        Creates the SALT2 model spectra flux based on the fit parameters.
        """
        source = get_source('SALT2', version='2.4')
        model = Model(source=source)
        model.set(z=0, t0=0, x0=self.sn_data['salt2.X0'], x1=self.sn_data['salt2.X1'], c=self.sn_data['salt2.Color'])
        wave = np.arange(3272, 9200, 2)
        flux = model.flux(self.salt2_phase, wave)
        return wave, flux

    def magnitude(self, min_wave, max_wave):
        """
        Calculates the AB magnitude in a given top-hat filter.
        """
        wave, flux, flux_err = self.rf_spec()
        ref_flux = 3.631e-20 * C * 1e8 / wave**2
        flux_sum = np.sum((flux * wave * 2 / PLANCK / C)[(wave > min_wave) & (wave < max_wave)])
        ref_flux_sum = np.sum((ref_flux * wave * 2 / PLANCK / C)[(wave > min_wave) & (wave < max_wave)])
        return -2.5*np.log10(flux_sum/ref_flux_sum)

    def snf_magnitude(self, filter_name, z=None):
        """
        Calculates the AB magnitude in a given SNf filter.
        """
        filter_edges = {'u' : (3300., 4102.),
                        'b' : (4102., 5100.),
                        'v' : (5200., 6289.),
                        'r' : (6289., 7607.),
                        'i' : (7607., 9200.)}
        min_wave, max_wave = filter_edges[filter_name]
        return self.magnitude(min_wave, max_wave)


if __name__ == '__main__':
    d = Dataset()
    sn = d.SN2005cf
    spec = sn.spec_nearest_max()
    w, f, v = spec.rf_spec()
