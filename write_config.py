""" Write configuration for FLAC move
"""

from glob import glob

with open('flac_template.txt', 'rt') as fobj:
    TPL_TXT = fobj.read()

out_parts = []

for fname in sorted(glob('*.flac')):
    print(fname)
    out_parts.append(TPL_TXT.format(fname=fname))


with open('flac_config.yml', 'wt') as fobj:
    fobj.write('\n\n'.join(out_parts))
