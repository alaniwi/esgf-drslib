# BSD Licence
# Copyright (c) 2010, Science & Technology Facilities Council (STFC)
# All rights reserved.
#
# See the LICENSE file in the source distribution of this software for
# the full license text.

'''

The drs module contains a minimal model class for DRS information
and some utility functions for converting filesystem paths to and from
DRS objects.

More sophisticated conversions can be done with the
:mod:`drslib.translate` and :mod:`drslib.cmip5` modules.

'''

import os
import itertools
import re
from abc import ABCMeta
from drslib.exceptions import TranslationError

import logging
log = logging.getLogger(__name__)



class BaseDRS(dict):
    """
    Base class of classes representing DRS entries.
    
    This class provides an interface to:
    1. Define and expose the components of the DRS and their order
    2. Convert components in and out of serialised form
    3. Determine whether a DRS entry is complete
    4. Define the publishing level of datasets represented by this DRS
    
    This class provides default implementations of:
    1. serialisation to dataset-id with or without version
    
    Subclasses decide what components make up the DRS.
    
    :cvar DRS_ATTRS: a sequence of component names in the order they appear in the
                     DRS identifier.
    :cvar PUBLISH_LEVEL: the last component name which is part of the published
                         dataset-id.

    """
    __metaclass__ = ABCMeta

    DRS_ATTRS = NotImplemented
    PUBLISH_LEVEL = NotImplemented
    VERSION_COMPONENT = 'version'
    OPTIONAL_ATTRS = NotImplemented

    def __init__(self, *argv, **kwargs):
        """
        Instantiate a DRS object with a set of DRS component values.

        >>> mydrs = DRS(activity='cmip5', product='output', model='HadGEM1',
        ...             experiment='1pctto4x', variable='tas')
        <DRS activity="cmip5" product="output" model="HadGEM1" ...>

        :param argv: If not () should be a DRS object to instantiate from
        :param kwargs: DRS component values.

        """

        # Initialise all components as None
        for attr in self._iter_components(with_version=True):
            self[attr] = None

        # Check only DRS components are used
        for kw in kwargs:
            if kw not in self._iter_components(with_version=True):
                raise KeyError("Keyword %s is not a DRS component" % repr(kw))

        # Use dict flexible instantiation
        super(BaseDRS, self).__init__(*argv, **kwargs)


    def __getattr__(self, attr):
        if attr in self._iter_components(with_version=True):
            return self[attr]
        else:
            raise AttributeError('%s object has no attribute %s' % 
                                 (repr(type(self).__name__), repr(attr)))

    def __setattr__(self, attr, value):
        if attr in self._iter_components(with_version=True):
            self[attr] = value
        else:
            raise AttributeError('%s is not a DRS component' % repr(attr))

    @classmethod
    def _iter_components(klass, with_version=True, to_publish_level=False):
        """
        Iterate component names including version at the correct point in the
        sequence for publication.

        """
        for attr in klass.DRS_ATTRS:
            yield attr
            if attr == klass.PUBLISH_LEVEL:
                if with_version:
                    yield klass.VERSION_COMPONENT
                if to_publish_level:
                    return

    @classmethod
    def _encode_component(klass, component, value):
        """
        Encode the value of component named `component` as a string and return.

        """
        raise NotImplementedError

    @classmethod
    def _decode_component(klass, component, value):
        """
        Decode the value of component named `component` from a string and 
        return the Python value.

        """
        raise NotImplementedError

    #-------------------------------------------------------------------------
    # Public implemented interfaces

    def is_complete(self):
        """Returns boolean to indicate if all components are specified.
        
        Returns ``True`` if all components excluding those in self.OPTIONAL_ATTRS
        have a value.

        """

        for attr in self._iter_components(with_version=True):
            if attr in self.OPTIONAL_ATTRS:
                continue
            if self.get(attr, None) is None:
                return False

        return True

    def is_publish_level(self):
        """Returns boolian to indicate if the all publish-level components are
        specified.

        """
        for attr in self._iter_components(to_publish_level=True, with_version=False):
            if self.get(attr, None) is None:
                return False
            
        return True
    
    def __repr__(self):
        kws = []
        for attr in self._iter_components(with_version=True, to_publish_level=True):
            kws.append(self._encode_component(attr, self[attr]))

        # Remove trailing '%' from components
        while kws and kws[-1] == '%':
            kws.pop(-1)

        return '<DRS %s>' % '.'.join(kws)

    def to_dataset_id(self, with_version=False):
        """
        Return the esgpublish dataset_id for this drs object.
        
        If version is not None and with_version=True the version is included.

        """
        parts = [self._encode_component(x, self[x]) for x in
                 self._iter_components(with_version=False, to_publish_level=True)]
        if self.version and with_version:
            parts.append(self._encode_component('version', self['version']))
        return '.'.join(parts)

    @classmethod
    def from_dataset_id(klass, dataset_id, **components):
        """
        Return a DRS object fro a ESG Publisher dataset_id.

        If the dataset_id contains less than 10 components all trailing
        components are set to None.  Any component of value '%' is set to None

        E.g.
        >>> drs = DRS.from_dataset_id('cmip5.output.MOHC.%.rpc45')
        >>> drs.institute, drs.model, drs.experiment, drs.realm
        ('MOHC', None, 'rpc45', None)

        """

        parts = dataset_id.split('.')
        for attr, val in itertools.izip(klass._iter_components(with_version=True, to_publish_level=True), parts):
            if val is '%':
                continue
            components[attr] = klass._decode_component(attr, val)
                   
        return klass(**components)


