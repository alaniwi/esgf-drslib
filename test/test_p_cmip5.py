"""
This test module uses the functional test features of nose.

"""

import tempfile, os, shutil
import zipfile

import drslib.p_cmip5.product as p
from drslib.p_cmip5 import init

from nose import with_setup

verbose = False

pc1 = None
pc2 = None
tmpdir = None


def setup_module():
    global pc1, pc2, tmpdir
    tmpdir = tempfile.mkdtemp(prefix='p_cmip5-')
    print 'TMPDIR   ',tmpdir
    shelve_dir = os.path.join(tmpdir, 'sh')

    # Example config file is in test directory
    test_dir = os.path.dirname(__file__)
    config1 = os.path.join(test_dir, 'sample_1.ini')
    config2 = os.path.join(test_dir, 'sample_2.ini')

    # Shelves are regenerated each time.  This could be optimised.
    init.init(shelve_dir)
    shelves = init._find_shelves(shelve_dir)

    # Create the dummy data
    z = zipfile.ZipFile(os.path.join(test_dir, 'dummy_archive.zip'))
    z.extractall(path=tmpdir)

    pc1 = p.cmip5_product(mip_table_shelve=shelves['stdo_mip'],
                          template=shelves['template'],
                          stdo=shelves['stdo'],
                          config=config1, not_ok_excpt=False)
    pc2 = p.cmip5_product(mip_table_shelve=shelves['stdo_mip'],
                          template=shelves['template'],
                          stdo=shelves['stdo'],
                          config=config2, not_ok_excpt=False)

def teardown_module():
    shutil.rmtree(tmpdir)

def do_product2(var, mip, expt,path, startyear,
            pci=None,path_output1=None,path_output2=None,verbose=False, tab='    ',selective_ads_scan=False):
    model = 'HADCM3'

    if path != None:
      path = os.path.join(tmpdir, path)
    if path_output1 != None:
      path_output1 = os.path.join(tmpdir, path_output1)
    if path_output2 != None:
      path_output2 = os.path.join(tmpdir, path_output2)

    if pci is None:
        pci = pc1

    if startyear == -999:
       pci.find_product_ads( var, mip, expt,model,path, verbose=verbose,selective_ads_scan=selective_ads_scan)
    else:
       pci.find_product( var, mip, expt,model,path,startyear=startyear,path_output1=path_output1,path_output2=path_output2, verbose=verbose,selective_ads_scan=selective_ads_scan)

    return (pci.product, pci.rc)

def check_product3(args, kwargs, expect=None):
    r = do_product2(*args, **kwargs)
    if expect:
      if type( expect) == type( () ):
        assert r == expect, '%s :: %s' % (str(r),str(expect))
      else:
        assert r[0] == expect, '%s :: %s' % (str(r),str(expect))

def test_gen():
    for var in ['tas','pr','ua']:
        for mip in ['3hr','day']:
            if mip == '3hr':
                expect = 'output2'
            else:
                expect = 'output1'
            yield check_product3, (var, mip, 'rcp45', 'tmp/a_2005_2100', 2050), {}, expect


def test_gen2():
    yield  check_product3, ('tas', '3hr', 'rcp45', 'tmp/a_2010_2020', 2090), {}
    yield  check_product3, ('tas', '3hr', 'rcp60', 'tmp/a_2010_2020', 2090), {}
    yield  check_product3, ('hus', '6hrLev', 'historical', 'tmp/a_1930_2000', 1949), {}, ('output1', 'OK013' )
    yield  check_product3, ('hus', '6hrLev', 'historical', 'tmp/a2_1930_2000', 1949), {'selective_ads_scan':True}, ('output1', 'OK013' )

def test_gen3():
    print '3d aero field'
    yield check_product3, ( 'sconcdust', 'aero', 'rcp85', 'tmp/a_2010_2020', 2015), {}, 'output2'
    yield check_product3, ( 'rhs', 'day', 'historical', 'tmp/a_2005_2100', -999), {}, 'split'
    yield check_product3, ( 'rhs', 'day', 'historicalxxx', 'tmp/a_2005_2100', -999), {}, 'output1'
    yield check_product3, ( 'rhs', 'day', 'historical', 'tmp/a_1930_2000', -999), {}, 'split'
    yield check_product3, ( 'rhs', 'day', 'historical', 'tmp/a_1930_2000', -999), dict( pci=pc2 ), 'split'
    yield check_product3, ( 'rhs', 'day', 'piControl', 'tmp/a_1930_2000', -999), {}, 'split'

