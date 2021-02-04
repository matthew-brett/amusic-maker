#!/usr/bin/env python
""" Process WAV files into Android music folder
"""

import os
import os.path as op
import re
from io import BytesIO
import shutil
from datetime import date as Date
from copy import deepcopy
import json
from hashlib import md5
from subprocess import check_call, check_output
from fnmatch import fnmatch
from argparse import ArgumentParser, RawDescriptionHelpFormatter

import requests
import yaml
from PIL import Image
from nameparser import HumanName


CONFIG_BASENAME = 'amusic_config.yml'
HASH_EXT = '.md5'
FBASE2FOLDER = re.compile(r'([A-Za-z_]+)[\d]')
DATE_FMT = '%Y-%m-%d'


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
    'tracknumber': 1,
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
    if 'min_img_size' not in settings:
        settings['min_img_size'] = (640, 480)
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
            fname = f'{fname}_disc{disc_no}'
        full['totaldiscs'] = disc_total
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
    return json.dumps(d, default=_obj2jobj,
                      sort_keys=True)


def str2hash(s):
    return md5(s.encode('latin1')).hexdigest()


def dict2hash(d):
    return str2hash(dict2json(d))


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
    extra_params = [str(p) for p in sox_params]
    check_call(['sox', in_fname] + extra_params + [out_fname])
    write_hash_for(out_hash, out_fname)
    return out_hash


def write_converted_file(in_fname,
                         full_out_fname,
                         settings,
                         force=False):
    froot, ext = op.splitext(in_fname)
    ensure_dir(settings['conv_path'])
    conv_fname = op.join(settings['conv_path'],
                         op.basename(froot) + settings['conv_ext'])
    out_hash = convert_file(in_fname, conv_fname, settings['sox_params'])
    shutil.copyfile(conv_fname, full_out_fname)
    return out_hash


def same_hash_for(exp_hash, out_fname):
    if exp_hash is None:
        return False
    if (out_hash:= stored_hash_for(out_fname)) is None:
        return False
    return out_hash == exp_hash


def write_song(music_fname,
               img_fname,
               full_out_fname,
               entry,
               settings,
               force=False):
    exp_params = dict(
        music_hash=stored_hash_for(music_fname),
        img_hash=stored_hash_for(img_fname),
        entry=entry)
    if same_hash_for(dict2hash(exp_params), full_out_fname):
        return
    if op.exists(full_out_fname) and not force:
        raise RuntimeError(f'File {full_out_fname} exists')
    write_converted_file(music_fname, full_out_fname, settings,
                         force=force)
    exp_params['music_hash'] = stored_hash_for(music_fname)
    # Add tags and image
    exp_params['img_hash'], img_data = write_proc_image(
        img_fname,
        settings['min_img_size'],
        settings['out_dim'],
    )
    write_tags(full_out_fname, entry, img_data)
    write_hash_for(dict2hash(exp_params), full_out_fname)


def get_tag_maker():

    from mutagen.id3 import APIC, USLT, Encoding, PictureType
    from mutagen.easyid3 import EasyID3

    # Extra ID3 keys
    # https://en.wikipedia.org/wiki/ID3#ID3v2_frame_specification
    EasyID3.RegisterTextKey('originalyear', 'TORY')
    EasyID3.RegisterTextKey('style', 'TIT1')
    # period becomes synonym for genre
    EasyID3.RegisterTextKey('period', 'TCON')
    # Details go into the lyrics field.
    LYRICS_KEY = "USLT::'eng'"

    def set_lyrics(tags, key, text):
        tags[LYRICS_KEY] = USLT(encoding=Encoding.UTF8, lang='eng', desc='desc',
                                text='\n'.join(text))

    EasyID3.RegisterKey('details', lambda t, k : t[LYRICS_KEY], set_lyrics)

    # Set picture
    def set_picture(tags, key, img_data):
        apic_type = getattr(PictureType, key.upper())
        tags.add(
            APIC(
                encoding=Encoding.UTF8,
                mime='image/jpeg', # image/jpeg or image/png
                type=apic_type,
                desc=key,
                data=img_data,
            )
        )

    EasyID3.RegisterKey('cover_front', setter=set_picture)

    return EasyID3


