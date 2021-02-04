""" Tests for amusic module / script
"""

import os
import os.path as op
import shutil
from datetime import date as Date
from glob import glob

from amusic import (MBInfo, DOInfo,
                    strip_nones, read_config,
                    proc_config, build_one, clear_hashes)


import pytest

HERE = op.dirname(__file__)

FUNEBRE_ID = '77441f5e-fb98-42e6-b73d-ed7e8507f855'

FUNEBRE_INFO = \
{'status': 'Official',
 'media': [{'position': 1,
   'format-id': '9712d52a-4509-3d4b-a1a2-67c88c643e31',
   'discs': [{'id': '2KoGCwA7mfWhT6g_.CL28TxZZ.8-',
     'offset-count': 8,
     'sectors': 300107,
     'offsets': [182, 52532, 114407, 129257, 160457, 183857, 234032, 283382]}],
   'format': 'CD',
   'title': '',
   'track-count': 8},
  {'position': 2,
   'format-id': '9712d52a-4509-3d4b-a1a2-67c88c643e31',
   'discs': [],
   'format': 'CD',
   'title': '',
   'track-count': 5}],
 'title': 'Requiem / Symphonie funèbre et triomphale',
 'packaging': 'Jewel Case',
 'status-id': '4e304316-386d-3409-af2e-78857eec5cfe',
 'date': '1985-12-03',
 'disambiguation': '',
 'asin': 'B00000E34S',
 'country': 'XW',
 'text-representation': {'script': 'Latn', 'language': 'eng'},
 'quality': 'normal',
 'packaging-id': 'ec27701a-4a22-37f4-bfac-6616e0f9750a',
 'id': '77441f5e-fb98-42e6-b73d-ed7e8507f855',
 'artist-credit': [{'joinphrase': '; ',
   'artist': {'type': 'Person',
    'disambiguation': 'composer',
    'name': 'Hector Berlioz',
    'type-id': 'b6e035f4-3ce9-331c-97df-83397230b0df',
    'sort-name': 'Berlioz, Hector',
    'id': '274774a7-1cde-486a-bc3d-375ec54d552d'},
   'name': 'Berlioz'},
  {'artist': {'id': '38712b4c-0fd4-4c65-8c7a-45676fecc973',
    'sort-name': 'London Symphony Orchestra',
    'type-id': 'a0b36c92-3eb1-3839-a4f9-4799823f54a5',
    'name': 'London Symphony Orchestra',
    'type': 'Orchestra',
    'disambiguation': ''},
   'joinphrase': ', ',
   'name': 'London Symphony Orchestra'},
  {'name': 'London Symphony Chorus',
   'artist': {'id': '12133eec-2c6c-4689-a102-8a558b82dde9',
    'sort-name': 'London Symphony Chorus',
    'type-id': '6124967d-7e3a-3eba-b642-c9a2ffb44d94',
    'name': 'London Symphony Chorus',
    'type': 'Choir',
    'disambiguation': ''},
   'joinphrase': ', '},
  {'artist': {'id': '68ee0381-c3a6-4b41-ad68-9de513e8e97f',
    'sort-name': 'Davis, Colin, Sir',
    'name': 'Sir Colin Davis',
    'type-id': 'b6e035f4-3ce9-331c-97df-83397230b0df',
    'disambiguation': 'English conductor',
    'type': 'Person'},
   'joinphrase': '',
   'name': 'Sir Colin Davis'}],
 'label-info': [{'label': {'type-id': '7aaa37fe-2def-3476-b359-80245850062d',
    'name': 'Philips',
    'disambiguation': '',
    'label-code': 305,
    'type': 'Original Production',
    'id': '6d38d6d2-bea8-46cf-b48e-a6195fd85f12',
    'sort-name': 'Philips'},
   'catalog-number': '416 283-2'}],
 'barcode': '028941628329',
 'release-events': [{'area': {'sort-name': '[Worldwide]',
    'id': '525d4e18-3d00-31b9-a58b-a146a916de8f',
    'iso-3166-1-codes': ['XW'],
    'disambiguation': '',
    'type': None,
    'type-id': None,
    'name': '[Worldwide]'},
   'date': '1985-12-03'}],
 'cover-art-archive': {'darkened': False,
  'front': False,
  'back': False,
  'count': 0,
  'artwork': False}}


