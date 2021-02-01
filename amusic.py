#!/usr/bin/env python
""" Process WAV files into Android music folder
"""

import os
import os.path as op
import re
import shutil
from datetime import date as Date, datetime as DTM
from copy import deepcopy
import json
from hashlib import md5
from subprocess import check_call, check_output
from argparse import ArgumentParser, RawDescriptionHelpFormatter

import requests
import yaml
from PIL import Image

import taglib

HERE = op.dirname(__file__)


CONFIG_BASENAME = 'amusic_config.yml'
HASH_EXT = '.md5'
FBASE2FOLDER = re.compile(r'([A-Za-z_]+)[\d]')
DATE_FMT = '%Y-%m-%d'


MBZ_URL_FMT = (
    'https://musicbrainz.org/ws/2/release/'
    '{release_id}?inc='
    # 'genres+'
    'artist-credits+labels+discids'
    # '+work-rels+work-level-rels'
    '&fmt=json'
)


DEF_TRACK_CONFIG = {
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


def out_fbaseroot_for(fname, entry):
    full = DEF_TRACK_CONFIG.copy()
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
    return f'{fname}_side{track_no:02d}'


def hash_fname_for(fname):
    return fname + HASH_EXT


def clear_hashes(path):
    for dirpath, dirnames, filenames in os.walk(path):
        for fn in filenames:
            if op.splitext(fn)[1] == HASH_EXT:
                os.unlink(op.join(dirpath, fn))


def stored_hash_for(fname, tdelta=0):
    hash_fname = hash_fname_for(fname)
    if not op.isfile(hash_fname):
        return None
    earliest_hash_time = op.getmtime(fname) + tdelta
    if op.getmtime(hash_fname) < earliest_hash_time:
        return None
    with open(hash_fname, 'rt') as fobj:
        return fobj.read().strip()


def _obj2jobj(obj):
    return obj.strftime(DATE_FMT)


def dict2json(d):
    return json.dumps(d, default=_obj2jobj)


def str2hash(s):
    return md5(s.encode('latin1')).hexdigest()


def dict2hash(d):
    return str2hash(dict2json(d))


def exp_hash_for(in_fname, entry):
    if (in_hash:= stored_hash_for(in_fname)) is None:
        return None
    exp_params = dict(in_hash=in_hash,
                      entry=entry)
    return dict2hash(exp_params)


def write_hash_for_fname(in_fname):
    md5sum = check_output(['md5', '-q', in_fname],
                          text=True)
    write_hash_for(md5sum, in_fname)
    return md5sum


def write_hash_for(hash_str, out_fname, tdelta=1):
    hash_fname = hash_fname_for(out_fname)
    with open(hash_fname, 'wt') as fobj:
        fobj.write(hash_str)
    # Make sure hash modification time later than original
    mtime = op.getmtime(out_fname) + tdelta
    os.utime(hash_fname, (mtime, mtime))


def convert_file(in_fname, out_fname, sox_params):
    if (in_hash := stored_hash_for(in_fname)) == None:
        in_hash = write_hash_for_fname(in_fname)
    params = dict(in_hash=in_hash, sox_params=sox_params)
    out_hash = dict2hash(params)
    if stored_hash_for(out_fname) == out_hash:
        return out_hash
    check_call(['sox', in_fname] + sox_params + [out_fname])
    write_hash_for(out_hash, out_fname)
    return out_hash


def write_converted_file(in_fname,
                         full_out_fname,
                         settings,
                         clobber=False):
    froot, ext = op.splitext(in_fname)
    ensure_dir(settings['conv_path'])
    conv_fname = op.join(settings['conv_path'],
                         op.basename(froot) + settings['conv_ext'])
    convert_file(in_fname, conv_fname, settings['sox_params'])
    shutil.copyfile(conv_fname, full_out_fname)


def same_hash_for(in_fname, out_fname, entry):
    if (exp_hash:= exp_hash_for(in_fname, entry)) is None:
        return False
    if (out_hash:= stored_hash_for(out_fname)) is None:
        return False
    return out_hash == exp_hash


def write_song(in_fname, full_out_fname, entry,
               settings, clobber=False):
    if same_hash_for(in_fname, full_out_fname, entry):
        return
    if op.exists(full_out_fname) and not clobber:
        raise RuntimeError(f'File {full_out_fname} exists')
    write_converted_file(in_fname, full_out_fname,
                         settings, clobber=clobber)
    song = taglib.File(full_out_fname)
    # All the rest are tags
    for key, value in entry.items():
        if not isinstance(value, list):
            value = [str(value)]
        song.tags[key.upper()] = value
    song.save()
    exp_hash = exp_hash_for(in_fname, entry)
    write_hash_for(exp_hash, full_out_fname)


def write_image(img_fname, full_out_dir,
                clobber=False,
                min_width=500,
                min_height=400):
    out_img_fname = op.join(full_out_dir, 'Folder.jpg')
    if (img_hash := stored_hash_for(img_fname)) == None:
        img_hash = write_hash_for_fname(img_fname)
    out_hash = stored_hash_for(out_img_fname)
    if img_hash == out_hash:
        return
    if op.exists(out_img_fname) and not clobber:
        raise RuntimeError(f'File {out_img_fname} exists')
    img = Image.open(img_fname)
    if img.width < min_width or img.height < min_height:
        raise ValueError(f'Low resolution image {img_fname}')
    img = resize_img(img, 1024)
    img.save(out_img_fname)
    write_hash_for(img_hash, out_img_fname)


def guess_folder(fbase):
    if (match := FBASE2FOLDER.match(fbase)) is None:
        return None
    return match.groups()[0].strip('_')


def ensure_dir(path):
    if not op.isdir(path):
        os.makedirs(path)


def build_one(fbase, config, settings, clobber=False):
    in_fname = find_file(fbase, settings['wav_paths'])
    entry = config.copy()
    # Remove folder and image entries.
    folder_name = entry.pop('folder_name')
    in_img_fname = entry.pop('img_fname')
    if folder_name is None:
        folder_name = guess_folder(fbase)
    full_out_dir = op.join(settings['out_path'], folder_name)
    ensure_dir(full_out_dir)
    out_fbase = out_fbaseroot_for(folder_name, entry)
    full_out_fname = op.join(full_out_dir,
                             out_fbase + settings['conv_ext'])
    write_song(in_fname, full_out_fname, entry,
               settings, clobber=clobber)
    if in_img_fname is None:
        print(f'No folder image specified for {fbase}')
        return
    img_fname = find_file(in_img_fname, settings['img_paths'])
    assert op.exists(img_fname)
    write_image(img_fname, full_out_dir, clobber)


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
        return DTM.strptime(d, DATE_FMT).date()

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
    parser.add_argument('--clobber', action='store_true',
                        help='Whether to overwrite existing files')
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
        for track, config in tracks.items():
            print('Building', track)
            build_one(track, config, settings, args.clobber)
        return 0
    else:
        raise RuntimeError(
            'Expecting one of'
            'one of "default-config", "mb-config", "build"')


if __name__ == '__main__':
    main()
