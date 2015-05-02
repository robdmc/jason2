import fnmatch
import ftplib
import os

from jason2.exceptions import ConnectionError


def zfill3(integer):
    return str(integer).zfill(3)


def jason2_glob(product, cycle, track):
    # FIXME this is way too dumb
    if product == "gdr_d":
        product_type = "N"
    elif product == "sgdr_d":
        product_type = "S"
    cycle_str = zfill3(cycle)
    track_str = zfill3(track)
    # FIXME also way too dumb
    extension = ".nc" if product == "gdr_d" else ".zip"
    return "JA2_GP{}_2PdP{}_{}_*{}".format(product_type, cycle_str, track_str,
                                           extension)


class FtpConnection(object):

    SERVER = "avisoftp.cnes.fr"
    ROOT_PATH = "/Niveau0/AVISO/pub/jason2/"

    def __init__(self, email):
        self.email = email
        self.connection = None

    def __enter__(self):
        self.connection = ftplib.FTP(self.server)
        self.connection.login("anonymous", self.email)
        return self

    def __exit__(self):
        self.connection.close()
        self.connection = None

    def fetch(self, product, cycle, tracks, data_directory):
        if self.connection is None:
            raise ConnectionError("Not connected to FTP server")
        cycle_str = zfill3(cycle)
        self.connection.cwd(os.path.join(self.ROOT_PATH, product,
                                         cycle_str))
        for track in tracks:
            glob = jason2_glob(product, cycle, track)
            filenames = fnmatch.filter(self.connection.nlist(), glob)
            assert len(filenames) == 1
            filename = filenames[0]
            outfile = os.path.join(data_directory, product, cycle_str,
                                   filename)
            self.connection.retrbinary("RETR {}".format(filename),
                                       open(outfile, "wb").write)
