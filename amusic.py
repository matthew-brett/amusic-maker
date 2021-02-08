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
from subprocess import check_call, check_output
from fnmatch import fnmatch
from argparse import ArgumentParser, RawDescriptionHelpFormatter

import requests
import yaml
from PIL import Image
from nameparser import HumanName


CONFIG_BASENAME = 'amusic_config.yml'
PARAMS_EXT = '.json'
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


def params_fname_for(fname):
    return fname + PARAMS_EXT


def clear_params(path):
    for dirpath, dirnames, filenames in os.walk(path):
        for fn in filenames:
            if op.splitext(fn)[1] == PARAMS_EXT:
                os.unlink(op.join(dirpath, fn))


def stored_params_for(fname, tdelta=-1):
    params_fname = params_fname_for(fname)
    if not op.isfile(params_fname):
        return None
    earliest_params_time = op.getmtime(fname) + tdelta
    if op.getmtime(params_fname) < earliest_params_time:
        return None
    with open(params_fname, 'rt') as fobj:
        return json.loads(fobj.read())


def _obj2jobj(obj):
    return obj.strftime(DATE_FMT)


def write_hash_for_fname(in_fname):
    md5sum = check_output(['md5', '-q', in_fname],
                          text=True)
    params = {'md5': md5sum}
    write_params_for(params, in_fname)
    return params


def dict2json(d):
    return json.dumps(d, default=_obj2jobj,
                      sort_keys=True)


def write_params_for(params, out_fname, tdelta=1):
    params_fname = params_fname_for(out_fname)
    with open(params_fname, 'wt') as fobj:
        fobj.write(dict2json(params))
    # Make sure params modification time later than original
    mtime = op.getmtime(out_fname) + tdelta
    os.utime(params_fname, (mtime, mtime))


def convert_file(in_fname, out_fname, sox_params):
    if (in_params := stored_params_for(in_fname)) == None:
        in_params = write_hash_for_fname(in_fname)
    params = dict(in_params=in_params, sox_params=sox_params)
    if stored_params_for(out_fname) == params:
        return params
    extra_params = [str(p) for p in sox_params]
    check_call(['sox', in_fname] + extra_params + [out_fname])
    write_params_for(params, out_fname)
    return params


def write_converted_file(in_fname,
                         full_out_fname,
                         settings,
                         force=False):
    froot, ext = op.splitext(in_fname)
    ensure_dir(settings['conv_path'])
    conv_fname = op.join(settings['conv_path'],
                         op.basename(froot) + settings['conv_ext'])
    out_params = convert_file(in_fname, conv_fname, settings['sox_params'])
    shutil.copyfile(conv_fname, full_out_fname)
    return out_params


def same_params_for(exp_params, out_fname):
    if exp_params is None:
        return False
    # JSON roundtrip for input parameters
    d2j2d = json.loads(dict2json(exp_params))
    if (out_params:= stored_params_for(out_fname)) is None:
        return False
    return out_params == d2j2d


def write_song(music_fname,
               img_fname,
               full_out_fname,
               entry,
               settings,
               force=False):
    exp_params = dict(
        music_params=stored_params_for(music_fname),
        img_params=stored_params_for(img_fname),
        entry=entry)
    if same_params_for(exp_params, full_out_fname):
        return
    if op.exists(full_out_fname) and not force:
        raise RuntimeError(f'File {full_out_fname} exists')
    write_converted_file(music_fname, full_out_fname, settings,
                         force=force)
    exp_params['music_params'] = stored_params_for(music_fname)
    # Add tags and image
    exp_params['img_params'], img_data = write_proc_image(
        img_fname,
        settings['min_img_size'],
        settings['out_dim'],
    )
    write_tags(full_out_fname, entry, img_data)
    write_params_for(exp_params, full_out_fname)


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
        if not key in etags.valid_keys:
            continue
        if not isinstance(value, list):
            value = [str(value)]
        etags[key.upper()] = value
    # Give more space to the title, which can be long.
    if not 'details' in entry:
        etags['details'] = entry['title']
    etags.save(full_out_fname)


def write_proc_image(img_fname, min_img_size=(640, 480),
                     out_dim=1024):
    if (img_params := stored_params_for(img_fname)) == None:
        img_params = write_hash_for_fname(img_fname)
    img = Image.open(img_fname)
    if img.size < tuple(min_img_size):
        raise ValueError(f'Low resolution image {img_fname}')
    img = resize_img(img, out_dim)
    fobj = BytesIO()
    img.save(fobj, format="jpeg")
    return img_params, fobj.getvalue()


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


def write_config(settings, tracks, config_fname):
    config = {'settings': settings}
    config.update(tracks)
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
        composer = composers[0] if len(composers) else {}
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
        parts = [int(v) for v in d.split('-')]
        if len(parts) < 2:
            return None
        elif len(parts) == 2:
            parts.append(1)
        y, m, d = parts
        return Date(y, m, 1 if d == 0 else d)

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
        self._artists = self._in_dict.get('extraartists', [])
        if (TL := self._in_dict.get('tracklist')):
            self._artists += sum([t.get('extraartists', []) for t in TL], [])
        # Add sort versions
        for a in self._artists:
            a['sort-name'] = get_sort_name(a.get('name'))

    @property
    def persons(self):
        return [a for a in self._artists if self._ok_role(a.get('role'))]

    def _ok_role(self, role):
        lrole = role.lower()
        if 'design' in lrole:
            return False
        if 'producer' in lrole:
            return False
        if 'engineer' in lrole:
            return False
        if 'notes' in lrole:
            return False
        return True

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
        styles = self._in_dict.get('styles', [])
        return None if len(styles) == 0 else styles[-1]

    def _tracks_with_suffix(self, tracklist, suffix=''):
        track_names = []
        for t in tracklist:
            if t['type_'] == 'heading':
                suffix = t['title'] + ' - '
            elif t['type_'] == 'index':
                track_names += self._tracks_with_suffix(
                    t['sub_tracks'],
                    t['title'] + ' - ')
            elif t['type_'] == 'track':
                track_names.append(f"{t['position']}: {suffix}{t['title']}")
        return track_names

    @property
    def details(self):
        return '\n'.join(self._tracks_with_suffix(self._in_dict['tracklist']))


def fill_tracks(wrapper,
                tracks,
                track_spec,
                release_spec=None,
                force=False,
               ):
    new_tracks = deepcopy(tracks)
    fill_obj = (None if release_spec is None
                else wrapper.from_release(release_spec))
    rel_id_key = wrapper.release_id_key
    done_key = wrapper.filled_flag_key
    for key, track_info in new_tracks.items():
        if not fnmatch(key, track_spec):
            continue
        if not force and track_info.get(done_key):
            continue
        if release_spec is None:
            if not (rel_id := track_info.get(rel_id_key)):
                continue
            fill_obj = wrapper.from_release(rel_id)
        else:
            rel_id = release_spec
        print(f'Filling {key} from {rel_id}')
        new_info = fill_obj.as_config()
        new_info[rel_id_key] = rel_id
        new_info[done_key] = True
        new_tracks[key].update(new_info)
    return new_tracks


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
        write_config(settings, tracks, args.config_path)
        return 0
    if args.action in ('mb-config', 'do-config'):
        if args.first_arg is None:
            raise RuntimeError('Need track spec')
        wrapper = DOInfo if args.action == 'do-config' else MBInfo
        tracks = fill_tracks(wrapper,
                             tracks,
                             args.first_arg,
                             args.second_arg,
                             force=args.force)
        write_config(settings, tracks, args.config_path)
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