def test_gen4():
    print 'test using sample_2.ini, in which there is a 30 year offset between dating in historical and piControl'
    yield check_product3, ( 'rhs', 'day', 'piControl', 'tmp/a_1930_2000', -999 ), dict( verbose=verbose, pci=pc2 ), 'split'
    yield check_product3, ( 'tas', '3hr', 'piControl', 'tmp/a_2005_2100', -999 ),  {},'split'
    yield check_product3, ( 'tas', '3hr', 'historical', 'tmp/a_1930_2000', 1990 ),  {},'output1'
    yield check_product3, ( 'tasxx', '3hr', 'rcp45', None, 1990 ),  {},'output2'
    yield check_product3, ( 'intpdiaz', 'Omon', 'rcp45', 'tmp/a_2010_2020', 2050 ),  {},'output1'
    yield check_product3, ( 'intpp', 'Omon', 'rcp45', 'tmp/a_2010_2020', 2050 ),  {},'output1'
    yield check_product3, ( 'sconcno3', 'aero', 'piControl', 'tmp/a_2010_2020', 2050 ), {}, 'output1'
    yield check_product3, ( 'ta', '6hrPlev', 'midHolocene', 'tmp/a_1001_1050', 1040 ), {}, ('output1','OK200.01')
    yield check_product3, ( 'ta', '6hrPlev', 'midHolocene', 'tmp/a_1001_1050', 1040 ), {'path_output1':'tmp/a_1001_1030'}, ('Failed','ERR007')
    yield check_product3, ( 'ta', '6hrPlev', 'midHolocene', 'tmp/a_2005_2100', -999 ), {}, 'split'
    yield check_product3, ( 'emioa', 'aero', 'decadal2005', 'tmp/a_2005_2100', -999 ), {}, 'output1'
    yield check_product3, ( 'sconcnh4', 'aero', 'decadal2005', 'tmp/a_2005_2100', -999 ), {}, 'split'
    yield check_product3, ( 'sconcnh4', 'aero', 'decadal2005', 'tmp/a_2005_2100', 2010 ), {}, 'output2'
    yield check_product3, ( 'sconcnh4', 'aero', 'decadal2005', 'tmp/a_2005_2100', 2015 ), {}, 'output1'
    yield check_product3, ( 'sconcnh4', 'aero', 'decadal2005', 'tmp/a_2005_2100', 2045 ), {}, 'output2'
    yield check_product3, ( 'sconcnh4', 'aero', 'decadal2001', 'tmp/a_2005_2100', -999 ), {}, 'split'

def test_gen5():
    print 'cfMon, section 1'
    yield check_product3, ( 'rlu', 'cfMon', 'amip', 'tmp/a_1930_2000', 1990 ), {}, ('output1','OK300')
    yield check_product3, ( 'rlu', 'cfMon', 'amip', 'tmp/single', None ), {}, ('output1','OK012')

def test_gen6():
    print 'cfMon, section 2'
    yield check_product3, ( 'rlut4co2', 'cfMon', 'piControl', 'tmp/a_1930_2000', 1950 ), {}, ('output1','OK100')

def test_gen7():
    print 'cfMon, section 3'
    yield check_product3, ( 'rlu4co2', 'cfMon', 'amip', 'tmp/a_1930_2000', 1980 ), {}, ('output1','OK300')
    yield check_product3, ( 'rlu4co2', 'cfMon', 'piControl', 'tmp/a_1930_2000', 1950  ), {}, ('output1','OK008.2')

def test_gen8():
    print '------------ cfMon, section 4 --------------'
    yield check_product3, ( 'clisccp', 'cfMon', 'amip', 'tmp/a_1930_2000', 1980 ), {}, ('output1', 'OK300')
    yield check_product3, ( 'clisccp', 'cfMon', 'piControl', 'tmp/a_2005_2100', 2020 ), {}, ('output1', 'OK200')
    yield check_product3, ( 'clisccp', 'cfMon', 'piControl', 'tmp/a_2005_2100', 2040 ), {}, ('output2', 'OK200')
    yield check_product3, ( 'clisccp', 'cfMon', 'abrupt4xco2', 'tmp/a_2010_2020', 2015 ), {}, ('output1','OK009.2')

##( 'rlu4co2', 'cfMon', 'piControl', startyear=2000, endyear=2000, path='./tmp/a_2010_2020', expected=('output1', 'OK008.2') )


def txxx_drs_tree():
    """
    Test drs_tree interface to p_cmip5.
    """
    from drslib import drs_tree

    # Point drs_root at /tmp since we won't be making any upgrades.
    dt = drs_tree.DRSTree('/tmp')
    dt.set_p_cmip5(pc1)
    dt.discover(os.path.join(tmpdir, 'tmp/tas'), activity='cmip5', institute='UKMO')

    #!TODO: More robust test here.
    datasets = set(dt.pub_trees.keys())
    assert datasets == set("""
cmip5.output2.UKMO.HADCM3.piControl.3hr.atmos.3hr.r1i1p1
cmip5.output2.UKMO.HADCM3.piControl.3hr.atmos.3hr.r2i1p1
cmip5.output1.UKMO.HADCM3.piControl.3hr.atmos.3hr.r1i1p1
cmip5.output1.UKMO.HADCM3.piControl.day.atmos.day.r3i1p1
cmip5.output1.UKMO.HADCM3.piControl.3hr.atmos.3hr.r2i1p1
""".strip().split())


for x in test_gen8():
   print x