def write_tags(full_out_fname, entry, img_data):
    etags = get_tag_maker()()
    etags['cover_front'] = img_data
    for key, value in entry.items():
        if not isinstance(value, list):
            value = [str(value)]
        etags[key.upper()] = value
    # Give more space to the title, which can be long.
    if not 'details' in entry:
        etags['details'] = entry['title']
    etags.save(full_out_fname)


def write_proc_image(img_fname, min_img_size=(640, 480),
                     out_dim=1024):
    if (img_hash := stored_hash_for(img_fname)) == None:
        img_hash = write_hash_for_fname(img_fname)
    img = Image.open(img_fname)
    if img.size < tuple(min_img_size):
        raise ValueError(f'Low resolution image {img_fname}')
    img = resize_img(img, out_dim)
    fobj = BytesIO()
    img.save(fobj, format="jpeg")
    return img_hash, fobj.getvalue()


def guess_folder(fbase):
    if (match := FBASE2FOLDER.match(fbase)) is None:
        return None
    return match.groups()[0].strip('_')


def ensure_dir(path):
    if not op.isdir(path):
        os.makedirs(path)


def build_one(fbase, config, settings, force=False):
    music_fname = find_file(fbase, settings['wav_paths'])
    entry = config.copy()
    # Remove folder and image entries.
    folder_name = entry.pop('folder_name')
    in_img_fname = entry.pop('img_fname')
    img_fname = find_file(in_img_fname,
                          settings['img_paths'])
    if folder_name is None:
        folder_name = guess_folder(fbase)
    full_out_dir = op.join(settings['out_path'], folder_name)
    ensure_dir(full_out_dir)
    out_fbase = out_fbaseroot_for(folder_name, entry)
    full_out_fname = op.join(full_out_dir,
                             out_fbase + settings['conv_ext'])
    write_song(music_fname,
               img_fname,
               full_out_fname, entry,
               settings, force=force)


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


# Dictionary to fix any incorrect sortnames below.
SORT_NAMES = {}


def pn2last_prefixes(pn):
    lasts = []
    prefixes = []
    for p in pn.last.split():
        if pn.is_prefix(p):
            prefixes.append(p)
        else:
            lasts.append(p)
    return ' '.join(lasts), prefixes


def get_sort_name(name):
    if name is None:
        return None
    pn = HumanName(name)
    last, prefixes = pn2last_prefixes(pn)
    if (key := last.lower()) in SORT_NAMES:
        return SORT_NAMES[key]
    return last + ', ' + ' '.join(pn.first_list + pn.middle_list + prefixes)


class MBInfo:

    role_key = 'type'
    role_sub_key = 'disambiguation'
    date_key = 'date'
    composer_str = 'composer'
    release_id_key = 'musicbrainz_release'
    filled_flag_key = 'musicbrainz_filled'
    url_fmt = (
        'https://musicbrainz.org/ws/2/release/'
        '{release_id}?inc='
        # 'genres+'
        'artist-credits+labels+discids'
        # '+work-rels+work-level-rels'
        '&fmt=json'
    )
    url_get_kwargs = {}

    @classmethod
    def from_release(cls, release_id):
        # https://musicbrainz.org/doc/MusicBrainz_API
        url = cls.url_fmt.format(release_id=release_id)
        response = requests.get(url, **cls.url_get_kwargs)
        return cls(json.loads(response.text))

    def __init__(self, in_dict):
        self._in_dict = in_dict
        self._credits = self._in_dict.get(
            'artist-credit', [])
        self._artists = [d['artist'] for d in self._credits
                         if 'artist' in d]

    def _get_value(self, key):
        res = self._in_dict.get(key)
        if res is not None:
            res = res.strip()
        return res

    def as_config(self):
        composers = self.composers
        composer = composers[0]
        composer_name = composer.get('name')
        return strip_nones({
            'album': self._get_value('title'),
            'artist': composer_name,
            'artistsort': composer.get('sort-name'),
            'albumartist': composer_name,
            'albumartistsort': composer.get('sort-name'),
            'composer': [c.get('name') for c in composers],
            'conductor': self.conductor.get('name'),
            'orchestra': self.orchestra.get('name'),
            'performer': [p['name'] for p in self.performers],
            'title': self._get_value('title'),
            'originaldate': self.date,
            'originalyear': self.year,
            'period': self.period,
            'details': self.details,
        })

    @property
    def date(self):
        d = self._in_dict.get(self.date_key)
        if d in (None, ''):
            return d
        y, m, d = [int(v) for v in d.split('-')]
        d = 1 if d == 0 else d
        return Date(y, m, d)

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
        return self.get_artists(**{self.role_key: 'Person'})

    @property
    def composers(self):
        return [p for p in self.persons
                if self.composer_str in p[self.role_sub_key].lower()]

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
                if 'conductor' in p[self.role_sub_key].lower()]

    @property
    def conductor(self):
        return self._single(self.conductors, {})

    @property
    def orchestras(self):
        return self.get_artists(**{self.role_key: 'Orchestra'})

    @property
    def orchestra(self):
        return self._single(self.orchestras, {})

    @property
    def choirs(self):
        c0 = self.get_artists(**{self.role_key: 'Choir'})
        c1 = self.get_artists(**{self.role_key: 'Chorus'})
        return c0 + c1

    @property
    def choir(self):
        return self._single(self.choirs, {})

    @property
    def performers(self):
        not_performers = (self.composers + self.conductors + self.choirs +
                          self.orchestras)
        performers = [p for p in self.persons if p not in not_performers]
        return performers + self.choirs + self.orchestras

    @property
    def period(self):
        return None

    @property
    def details(self):
        return None


