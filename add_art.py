from mutagen.mp3 import MP3
from mutagen.id3 import ID3, APIC, error

MP3_FNAME = 'beethoven_missa_solemnis_d1_side01.mp3'
IMG_FNAME = 'Folder.jpg'

audio = MP3(MP3_FNAME, ID3=ID3)
audio.tags.add(
    APIC(
        encoding=3, # 3 is for utf-8
        mime='image/jpeg', # image/jpeg or image/png
        type=3, # 3 is for the cover image
        desc=u'Cover',
        data=open(IMG_FNAME, 'rb').read()
    )
)
audio.save()
