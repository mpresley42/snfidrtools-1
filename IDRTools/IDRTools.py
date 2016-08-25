import os
import numpy as np
import cPickle as pickle
import matplotlib.pyplot as plt
from IPython import embed
from astropy.io import fits


"""
A bunch of handy utilities for working with the Nearby Supernova Factory
Internal Data Release.
"""

IDR_dir = '/Users/samdixon/repos/snifs/ALLEG2a_SNeIa'
META = os.path.join(IDR_dir, 'META.pkl')

class Dataset(object):

    def __init__(self, idr_dir=IDR_dir, meta=META, subset='training'):
        self.idr_dir = idr_dir
        self.meta = pickle.load(open(meta, 'rb'))
        self.data = {}
        if subset is not None:
            for k, v in self.meta.iteritems():
                k = k.replace('.', '_')
                k = k.replace('-', '_')
                if v['idr.subset'] == subset:
                    self.data[k] = v
        else:
            self.data = self.meta
        self.sne_names = self.data.keys()
        self.sne = [Supernova(v) for k, v in self.data.iteritems()]
        for k, v in self.data.iteritems():
            setattr(self, k, Supernova(v))


class Supernova(object):

    def __init__(self, data):
        for k, v in data.iteritems():
            k = k.replace('.', '_')
            setattr(self, k, v)
        self.spectra = [Spectrum(obs) for obs in self.spectra.itervalues()]

    def get_spec_nearest_max(self):
        """
        Return the spectrum object for the observation closest to B-band max
        """
        min_phase = min(s.salt2_phase for s in self.spectra if s.salt2_phase>0)
        return [s for s in self.spectra if s.salt2_phase == min_phase][0]



class Spectrum(object):

    def __init__(self, data):
        for k, v in data.iteritems():
            k = k.replace('.', '_')
            setattr(self, k, v)

    def get_rf_spec(self):
        """
        Returns the restframe spectrum info from the IDR FITS files
        """
        path = os.path.join(IDR_dir, self.idr_spec_restframe)
        f = fits.open(path)
        head = f[0].header
        flux = f[0].data
        err = f[1].data
        f.close()
        wave = np.linspace(head['CRVAL1'], head['CRVAL1']+head['CDELT1']*len(flux), len(flux)+1)[:-1]
        return wave, flux, err

    def get_smoothed_rf_spec(self, n_l=30, smooth_fac=0.005):
        """
        Returns the smoothed restframe spectrum info using the algorithm from
        Blondin et al 2007.
        """
        wave, f_sn, f_var = self.get_rf_spec()
        f_ts = []
        for i in range(n_l/2, len(f_sn)-n_l/2):
            sig = wave[i]*smooth_fac
            sub = range(i-n_l/2, i+n_l/2)
            x = wave[i]-wave[sub]
            g = 1/np.sqrt(2*np.pi)*np.exp(-1/sig**2*x**2)
            w = g/f_var[sub]
            f_ts_i = np.dot(w, f_sn[sub])/np.sum(w)
            f_ts.append(f_ts_i)
        return wave[n_l/2:-n_l/2], np.array(f_ts)


    def plot_rf_spec(self, err=False, save=None, show=True):
        """
        Plots the restframe spectrum
        """
        w, f, e = self.get_rf_spec()
        plt.plot(w, f, 'b-', alpha=0.5)
        if err:
            plt.fill_between(w, f-e, f+e, color='b', alpha=0.5)
        if save is not None:
            plt.savefig(save, bbox_inches='tight')
        elif show:
            plt.show()

    def plot_smoothed_rf_spec(self, n_l=30, smooth_fac=0.005, save=None):
        """
        Plots the restframe spectrum
        """
        w_s, f_ts = self.get_smoothed_rf_spec(n_l=n_l, smooth_fac=smooth_fac)
        plt.plot(w_s, f_ts, 'k-')
        if save is not None:
            plt.savefig(save, bbox_inches='tight')
        else:
            plt.show()


if __name__ == '__main__':
    d = Dataset()
    embed()