class DRS(BaseDRS):
    """
    Represents a DRS entry.  DRS objects are dictionaries where DRS
    components are also exposed as attributes.  Therefore you can get/set
    DRS components using dictionary or attribute notation.

    In combination with the translator machinary, this class maintains
    consistency between the path and filename portion of the DRS.

    :ivar activity: string
    :ivar product: string
    :ivar institute: string
    :ivar model: string
    :ivar experiment: string
    :ivar frequency: string
    :ivar realm: string
    :ivar variable: string
    :ivar table: string of None
    :ivar ensemble: (r, i, p)
    :ivar version: integer
    :ivar subset: (N1, N2, clim) where N1 and N2 are (y, m, d, h, mn, sec) 
        and clim is boolean
    :ivar extended: A string containing miscellaneous stuff.  Useful for
        representing irregular CMIP3 files

    """

    DRS_ATTRS = ['activity', 'product', 'institute', 'model', 'experiment',
                 'frequency', 'realm', 'table', 'ensemble', 
                 'variable', 'subset', 'extended']
    PUBLISH_LEVEL = 'ensemble'
    OPTIONAL_ATTRS = ['extended']

    @classmethod
    def _encode_component(klass, attr, value):
        """
        Encode a DRS component as a string.  Components that are None
        are encoded as '%'.

        """
        from drslib.translate import _from_date

        #!TODO: this code overlaps serialisation code in translate.py
        if value is None:
            val = '%'
        elif attr is 'ensemble':
            val = _ensemble_to_rip(value)
            if val == '':
                val = '%'
        elif attr is 'version':
            val = 'v%d' % value
        elif attr is 'subset':
            N1, N2, clim = value
            if clim:
                val = '%s-%s-clim' % (_from_date(N1), _from_date(N2))
            else:
                val = '%s-%s' % (_from_date(N1), _from_date(N2))
        else:
            val = value

        return val

    @classmethod
    def _decode_component(klass, attr, val):
        from drslib.translate import _to_date
        
        if val == '%':
            ret = None
        elif attr is 'ensemble':
            if val == (None, None, None):
                ret = None
            else:
                ret = _rip_to_ensemble(val)
        elif attr is 'version':
            if val[0] == 'v':
                ret = int(val[1:])
            else:
                ret = int(val)
        elif attr is 'subset':
            parts = val.split('-')
            if len(parts) > 3:
                raise ValueError('cannot parse extended component %s' % repr(val))
                N1, N2 = _to_date(parts[0]), _to_date(parts[1])
            if len(parts) == 3:
                clim = parts[2]
                if clim != 'clim':
                    raise ValueError('unsupported extended component %s' % repr(val))
            else:
                clim = None
            val = (N1, N2, clim)
        else:
            ret = val
                
        return ret
        

            
def _rip_to_ensemble(rip_str):
    mo = re.match(r'(?:r(\d+))?(?:i(\d+))?(?:p(\d+))?', rip_str)
    if not mo:
        raise TranslationError('Unrecognised ensemble syntax %s' % rip_str)
    
    (r, i, p) = mo.groups()
    return (_int_or_none(r), _int_or_none(i), _int_or_none(p))

def _ensemble_to_rip(ensemble):
    parts = []
    for prefix, val in zip(['r', 'i', 'p'], ensemble):
        if val is None:
            continue
        parts.append('%s%d' % (prefix, val))

    return ''.join(parts)


def _int_or_none(x):
    if x is None:
        return None
    else:
        return int(x)




class DRSFileSystem(object):
    """
    Represents the mapping scheme between :class:`DRS` objects and
    a filesystem.

    Instances of this class deal with how DRS objects are partitioned into
    Publicaiton-level datasets and how files within a DRS are mapped to
    the filesystem.

    :cvar drs_cls: The subclass of :class:`BaseDRS` used in this filesystem.

    :cvar publish_level: the last component name which is part of the published
        dataset-id.

    :ivar drs_root: The path to the root directory of a DRS filesystem.
        This path represents the activity level of the DRS.


    """

    drs_cls = NotImplemented

    def __init__(self, drs_root):
        self.drs_root = drs_root

    def filename_to_drs(self, filename):
        """
        Return a DRS instance deduced from a filename.

        """
        raise NotImplementedError

    def filepath_to_drs(self, filepath):
        """
        Return a DRS instance deduced from a full path.

        """
        raise NotImplementedError

    def publication_path_to_drs(self, path):
        """
        Create a :class:`DRS` object from a filesystem path.

        """
        raise NotImplementedError

    def drs_to_publication_path(self, drs):
        """
        Returns a directory path from a :class:`DRS` object.  Any DRS component
        that is set to None will result in a wildcard '*' element in the path.

        """
        raise NotImplementedError

    def drs_to_publication_subpath(self, drs):
        """
        Return the subpath within the versioning directory for this 
        :class:`DRS` instance.

        """
        raise NotImplementedError

    def publication_subpath_to_drs(self, subpath):
        """
        Return a :class:`DRS` instance representing the DRS components
        deducible from `subpath`.

        """
        raise NotImplementedError

