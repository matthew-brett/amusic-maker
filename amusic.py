#!/usr/bin/env python
""" Process WAV files into Android music folder
"""

import os
import os.path as op
from datetime import date as Date, datetime as DTM
from copy import deepcopy
import json
from subprocess import check_call
from argparse import ArgumentParser, RawDescriptionHelpFormatter

import requests
import yaml
from PIL import Image

import taglib

HERE = op.dirname(__file__)
CONFIG_BASENAME = 'amusic_config.yml'

MBZ_URL_FMT = (
    'https://musicbrainz.org/ws/2/release/'
    '{release_id}?inc='
    # 'genres+'
    'artist-credits+labels+discids'
    # '+work-rels+work-level-rels'
    '&fmt=json'
)


def_track_config = {
    'media': 'Vinyl',
    'source': 'Vinyl (Lossless)',
    'releasestatus': 'official',
    'releasetype': 'album',
    'script': 'Latn'
}


DEFAULT_TRACK_CONFIG = {
    'folder_name': None,
    'img_fname': None,
    'album': 'Mass in B Minor',
    'albumartist': 'The Sixteen',
    'albumartistsort': 'Sixteen, The',
    'artist': 'Johann Sebastian Bach',
    'artists': 'Johann Sebastian Bach',
    'artistsort': 'Bach, Johann Sebastian',
    'composer': 'Johann Sebastian Bach',
    'conductor': 'Harry Christophers',
    'title': 'BWV 232 Kyrie / Chorus - Kyrie eleison',
    'soloists': ['Catherine Dubosc'],
    'discnumber': 1,
    'disctotal': 1,
    'tracknumber': 1,
    'tracktotal': 2,
    'originaldate': Date(1994, 4, 1),
    'originalyear': 1994,
    'period': 'Baroque',
    'style': 'Choral'}


def read_config(config_fname):
    """ Read, process config file `config_fname`

    Parameters
    ----------
    config_fname : str
        Path for configuration file.

    Returns
    -------
    config : dict
        Configuration.
    """
    with open(config_fname, 'rt') as fobj:
        res = yaml.load(fobj, Loader=yaml.SafeLoader)
    return res


def proc_config(config, config_path):
    config_path = op.abspath(config_path)
    tracks = deepcopy(config)
    settings = tracks.pop('settings')
    for key, value in settings.items():
        if not key.endswith('_path'):
            continue
        # Allow home directory expansion.
        value = op.expanduser(value)
        if not op.isabs(value):
            value = op.join(config_path, value)
        settings[key] = value
    return settings, tracks


def resize_img(img, target_res=1024):
    if max(img.size) <= target_res:
        return img
    ratio = target_res / max(img.size)
    new_size = tuple(int(d * ratio) for d in img.size)
    return img.resize(new_size, Image.LANCZOS)


def find_file(fbase, paths):
    search_paths = ['.'] + paths
    for dn in search_paths:
        fname = op.join(dn, fbase)
        if op.isfile(fname):
            return fname
    raise RuntimeError(f'Could not find {fname} in ' +
                       op.pathsep.join(search_paths))


def convert_file(in_fname, out_fname):
    check_call(['sox', in_fname, '-C', '320', out_fname])


def build_one(fbase, config, settings, clobber=False):
    in_fname = find_file(fbase, settings['wav_paths'])
    entry = config.copy()
    folder_name = entry.pop('folder_name')
    full_out_dir = op.join(settings['out_path'], folder_name)
    if not op.isdir(full_out_dir):
        os.makedirs(full_out_dir)
    fname = folder_name
    in_img_fname = entry.pop('img_fname')
    img_fname = find_file(in_img_fname, settings['img_paths'])
    assert op.exists(img_fname)
    full = def_track_config.copy()
    full.update(entry)
    disc_total = full.get('disctotal')
    if disc_total:
        if disc_total > 1:
            disc_no = full['discnumber']
            fname = f'{fname}_d{disc_no}'
        full['totaldiscs'] = disc_total
    if 'tracktotal' in full:
        full['totaltracks'] = full['tracktotal']
    track_no = full['tracknumber']
    fname = f'{fname}_side{track_no:02d}.mp3'
    full_out_fname = op.join(full_out_dir, fname)
    if op.exists(full_out_fname) and not clobber:
        raise RuntimeError(f'File {full_out_fname} exists')
    convert_file(in_fname, full_out_fname)
    song = taglib.File(full_out_fname)
    # All the rest are tags
    for key, value in entry.items():
        if not isinstance(value, list):
            value = [str(value)]
        song.tags[key.upper()] = value
    song.save()
    out_img_fname = op.join(full_out_dir, 'Folder.jpg')
    if op.exists(out_img_fname) and not clobber:
        raise RuntimeError(f'File {out_img_fname} exists')
    img = Image.open(img_fname)
    img = resize_img(img, 1024)
    img.save(out_img_fname)


