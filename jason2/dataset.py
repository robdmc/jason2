"""Working with netCDF4 data."""

from collections import namedtuple
import datetime

import netCDF4
import numpy


Waveforms = namedtuple("Waveforms", ["data", "latitudes"])
Height = namedtuple("Height", ["data", "average", "stddev", "latitudes"])
Heights = namedtuple("Heights", ["data", "datetime"])


class Dataset(object):
    """Wrapper around a netCDF4 dataset.

    We wrap because we have some common functions that we need to do on the
    data, such as location masking.

    """

    GATE_2_METERS = 0.4684375

    def __init__(self, filename, bounds):
        self.data = netCDF4.Dataset(filename)
        self.variables = self.data.variables
        self.bounds = bounds

    def get_waveforms(self, clip=None):
        """Get waveform data for this dataset.

        The dataset needs to be an sgdr dataset, otherwise there won't be any
        waveform data to extract.

        """
        mask20hz = self._get_20hz_mask().flatten()
        waveforms = self.variables["waveforms_20hz_ku"][:]
        waveforms.shape = (waveforms.shape[0] * waveforms.shape[1],
                           waveforms.shape[2])
        waveforms = waveforms[mask20hz, :]
        if clip is not None:
            waveforms = numpy.clip(waveforms, 0, clip)
        return Waveforms(waveforms,
                         self.variables["lat_20hz"][:].flatten()[mask20hz])

    def get_heights(self):
        data = {
            "ocean": self._get_height("range_20hz_ku"),
            "mle3": self._get_height("range_20hz_ku_mle3"),
            "ice": self._get_height("ice_range_20hz_ku"),
            "threshold_50": self.get_threshold_height(0.50),
        }
        datetime = self._jason2time_to_datetime(
            numpy.median(self.variables["time"][:][self._get_1hz_mask()]))
        return Heights(data, datetime)

    def get_sea_surface_height(self):
        """Ocean height"""
        return self._get_height("range_20hz_ku")

    def get_mle3_height(self):
        """MLE3"""
        return self._get_height("range_20hz_ku_mle3")

    def get_ice_height(self):
        """Ice height"""
        return self._get_height("ice_range_20hz_ku")

    def get_threshold_height(self, threshold_level):
        """Height from a threshold retracker."""
        waveforms = self.get_waveforms()
        mle3 = self.get_mle3_height()
        retracked = numpy.empty(len(waveforms.data))
        retracked[:] = numpy.NAN
        for i, row in enumerate(waveforms.data):
            rowmax = numpy.max(row)
            dc = numpy.mean(row)
            threshold = dc + threshold_level * (rowmax - dc)
            binnumber = None
            for j, value in enumerate(row[1:]):
                if value >= threshold:
                    if value - row[j-1] == 0:
                        binnumber = j - 1
                    else:
                        binnumber = (j - 1) + ((threshold - row[j-1]) /
                                               (value - row[j-1]))
                    break
            if binnumber is None:
                retracked[i] = numpy.NAN
            else:
                retracked[i] = mle3.data[i] - \
                    (32 - binnumber + 1) * self.GATE_2_METERS
        latitudes = self.variables[
            "lat_20hz"][:][self._get_20hz_mask()].flatten()
        return Height(retracked, numpy.mean(retracked),
                      numpy.std(retracked), latitudes)

    def _get_height(self, range_name):
        correction = self._get_20hz_correction()
        mask20hz = self._get_20hz_mask()
        data = (self.variables["alt_20hz"] -
                correction -
                self.variables[range_name][:])[mask20hz].flatten()
        return Height(data, numpy.mean(data), numpy.std(data),
                      self.variables["lat_20hz"][:][mask20hz].flatten())

    def _jason2time_to_datetime(self, jason2time):
        return datetime.datetime(2000, 1, 1, 0, 0, 0) + \
            datetime.timedelta(seconds=jason2time)

    def _get_1hz_mask(self):
        return numpy.any(self._get_20hz_mask(), 1)

    def _get_20hz_mask(self):
        """Get a location mask for 20hz data."""
        mask = numpy.logical_and(
            self.variables["lat_20hz"][:] >= self.bounds.miny,
            self.variables["lat_20hz"][:] <= self.bounds.maxy)
        if self.bounds.minx is not None:
            mask = numpy.logical_and(
                mask,
                self.variables["lon_20hz"][:] >=
                self.bounds.minx)
        if self.bounds.maxx is not None:
            mask = numpy.logical_and(
                mask,
                self.variables["lon_20hz"][:] <=
                self.bounds.maxx)
        return mask

    def _get_20hz_correction(self):
        correction = (
            self.variables["model_dry_tropo_corr"][:] +
            self.variables["model_wet_tropo_corr"][:] +
            self.variables["iono_corr_gim_ku"][:] +
            self.variables["solid_earth_tide"][:] +
            self.variables["pole_tide"][:]
        )
        correction.shape = (len(correction), 1)
        return numpy.tile(correction, (1, 20))
