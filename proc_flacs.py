""" Process flacs """

import os
import os.path as op
import shutil

import yaml
from PIL import Image

import taglib


with open('flac_config.yml', 'rt') as fobj:
    config = yaml.load(fobj)


def_config = {
    'media': 'Vinyl',
    'source': 'Vinyl (Lossless)',
    'releasestatus': 'official',
    'releasetype': 'album',
    'script': 'Latn'
}


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
    full = def_config.copy()
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


def main():
    out_dir = op.join('..', 'music')
    waiting = True
    for key, entry in config.items():
        if waiting:
            if key == 'lvbmissa1-cr.flac':
                waiting = False
            else:
                continue
        proc_config_entry(key, entry, out_dir)
