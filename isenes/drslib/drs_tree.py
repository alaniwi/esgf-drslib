"""
Classes modelling the DRS directory hierarchy.

"""

import os, shutil
from glob import glob
import re
import stat

import cdms2


from isenes.drslib.cmip5 import make_translator
from isenes.drslib.drs import DRS, cmorpath_to_drs, drs_to_cmorpath
from isenes.drslib import config

import logging
log = logging.getLogger(__name__)

#---------------------------------------------------------------------------
# DRY definitions

VERSIONING_FILES_DIR = 'files'
VERSIONING_LATEST_DIR = 'latest'

#---------------------------------------------------------------------------

class DRSTree(object):
    """
    Manage a Data Reference Syntax directory structure.

    """

    def __init__(self, drs_root):
        self.drs_root = drs_root
        self.realm_trees = []
        self.next_version = None
        
        
    def discover(self, product=None, institute=None, model=None, 
                 experiment=None,
                 frequency=None, realm=None):
        """
        Scan the directory structure for RealmTrees.

        This implementation is a compromise between the need to
        auto-discover RealmTrees and the fact that scanning the entire
        DRSTree may be infeasible.  You must specify the are of the
        DRS to scan up to the model level.

        """

        drs = DRS(product=product, institute=institute, model=model,
                  experiment=experiment, frequency=frequency, realm=realm)

        # Grab options from the config
        if not product:
            product = config.drs_defaults.get('product')
        if not institute:
            institute = config.drs_defaults.get('institute')
        if not model:
            model = config.drs_defaults.get('model')

        if product is None or institute is None or model is None:
            raise Exception("Insufficiently specified DRS.  You must define product, institute and model.")

        # If these options are not specified they default to wildcards
        if not frequency:
            drs.frequency = '*'
        if not realm:
            drs.realm = '*'
        if not experiment:
            drs.experiment = '*'

        rt_glob = drs_to_cmorpath(self.drs_root, drs)
        realm_trees = glob(rt_glob)
        for rt_path in realm_trees:
            drs = cmorpath_to_drs(self.drs_root, rt_path)
            log.info('Discovered realm-tree at %s' % rt_path)
            self.realm_trees.append(RealmTree(self.drs_root, drs))

