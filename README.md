# Notice

After Apple's discontinuation of iPhoto in favor of the new Photos app, I have made a fork of phoshare and adapted it so it can work with Photos.

# Overview

`phoshare` allows you to export and synchronize your Photos library to a folder tree. It preserves both the original and modified image, your folder and album organization, and applies your Photos titles, descriptions, keywords, face tags, face rectangles, places, and ratings to the IPTC/EXIF metadata of your images. You can export a full copy of your library, or just build a tree of linked images that require very little additional disk space. You can re-run `phoshare` at any time to synchronize any changes made in Photos to your export tree quickly.

[Dan Warne](http://danwarne.com/) has written a blog post on [how to back up your iPhoto library to Dropbox](http://danwarne.com/backup-iphoto-library-dropbox-resize-images-save-space-2/) with `phoshare`.

`phoshare` is written in Python, and is easily customizable by just editing the Python scripts.

This fork is intended to revive `phoshare` as the original author [discontinued development](https://groups.google.com/forum/?fromgroups=#!topic/phoshare-users/moWsMcD5SdQ) in late 2012. It's meant for use with the latest version of Photos (1.0.1 as of this writing). For any version of iPhoto or Aperture, please use an earlier version from the original [project](https://code.google.com/p/phoshare/downloads/list).

# TO-DO

The adaptation to Photos library is still in progress, although the main features already work. Please take into account there is no documentation available about the Photos library structure, all of it has been figured out by reverse-engineering.

There still some disabled features and possible issues:

- [ ] Make script to generate an OS X app
- [ ] Take into account other album types, like smart or iCloud albums.
- [ ] Export also the images hanging from the root album.
- [ ] Enable metadata export.
- [ ] Enable face albums export, in case these stil exist.
- [ ] Fix Python PEP8 and Code Inspections.
- [ ] Clean-up entirely the code once the old features are all restored or completely discarded.
- [ ] Fix issue if the Photos library path contains non-Ascii characters.
- [ ] Fix issue if the export path contains non-Ascii characters.
- [ ] Fix issue if any export filter contains non-Ascii characters.
- [ ] When exporting try to keep in the filesystem to file dates equal to the image date.
- [ ] Test what happens when importing to Photos an old image without metadata, and thus with no image date.
- [ ] Test the current behaviour when exporting metadata (when enabled) if the export file is a hard link.

# Documentation

For now, use the original [Documentation](https://sites.google.com/site/phosharedoc) link for "How To" information, and the [user group](http://groups.google.com/group/phoshare-users) for additional information. I will update the documentation for the fork as time permits.

# License

Original work Copyright 2010 Google Inc.
Modified work Copyright 2014 Luke Hagan
Modified work Copyright 2017 Benjamín Valero

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
