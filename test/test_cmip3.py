# BSD Licence
# Copyright (c) 2010, Science & Technology Facilities Council (STFC)
# All rights reserved.
#
# See the LICENSE file in the source distribution of this software for
# the full license text.

"""
Tests compatible with nosetests

"""


import os

from drslib import cmip3, cmip5

translator = cmip3.make_translator('/')
cmip5_translator = cmip5.make_translator('cmip5')

def test_1():
    p = '/20c3m/atm/da/rsus/gfdl_cm2_0/run1/rsus_A2.19610101-19651231.nc'
    p2 = convert(p)
    assert p2 == 'cmip5/output/GFDL/CM2/20c3m/day/atmos/A2/r1/v%s/rsus/rsus_A2_CM2_20c3m_r1_19610101-19651231.nc' % cmip3.today_version
    
def test_listing():
    """
    Test successful conversion of part of the CMIP3 listing
    
    """
    
    fh = open(os.path.join(os.path.dirname(__file__), 'cmip3_test_ls'))
    for line in fh:
        yield convert, line.strip()
    
def convert(filepath):
    print ('%s -->' % filepath),
    drs = translator.filepath_to_drs(filepath)
    cmip5_filepath = cmip5_translator.drs_to_filepath(drs)

    print cmip5_filepath
    
    return cmip5_filepath

def test_var_underscore():
    """test_var_underscore

    Regression test found in CMIP3 when a variable contains an underscore.

    """
    p = '/1pctto2x/atm/mo/rlftoaa_co2/ipsl_cm4/run1/rlftoaa_co2_A5_1860-1869.nc'
    p2 = convert(p)

    assert p2 == 'cmip5/output/IPSL/CM4/1pctto2x/mon/atmos/A5/r1/v%s/rlftoaa_co2/rlftoaa_co2_A5_CM4_1pctto2x_r1_1860-1869.nc' % cmip3.today_version

############################################################################
# Tests on new DRS structure (including mip_table) start here
#
def test_table():
    p = '/sresb1/ocn/mo/wfo/csiro_mk3_5/run1/wfo_O1c_2211-2220_SRESB1_mk3.5_run1.nc'
    drs = translator.filepath_to_drs(p)

    print drs
    assert drs.table == 'O1c'