def test_strip_nones():
    assert strip_nones(1) == 1
    assert strip_nones(None) is None
    assert strip_nones([1, 2, 3]) == [1, 2, 3]
    assert strip_nones([1, None, 3]) == [1, 3]
    assert strip_nones([None, None, None]) is None
    assert strip_nones({'a': 1, 'b': 2}) == {'a': 1, 'b': 2}
    assert strip_nones({'a': None, 'b': 2}) == {'b': 2}
    assert strip_nones({'a': None, 'b': None}) is None
    assert strip_nones({'a': 1, 'b': [1, 2]}) == {'a': 1, 'b': [1, 2]}
    assert strip_nones({'a': 1, 'b': [1, None]}) == {'a': 1, 'b': [1]}
    assert strip_nones({'a': 1, 'b': [None, None]}) == {'a': 1}
    assert strip_nones({'a': 1, 'b': {'c': 3}}) == {'a': 1, 'b': {'c': 3}}
    assert strip_nones({'a': 1, 'b': {'c': None}}) == {'a': 1}
    assert strip_nones([1, [2, 3]]) == [1, [2, 3]]
    assert strip_nones([1, [2, None]]) == [1, [2]]
    assert strip_nones([1, [None, None]]) == [1]
    assert strip_nones([1, (2, None)]) == [1, (2,)]
    assert strip_nones([1, (None, None)]) == [1]
    assert strip_nones([1, (None, None)]) == [1]
    assert strip_nones((1, (None, None))) == (1,)


def test_mbinfo():
    mbi = MBInfo(FUNEBRE_INFO)
    composers = mbi.composers
    assert len(composers) == 1
    assert composers[0]['name'] == 'Hector Berlioz'
    assert composers[0]['sort-name'] == 'Berlioz, Hector'
    assert mbi.composer == composers[0]
    conductors = mbi.conductors
    assert len(conductors) == 1
    assert conductors[0]['name'] == 'Sir Colin Davis'
    assert mbi.conductor == conductors[0]
    orchestras = mbi.orchestras
    assert len(orchestras) == 1
    assert orchestras[0]['name'] == 'London Symphony Orchestra'
    assert mbi.orchestra == orchestras[0]
    choirs = mbi.choirs
    assert len(choirs) == 1
    assert choirs[0]['name'] == 'London Symphony Chorus'
    assert mbi.choir == choirs[0]
    assert mbi.date == Date(1985, 12, 3)
    assert mbi.year == 1985


def test_get_mbinfo():
    mbi = MBInfo(FUNEBRE_INFO)
    mbi2 = MBInfo.from_release(FUNEBRE_ID)
    assert mbi.as_config() == mbi2.as_config()


def test_doinfo():
    # https://www.discogs.com/Palestrina-Monteverdi-Netherlands-Chamber-Choir-Felix-De-Nobel-Palestrina-Monteverdi/release/7793083
    mbi = DOInfo.from_release(7793083)
    composers = mbi.composers
    assert len(composers) == 2
    assert composers[0]['name'] == 'Claudio Monteverdi'
    assert composers[1]['name'] == 'Giovanni Pierluigi Da Palestrina'
    conductors = mbi.conductors
    assert len(conductors) == 1
    assert conductors[0]['name'] == 'Felix De Nobel'
    assert mbi.conductor == conductors[0]
    orchestras = mbi.orchestras
    assert len(orchestras) == 1
    assert orchestras[0]['name'] == 'Nederlands Kamerkoor'
    assert mbi.orchestra == orchestras[0]
    choirs = mbi.choirs
    assert len(choirs) == 0
    assert mbi.date is None
    assert mbi.year is None


def glob_rm(glob_str):
    for fn in glob(glob_str, recursive=True):
        os.unlink(fn)


def test_build_one():
    config_fname = op.join(HERE, 'amusic_config.yml')
    config = read_config(config_fname)
    settings, tracks = proc_config(config, HERE)
    assert len(tracks) == 1
    fbase, config = list(tracks.items())[0]
    out_path = op.join(HERE, 'amusic_tmp')
    # Clear output path
    if op.isdir(out_path):
        shutil.rmtree(out_path)
    # Clear input file hashes
    clear_hashes('wavs')
    clear_hashes('images')
    # Do a build
    build_one(fbase, config, settings)
    assert op.isdir(out_path)
    # Hashes match, no error.
    build_one(fbase, config, settings, True)
    # Change album details, hashes don't match, error
    config['album'] = 'Eldorado'
    with pytest.raises(RuntimeError):
        build_one(fbase, config, settings)
    build_one(fbase, config, settings, True)
    # Hashes match, no error.
    build_one(fbase, config, settings)
    # Delete input hashes, error again
    clear_hashes('wavs')
    with pytest.raises(RuntimeError):
        build_one(fbase, config, settings)
    build_one(fbase, config, settings, True)
    # Delete output hashes, error again
    glob_rm(op.join(out_path, '**', '*.mp3.md5'))
    with pytest.raises(RuntimeError):
        build_one(fbase, config, settings)
    build_one(fbase, config, settings, True)
    # Delete image input hashes, error again
    clear_hashes('images')
    with pytest.raises(RuntimeError):
        build_one(fbase, config, settings)
    build_one(fbase, config, settings, True)
    # Delete output hashes, error again
    glob_rm(op.join(out_path, '**', '*.jpg.md5'))
    with pytest.raises(RuntimeError):
        build_one(fbase, config, settings)
    build_one(fbase, config, settings, True)
    # Clear input file hashes
    clear_hashes('wavs')
    clear_hashes('images')