class DOInfo(MBInfo):

    role_key = 'role'
    role_sub_key = 'role'
    date_key = 'released'
    composer_str = 'composed by'
    release_id_key = 'discogs_release'
    filled_flag_key = 'discogs_filled'
    url_fmt = "https://api.discogs.com/releases/{release_id}"
    url_get_kwargs = {'headers': {'User-Agent': "FooBarApp/3.0"}}

    def __init__(self, in_dict):
        self._in_dict = in_dict
        self._artists = self._in_dict.get(
            'extraartists', [])
        # Add sort versions
        for a in self._artists:
            a['sort-name'] = get_sort_name(a.get('name'))

    @property
    def persons(self):
        return self._artists

    @property
    def year(self):
        res = self._in_dict.get('year')
        if res not in (None, 0):
            return str(res)
        d = self.date
        if d is None:
            return None
        return d.year

    @property
    def period(self):
        return self._in_dict.get('styles', [])[-1]

    @property
    def details(self):
        details = []
        suffix = ''
        for t in self._in_dict['tracklist']:
            if t['type_'] == 'heading':
                suffix = t['title'] + ' - '
            elif t['type_'] == 'track':
                details.append(f"{t['position']}: {suffix}{t['title']}")
        return '\n'.join(details)


def fill_config(wrapper,
                config,
                track_spec,
                release_spec=None):
    new_config = deepcopy(config)
    fill_obj = (None if release_spec is None
                else wrapper.from_release(release_spec))
    rel_id_key = wrapper.release_id_key
    done_key = wrapper.filled_flag_key
    for key, track_info in new_config.items():
        if not fnmatch(key, track_spec):
            continue
        if track_info.get(done_key):
            continue
        if release_spec is None:
            if not (rel_id := track_info.get(rel_id_key)):
                continue
            fill_obj = wrapper.from_release(rel_id)
        else:
            rel_id = release_spec
        new_info = fill_obj.as_config()
        new_info[rel_id_key] = rel_id
        new_info[done_key] = True
        new_config[key].update(new_info)
    return new_config


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
    parser.add_argument('--force', action='store_true',
                        help='Whether to overwrite existing files/parameters')
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
    if args.action in ('mb-config', 'do-config'):
        if args.first_arg is None:
            raise RuntimeError('Need track spec')
        wrapper = DOInfo if args.action == 'do-config' else MBInfo
        config = fill_config(wrapper,
                             config,
                             args.first_arg,
                             args.second_arg,
                             force=args.force)
        write_config(config, args.config_path)
        return 0
    if args.action == 'build':
        for track, config in tracks.items():
            print('Building', track)
            build_one(track, config, settings, args.force)
        return 0
    else:
        raise RuntimeError(
            'Expecting one of'
            '"default-config", "mb-config", "do-config", "build"')


if __name__ == '__main__':
    main()
