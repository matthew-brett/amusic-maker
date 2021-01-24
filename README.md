# Processing utilities for vinyl recordings

These are utilities for converting and arranging wav files, from vinyl
recordings, into a structure suitable for an Android music application.

## Steps for one album

*   Convert album wav files to 320kbs, store in 'source' folder.  This will give
    one mp3 file per vinyl side.

    ```
    convert_wav ../foo_1.wav --out-name composer_work_1.mp3
    convert_wav ../foo_1.wav --out-name composer_work_1.mp3
    ```

*   Add album details to config file:

    ```
    default_entry source/composer_work_1.mp3
    default_entry source/composer_work_1.mp3
    ```

    Then edit `music_files.yaml`.

    or lookup the album in MusicBrainz, find the release ID from the URL (e.g.
    <https://musicbrainz.org/release/77441f5e-fb98-42e6-b73d-ed7e8507f855/details>) then:

    ```
    fill_entry source/composer_work_1.mp3 77441f5e-fb98-42e6-b73d-ed7e8507f855
    fill_entry source/composer_work_2.mp3 77441f5e-fb98-42e6-b73d-ed7e8507f855
    ```

    May still need edits of course.

*   Check jpg for album and add to `music_files.yaml`.
