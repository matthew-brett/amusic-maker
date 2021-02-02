import os.path as op
import shutil

from io import BytesIO

from mutagen.id3 import ID3, APIC, USLT
from mutagen.easyid3 import EasyID3

# Discard disctotal quietly
EasyID3.RegisterTextKey('period', 'TCON')
EasyID3.RegisterKey('disctotal', setter=lambda s, k, v: None)
# Details go into the lyrics field.

def get_lyrics(tags, key):
    return tags["USLT::'eng'"]

def set_lyrics(tags, key, text):
    tags["USLT::'eng'"] = USLT(encoding=3, lang='eng', desc='desc',
                               text='\n'.join(text))

EasyID3.RegisterKey('details', get_lyrics, set_lyrics)


HERE = op.dirname(__file__)
MP3_FNAME = 'mp3s_tmp/aclip.mp3'
IMG_FNAME = op.join(HERE, '..', 'images', 'brown_team.jpg')

tags = ID3()
tags.add(
    APIC(
        encoding=3, # 3 is for utf-8
        mime='image/jpeg', # image/jpeg or image/png
        type=3, # 3 is for the cover image
        desc=u'Cover',
        data=open(IMG_FNAME, 'rb').read()
    )
)
mem_tags = BytesIO()
tags.save(mem_tags)
mem_tags.seek(0)
etags = EasyID3(mem_tags)
etags['artist'] = 'Beyonce'
etags['title'] = 'my title'
etags['period'] = 'my genre'
etags['performer'] = ['foo', 'bar', 'baz']
etags['disctotal'] = '3'
etags['details'] = 'foo bar'

etags.save(mem_tags)
mem_tags.seek(0)

all_tags = ID3(mem_tags)

print(all_tags)
