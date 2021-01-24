# Processing utilities for vinyl recordings

These are utilities for converting and arranging wav files, from vinyl
recordings, into a structure suitable for an Android music application.

## Steps for one album

*   Add album details to `amusic_files.yml` config file:

    ```
    default_entry wavs/composer_work_1.wav
    default_entry wavs/composer_work_1.wav
    ```

    Then edit `music_files.yaml`.

    or lookup the album in MusicBrainz, find the release ID from the URL (e.g.
    <https://musicbrainz.org/release/77441f5e-fb98-42e6-b73d-ed7e8507f855/details>) then:

    ```
    fill_entry wavs/composer_work_1.wav 77441f5e-fb98-42e6-b73d-ed7e8507f855
    fill_entry wavs/composer_work_2.wav 77441f5e-fb98-42e6-b73d-ed7e8507f855
    ```

    May still need edits of course.

*   Check jpg for album and add to `amusic_files.yml`.

*   Create directory, files, with

    ```
    build_amusic
    ```