class RealmTree(object):
    """
    A directory tree at the Realm level.

    """
    #!TODO: At some point we want to check incoming files to see if they are
    #       duplicates of already versioned files.

    STATE_INITIAL = 'INITIAL'
    STATE_VERSIONED = 'VERSIONED'
    STATE_VERSIONED_TRANS = 'VERSIONED_TRANS'

    CMD_MOVE = 0
    CMD_LINK = 1

    DIFF_NONE = 0
    DIFF_TRACKING_ID = 1
    DIFF_SIZE = 2
    DIFF_V1_ONLY = 4
    DIFF_V2_ONLY = 8

    def __init__(self, drs_root, drs):
        """
        A part of the drs tree containing 1 realm.

        This class works out what state the tree is in

        """

        self.drs_root = drs_root
        self.drs = drs
        self.state = None
        self._todo = []
        self.versions = {}
        self._vtrans = make_translator(drs_root)
        self._cmortrans = make_translator(drs_root, with_version=False)

        self.realm_dir = os.path.join(self.drs_root,
                                      self.drs.product,
                                      self.drs.institute,
                                      self.drs.model,
                                      self.drs.experiment,
                                      self.drs.frequency,
                                      self.drs.realm)
        if not os.path.exists(self.realm_dir):
            raise RuntimeError('Realm directory %s does not exist' % self.realm_dir)

        self.deduce_state()
        self._setup_versioning()

    @classmethod
    def from_path(Class, path):
        """
        Construct a RealmTree from a realm-level filesystem path.

        """
        p = os.path.normpath(os.path.abspath(path))
        p, realm = os.path.split(p)
        p, frequency = os.path.split(p)
        p, experiment = os.path.split(p)
        p, model = os.path.split(p)
        p, institute = os.path.split(p)
        p, product = os.path.split(p)
        drs_root = p

        drs = DRS(realm=realm, frequency=frequency, experiment=experiment,
                  model=model, institute=institute, product=product)

        return Class(drs_root, drs)

    def deduce_state(self):
        """
        Scan the directory structure to work out what state the
        tree is in.

        """

        self._deduce_versions()
        self._deduce_todo()

        if not self.versions:
            self.state = self.STATE_INITIAL
        elif self._todo:
            self.state = self.STATE_VERSIONED_TRANS
        else:
            self.state = self.STATE_VERSIONED


    def do_version(self):
        """
        Move incoming files into the next version

        """
        log.info('Transfering %s to version %d' % (self.realm_dir, self.next_version))
        self._do_commands(self._todo_commands())
        self.deduce_state()
        self._do_latest()

    def list_todo(self):
        """
        Return an iterable of command descriptions in the todo list.

        """
        for cmd, src, dest in self._todo_commands():
            if cmd == self.CMD_MOVE:
                yield "mv %s %s" % (src, dest)
            elif cmd == self.CMD_LINK:
                yield "ln -s %s %s" % (src, dest)
            else:
                raise Exception("Unrecognised command type")


    def diff_version(self, v1, v2=None, by_tracking_id=False):
        """
        Deduce the difference between two versions or between a version
        and the todo list.
        """
        
        files1 = {}
        for filepath, drs in self.versions[v1]:
            files1[os.path.basename(filepath)] = filepath

        if v2 is None:
            fl = self._todo
        else:
            fl = self.versions[v2]

        files2 = {}
        for filepath, drs in fl:
            files2[os.path.basename(filepath)] = filepath

        for file in set(files1.keys() + files2.keys()):
            if file in  files1 and file in files2:
                yield (self._diff_file(files1[file], files2[file], 
                                       by_tracking_id),
                       files1[file], files2[file])
            elif file in files1:
                yield (self.DIFF_V1_ONLY, files1[file], None)
            else:
                yield (self.DIFF_V2_ONLY, None, files2[file])


    #-------------------------------------------------------------------
    
    def _do_latest(self):
        version = max(self.versions.keys())
        latest_dir = 'v%d' % version
        log.info('Setting latest to %s' % latest_dir)
        latest_lnk = os.path.join(self.realm_dir, VERSIONING_LATEST_DIR)

        if os.path.exists(latest_lnk):
            os.remove(latest_lnk)
        os.symlink(latest_dir, latest_lnk)

    def _todo_commands(self):
        """
        Yield a sequence of tuples (CMD, SRS, DEST) indicating the
        files that need to be moved and linked to transfer to next version.

        """
        v = self.next_version
        done = set()
        for filepath, drs in self._todo:
            filename = os.path.basename(filepath)
            ensemble = 'r%di%dp%d' % drs.ensemble
            fdir = '%s_%s_%d' % (drs.variable, ensemble, v)
            newpath = os.path.join(self.realm_dir, VERSIONING_FILES_DIR,
                                   fdir, filename)

            yield self.CMD_MOVE, filepath, newpath

            linkpath = os.path.join(self.realm_dir, 'v%d' % v,
                                    drs.variable, ensemble, 
                                    filename)
            yield self.CMD_LINK, newpath, linkpath
            done.add(filename)

        #!TODO: Handle deleted files!

        # Now scan through previous version to find files to update
        if v > 1:
            for filepath, drs in self.versions[v-1]:
                filename = os.path.basename(filepath)
                if filename not in done:
                    ensemble = 'r%di%dp%d' % drs.ensemble
                    fdir = '%s_%s_%d' % (drs.variable, ensemble, v-1)
                    linkpath = os.path.join(self.realm_dir, 'v%d' % v,
                                            drs.variable, ensemble, filename)
                    pfilepath = os.path.join(self.realm_dir, VERSIONING_FILES_DIR,
                                             fdir, filename)
                    yield self.CMD_LINK, pfilepath, linkpath

    def _do_commands(self, commands):
        for cmd, src, dest in commands:
            if cmd == self.CMD_MOVE:
                self._do_mv(src, dest)
            elif cmd == self.CMD_LINK:
                self._do_link(src, dest)
            

    def _do_mv(self, src, dest):
        dir = os.path.dirname(dest)
        if not os.path.exists(dir):
            log.info('Creating %s' % dir)
            os.makedirs(dir)
        log.info('Moving %s %s' % (src, dest))
        shutil.move(src, dest)

    def _do_link(self, src, dest):
        dir = os.path.dirname(dest)
        if not os.path.exists(dir):
            log.info('Creating %s' % dir)
            os.makedirs(dir)
        log.info('Linking %s %s' % (src, dest))
        os.symlink(src, dest)

    def _setup_versioning(self):
        """
        Do initial configuration of directory tree to support versioning.

        """
        path = os.path.join(self.realm_dir, VERSIONING_FILES_DIR)
        if not os.path.exists(path):
            log.info('Initialising %s for versioning.' % self.realm_dir)
            os.mkdir(path)


    def _deduce_versions(self):
        i = 1
        v = self.versions
        while True:
            vpath = os.path.join(self.realm_dir, 'v%d' % i)
            if not os.path.exists(vpath):
                self.next_version = i
                return v

            contents = []
            for dirpath, dirnames, filenames in os.walk(vpath,
                                                        topdown=False):
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    drs = self._vtrans.filepath_to_drs(filepath)
                    contents.append((filepath, drs))
            v[i] = contents
            
            i += 1
            
    def _deduce_todo(self):
        #!WARNING: Only call after _deduce_versions()
        todo = self._todo = []
        
        for dir in os.listdir(self.realm_dir):
            pat = r'%s|%s|v\d+' % (VERSIONING_FILES_DIR, VERSIONING_LATEST_DIR)
            if re.match(pat, dir):
                continue

            path = os.path.join(self.realm_dir, dir)
            for dirpath, dirnames, filenames in os.walk(path, topdown=False):
                for filepath in (os.path.join(dirpath, f) for f in filenames):
                    drs = self._cmortrans.filepath_to_drs(filepath)
                    todo.append((filepath, drs))


    def _diff_file(self, filepath1, filepath2, by_tracking_id=False):
        diff_state = self.DIFF_NONE

        # Check files are the same size
        if _get_size(filepath1) != _get_size(filepath2):
            diff_state |= self.DIFF_SIZE

        # Check by tracking_id
        if by_tracking_id:
            if filepath1[-3:] == filepath2[-3:] == '.nc':
                if _get_tracking_id(filepath1) != _get_tracking_id(filepath2):
                    diff_state |= state.DIFF_TRACKING_ID

        #!TODO: what about md5sum?  This would be slow, particularly as
        #       esgpublish does it anyway.

        return diff_state


def _get_tracking_id(filename):
    ds = cdms2.open(filename)
    return ds.tracking_id

def _get_size(filename):
    return os.stat(filename)[stat.ST_SIZE]
