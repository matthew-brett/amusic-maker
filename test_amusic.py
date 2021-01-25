""" Tests for amusic module / script
"""

from amusic import get_mb_release, MBInfo

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


def test_mb_track_info():
    # Check info hasn't changed.  If it has, we have to 
    # change the tests
    info = get_mb_release(FUNEBRE_ID)
    assert info == FUNEBRE_INFO


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