def write_config(config, config_fname):
    with open(config_fname, 'wt') as fobj:
        yaml.dump(config, fobj,
                  indent=4,
                  allow_unicode=True,
                  encoding='utf-8',
                  sort_keys=False)


def strip_nones(val):
    """ Remove None and empty values from dictionary / sequence
    """
    if isinstance(val, dict):
        out = {k: s for k, v in val.items()
               if (s := strip_nones(v)) is not None}
    elif isinstance(val, (list, tuple)):
        out = val.__class__(
            s for v in val if (s := strip_nones(v)) is not None)
    else:
        return val
    return out if len(out) else None


class MBInfo:

    def __init__(self, in_dict):
        self._in_dict = in_dict
        self._credits = self._in_dict.get(
            'artist-credit', [])
        self._artists = [d['artist'] for d in self._credits
                         if 'artist' in d]

    def as_config(self):
        d = self._in_dict
        composer = self.composer
        return strip_nones({
            'album': d.get('title'),
            'albumartist': composer.get('name'),
            'albumartistsort': composer.get('sort-name'),
            'composer': composer.get('name'),
            'conductor': self.conductor.get('name'),
            'title': d.get('title'),
            'originaldate': self.date,
            'originalyear': self.year,
        })

    @property
    def date(self):
        d = self._in_dict.get('date')
        if d in (None, ''):
            return d
        return DTM.strptime(d, '%Y-%m-%d').date()

    @property
    def year(self):
        d = self.date
        if d is None:
            return None
        return d.year

    def get_artists(self, **kwargs):
        return [a for a in self._artists
                if all((k in a and a[k] == v) for k, v in kwargs.items())]

    @property
    def persons(self):
        return self.get_artists(type='Person')

    @property
    def composers(self):
        return [p for p in self.persons
                if 'composer' in p['disambiguation'].lower()]

    def _single(self, seq, default=None):
        if len(seq) == 0:
            return default
        assert len(seq) == 1
        return seq[0]

    @property
    def composer(self):
        return self._single(self.composers, {})

    @property
    def conductors(self):
        return [p for p in self.persons
                if 'conductor' in p['disambiguation'].lower()]

    @property
    def conductor(self):
        return self._single(self.conductors, {})

    @property
    def orchestras(self):
        return self.get_artists(type='Orchestra')

    @property
    def orchestra(self):
        return self._single(self.orchestras, {})

    @property
    def choirs(self):
        return self.get_artists(type='Choir')

    @property
    def choir(self):
        return self._single(self.choirs, {})


def get_mb_release(mb_release_id):
    # https://musicbrainz.org/doc/MusicBrainz_API
    response = requests.get(MBZ_URL_FMT.format(release_id=mb_release_id))
    return json.loads(response.text)


def get_parser():
    parser = ArgumentParser(description=__doc__,  # Usage from docstring
                            formatter_class=RawDescriptionHelpFormatter)
    parser.add_argument('action',
                        help='one of "default-config", "mb-config", "build"')
    parser.add_argument('first_arg', nargs='?',
                        help='Argument, meaning depends on "action"')
    parser.add_argument('second_arg', nargs='?',
                        help='Argument, meaning depends on "action"')
    parser.add_argument('--config-path',
                        default=op.join(os.getcwd(), CONFIG_BASENAME),
                        help='Path to config file')
    return parser


def main():
    parser = get_parser()
    args = parser.parse_args()
    config = read_config(args.config_path)
    settings, tracks = proc_config(
        config,
        op.dirname(args.config_path))
    if args.action == 'default-config':
        if args.first_arg is None:
            raise RuntimeError('Need track filename')
        config[args.first_arg] = DEFAULT_TRACK_CONFIG
        write_config(config, args.config_path)
        return 0
    if args.action == 'mb-config':
        if args.first_arg is None:
            raise RuntimeError('Need track filename')
        if args.second_arg is None:
            raise RuntimeError('Need release id')
        info = get_mb_release(args.second_arg)
        mbi = MBInfo(info)
        config[args.first_arg].update(mbi.as_config())
        write_config(config, args.config_path)
        return 0
    if args.action == 'build':
        pass
        return 0
    else:
        raise RuntimeError(
            'Expecting one of'
            'one of "default-config", "mb-config", "build"')


if __name__ == '__main__':
    main()
