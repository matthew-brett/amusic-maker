import shutil

from io import BytesIO

from mutagen.mp3 import MP3
from mutagen.id3 import ID3, APIC, error
from mutagen.easyid3 import EasyID3

MP3_FNAME = 'mp3s_tmp/aclip.mp3'
IMG_FNAME = 'images/brown_team.jpg'
OUT_FNAME = 'foo.mp3'

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
etags['genre'] = 'my genre'
etags['performer'] = ['foo', 'bar', 'baz']
# audio.save()

shutil.copyfile(MP3_FNAME, OUT_FNAME)
etags.save(OUT_FNAME)
tags_in = ID3(OUT_FNAME)
print(tags_in)
