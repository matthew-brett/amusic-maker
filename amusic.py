""" Process flacs """

import os
import os.path as op
import shutil
import datetime
from copy import deepcopy
from argparse import ArgumentParser, RawDescriptionHelpFormatter

import yaml
from PIL import Image

import taglib

HERE = op.dirname(__file__)
CONFIG_FNAME = op.join(HERE, 'amusic_config.yml')


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
    'originaldate': datetime.date(1994, 4, 1),
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


def proc_config(config, config_fname):
    config_path = op.abspath(op.dirname(config_fname))
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


def proc_config_entry(in_fname, entry, out_dir):
    entry = entry.copy()
    folder_name = entry.pop('folder_name')
    full_out_dir = op.join(out_dir, folder_name)
    if not op.isdir(full_out_dir):
        os.makedirs(full_out_dir)
    fname = folder_name
    img_fname = entry.pop('img_fname')
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
    fname = f'{fname}_side{track_no:02d}.flac'
    full_out_fname = op.join(full_out_dir, fname)
    if op.exists(full_out_fname):
        raise RuntimeError(f'File {full_out_fname} exists')
    shutil.copy2(in_fname, full_out_fname)
    song = taglib.File(full_out_fname)
    # All the rest are tags
    for key, value in entry.items():
        if not isinstance(value, list):
            value = [str(value)]
        song.tags[key.upper()] = value
    song.save()
    out_img_fname = op.join(full_out_dir, 'Folder.jpg')
    if not op.exists(out_img_fname):
        img = Image.open(img_fname)
        img = resize_img(img, 1024)
        img.save(out_img_fname)


def write_config(config, config_fname=CONFIG_FNAME):
    with open(CONFIG_FNAME, 'wt') as fobj:
        yaml.dump(config, fobj,
                  indent=4,
                  allow_unicode=True,
                  encoding='utf-8',
                  sort_keys=False)


def get_parser():
    parser = ArgumentParser(description=__doc__,  # Usage from docstring
                            formatter_class=RawDescriptionHelpFormatter)
    parser.add_argument('action',
                        help='one of "default-config", "mb-config", "build"')
    parser.add_argument('first_arg', nargs='?',
                        help='Argument, meaning depends on "action"')
    return parser


def main():
    parser = get_parser()
    args = parser.parse_args()
    config = read_config(CONFIG_FNAME)
    settings, tracks = proc_config(config, CONFIG_FNAME)
    if args.action == 'default-config':
        if args.first_arg is None:
            raise RuntimeError('Need track filename')
        config[args.first_arg] = DEFAULT_TRACK_CONFIG
        write_config(config, CONFIG_FNAME)
        return 0
    else:
        raise RuntimeError(
            'Expecting one of'
            'one of "default-config", "mb-config", "build"')


if __name__ == '__main__':
    main()
