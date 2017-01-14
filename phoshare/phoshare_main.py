#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Reads Photos library info, and exports photos and movies."""

# Original work Copyright 2010 Google Inc.
# Modified work Copyright 2014 Luke Hagan
# Modified work Copyright 2017 Benjamín Valero
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

# Modifications to original source:
#
#   2014-06-04: retrieve keywords from iPhoto database using sqlite
#   2017-01-14: retrieve all necessary data entirely from Photos SQLite database
#

import getpass
import logging
import os
import re
import sys
import time
import unicodedata

from optparse import OptionParser
import MacOS

import appledata.iphotodata as iphotodata
import tilutil.exiftool as exiftool
import tilutil.systemutils as su
import tilutil.imageutils as imageutils
import phoshare.phoshare_version

# Maximum diff in file size to be not considered a change (to allow for
# meta data updates for example)
_MAX_FILE_DIFF = 60000

# Fudge factor for file modification times
_MTIME_FUDGE = 3

'''
# List of extensions for image formats that support EXIF data. Sources:
# - iPhoto help topic: About digital cameras that support RAW files
# - Apple RAW Support listing: http://www.apple.com/aperture/specs/raw.html
# - ExifTool supported formats (R/W only): http://www.sno.phy.queensu.ca/~phil/exiftool/#supported
_EXIF_EXTENSIONS = ('3fr', 'arw', 'ciff', 'cr2', 'crw', 'dcr', 'erf', 'jpg', 'jpeg', 'k25', 'kdc',
                    'nef', 'nrw', 'orf', 'pef', 'png', 'raf', 'raw', 'rw2', 'rwl', 'sr2', 'srf',
                    'srw', 'tif', 'tiff')
'''

# create logger
_logger = logging.getLogger('google')
_logger.setLevel(logging.DEBUG)
  
'''
def region_matches(region1, region2):
    """Tests if two regions (rectangles) match."""
    if len(region1) != len(region2):
        return False
    for i in xrange(len(region1)):
        if abs(region1[i] - region2[i]) > 0.0000005:
            return False
    return True
'''

def delete_album_file(album_file, albumdirectory, msg, options):
    """sanity check - only delete from album directory."""
    if not album_file.startswith(albumdirectory):
        print >> sys.stderr, (
            "Internal error - attempting to delete file "
            "that is not in album directory:\n    %s") % (su.fsenc(album_file))
        return False
    if msg:
        print "%s: %s" % (msg, su.fsenc(album_file))

    if not imageutils.should_delete(options):
        return False
    if options.dryrun:
        return True

    try:
        if os.path.isdir(album_file):
            file_list = os.listdir(album_file)
            for subfile in file_list:
                delete_album_file(os.path.join(album_file, subfile),
                                  albumdirectory, msg, options)
            os.rmdir(album_file)
        else:
            os.remove(album_file)
        return True
    except OSError as ex:
        print >> sys.stderr, "Could not delete %s: %s" % (su.fsenc(album_file),
                                                          ex)
    return False


class ExportFile(object):
    """Describes an exported image."""

    def __init__(self, photo, container, export_directory, base_name, options):
        """Creates a new ExportFile object."""
        self.photo = photo
        '''
        self.container = container
        '''

        extension = su.getfileextension(photo.image_path)
        self.export_file = os.path.join(
            export_directory, base_name + '.' + extension)

        '''
        # Location of "Original" file, if any.
        originals_folder = u"Originals"
        if photo.originalpath:
            self.original_export_file = os.path.join(
                export_directory, originals_folder, base_name + "." +
                su.getfileextension(photo.originalpath))
        else:
            self.original_export_file = None
        '''

    '''
    def get_photo(self):
        """Gets the associated iPhotoImage."""
        return self.photo
    '''

    def _check_need_to_export(self, source_file, options):
        """Returns true if the image file needs to be exported.

        Args:
          source_file: path to image file, with aliases resolved.
          options: processing options.
        """
        if not os.path.exists(self.export_file):
            return True
        # In link mode, check the inode.
        if options.link:
            export_stat = os.stat(self.export_file)
            source_stat = os.stat(source_file)
            if export_stat.st_ino != source_stat.st_ino:
                su.pout('Changed:  %s: inodes don\'t match: %d vs. %d' %
                        (self.export_file, export_stat.st_ino, source_stat.st_ino))
                return True
        if os.path.getmtime(self.export_file) + _MTIME_FUDGE < os.path.getmtime(source_file):
            su.pout('Changed:  %s: newer version is available: %s vs. %s' %
                    (self.export_file,
                     time.ctime(os.path.getmtime(self.export_file)),
                     time.ctime(os.path.getmtime(source_file))))
            return True

        # With creative renaming in Photos it is possible to get
        # stale files if titles get swapped between images. Double
        # check the size, allowing for some difference for meta data
        # changes made in the exported copy
        source_size = os.path.getsize(source_file)
        export_size = os.path.getsize(self.export_file)
        diff = abs(source_size - export_size)
        if diff > _MAX_FILE_DIFF or (diff > 32 and options.link):
            su.pout('Changed:  %s: file size: %d vs. %d' %
                    (self.export_file, export_size, source_size))
            return True

        return False

    '''
    def _generate_original(self, options):
        """Exports the original file."""
        do_original_export = False
        export_dir = os.path.split(self.original_export_file)[0]
        if not os.path.exists(export_dir):
            su.pout("Creating folder " + export_dir)
            if not options.dryrun:
                os.mkdir(export_dir)
        original_source_file = su.resolve_alias(self.photo.originalpath)
        if os.path.exists(self.original_export_file):
            # In link mode, check the inode.
            if options.link:
                export_stat = os.stat(self.original_export_file)
                source_stat = os.stat(original_source_file)
                if export_stat.st_ino != source_stat.st_ino:
                    su.pout('Changed:  %s: inodes don\'t match: %d vs. %d' %
                            (self.original_export_file, export_stat.st_ino, source_stat.st_ino))
                    do_original_export = True
            if (os.path.getmtime(self.original_export_file) + _MTIME_FUDGE <
                os.path.getmtime(original_source_file)):
                su.pout('Changed:  %s: newer version is available: %s vs. %s' %
                        (self.original_export_file,
                         time.ctime(os.path.getmtime(
                             self.original_export_file)),
                         time.ctime(os.path.getmtime(original_source_file))))
                do_original_export = True
        else:
            do_original_export = True

        do_iptc = (options.iptc == 1 and
                   do_original_export) or options.iptc == 2
        if do_iptc and options.link:
            if self.check_iptc_data(original_source_file, options,
                                    is_original=True, file_updated=do_original_export):
                do_original_export = True
        exists = True  # True if the file exists or was updated.
        if do_original_export:
            exists = imageutils.copy_or_link_file(original_source_file,
                                                  self.original_export_file,
                                                  options.dryrun,
                                                  options.link,
                                                  options)
        else:
            _logger.debug(u'%s up to date.', self.original_export_file)
        if exists and do_iptc and not options.link:
            self.check_iptc_data(self.original_export_file, options,
                                 is_original=True, file_updated=do_original_export)
    '''

    def generate(self, options):
        """makes sure all files exist in other album, and generates if
           necessary."""
        try:
            source_file = su.resolve_alias(self.photo.image_path)
            do_export = self._check_need_to_export(source_file, options)
            '''
            # if we use links, we update the IPTC data in the original file
            do_iptc = (options.iptc == 1 and do_export) or options.iptc == 2
            if do_iptc and options.link:
                if self.check_iptc_data(source_file, options, file_updated=do_export):
                    do_export = True
            '''
            exists = True  # True if the file exists or was updated.
            if do_export:
                exists = imageutils.copy_or_link_file(source_file,
                                                      self.export_file,
                                                      options.dryrun,
                                                      options.link,
                                                      options)
            else:
                _logger.debug(u'%s up to date.', self.export_file)

            '''
            # if we copy, we update the IPTC data in the copied file
            if exists and do_iptc and not options.link:
                self.check_iptc_data(self.export_file, options, file_updated=do_export)

            if (options.originals and self.photo.originalpath and
                not self.photo.rotation_is_only_edit):
                self._generate_original(options)
            '''
        except (OSError, MacOS.Error) as ose:
            su.perr(u"Failed to export %s to %s: %s" % (self.photo.image_path, self.export_file,
                                                        ose))

    '''
    def get_export_keywords(self, do_face_keywords):
        """Returns the list of keywords that should be in the exported image."""
        new_keywords = []
        if self.photo.keywords:
            for keyword in self.photo.keywords:
                if keyword and not keyword in new_keywords:
                    new_keywords.append(keyword)
        if do_face_keywords:
            for keyword in self.photo.getfaces():
                if keyword and not keyword in new_keywords:
                    new_keywords.append(keyword)
        return new_keywords

    def _check_person_iptc_data(self, export_file,
                                region_rectangles, region_names, do_faces, messages):
        """Tests if the person names or regions in the export file need to be
           updated.

        Returns: (new_rectangles, new_persons), or (None, None)
        """
        if do_faces:
            photo_rectangles = self.photo.face_rectangles
            photo_faces = self.photo.faces
        else:
            photo_rectangles = []
            photo_faces = []
        combined_region_names = ','.join(region_names)
        combined_photo_faces = ','.join(photo_faces)
        if combined_region_names != combined_photo_faces:
            messages.append(u'  Persons (%s instead of %s)'
                    % (combined_region_names, combined_photo_faces))
            return (photo_rectangles, photo_faces)

        if len(region_rectangles) != len(photo_rectangles):
            messages.append(u'  Number of regions (%d vs %d)' %
                    (len(region_rectangles), len(photo_rectangles)))
            #su.pout('%s vs %s' % (combined_region_names, combined_photo_faces))
            #su.pout('%s vs %s' % (region_rectangles, photo_rectangles))
            
            return (photo_rectangles, photo_faces)

        for p in xrange(len(region_rectangles)):
            if not region_matches(region_rectangles[p], photo_rectangles[p]):
                messages.append(u'  Region for %s '
                        '(%s vs %s)' %
                        (region_names[p],
                         ','.join(str(c) for c in region_rectangles[p]),
                         ','.join(str(c) for c in photo_rectangles[p])))
                return (photo_rectangles, photo_faces)

        return (None, None)
    
    def check_iptc_data(self, export_file, options, is_original=False, file_updated=False):
        """Tests if a file has the proper keywords and caption in the meta
           data."""
        if not su.getfileextension(export_file) in _EXIF_EXTENSIONS:
            return False
        messages = []

        iptc_data = exiftool.get_iptc_data(export_file)
         
        new_caption = imageutils.get_photo_caption(self.photo, self.container,
                                                   options.captiontemplate)
        if not su.equalscontent(iptc_data.caption, new_caption):
            messages.append(u'  File caption:   %s' % (su.nn_string(iptc_data.caption).strip()))
            messages.append(u'  iPhoto caption: %s' % (new_caption))
        else:
            new_caption = None

        new_keywords = None
        new_date = None
        new_rating = -1
        
        new_keywords = self.get_export_keywords(options.face_keywords)
        if not imageutils.compare_keywords(new_keywords, iptc_data.keywords):
            messages.append(u'  File keywords:   %s' % (u','.join(iptc_data.keywords)))
            if new_keywords == None:
                messages.append(u'  iPhoto keywords: <None>')
            else:
                messages.append(u'  iPhoto keywords: %s' % (u','.join(new_keywords)))
        else:
            new_keywords = None

        if self.photo.rating != None and iptc_data.rating != self.photo.rating:
            messages.append(u'  File rating:   %d' % (iptc_data.rating))
            messages.append(u'  iPhoto rating: %d' % (self.photo.rating))
            new_rating = self.photo.rating

        if iptc_data.hierarchical_subject:
            messages.append(u'  File subjects:   %s' % (u','.join(iptc_data.hierarchical_subject)))
        new_gps = None
        if options.gps and self.photo.gps:
            if (not iptc_data.gps or not self.photo.gps.is_same(iptc_data.gps)):
                if iptc_data.gps:
                    old_gps = iptc_data.gps
                else:
                    old_gps = imageutils.GpsLocation()
                messages.append(u'  File GPS:   %s' % (old_gps.to_string()))
                messages.append(u'  iPhoto GPS: %s' % (self.photo.gps.to_string()))
                new_gps = self.photo.gps

        # Don't export the faces into the original file (could have been
        # cropped).
        do_faces = options.faces and not is_original
        (new_rectangles, new_persons) = self._check_person_iptc_data(
            export_file, iptc_data.region_rectangles, iptc_data.region_names, do_faces, messages)

        if (new_caption != None or new_keywords != None or new_date or
            iptc_data.hierarchical_subject or
            new_gps or new_rating != -1 or new_rectangles != None or new_persons != None):
            su.pout(u'Updating IPTC for %s because of\n%s' % (export_file, u'\n'.join(messages)))
            if (file_updated or imageutils.should_update(options)) and not options.dryrun:
                exiftool.update_iptcdata(export_file, new_caption, new_keywords,
                                         new_date, new_rating, new_gps,
                                         new_rectangles, new_persons, iptc_data.image_width,
                                         iptc_data.image_height, hierarchical_subject=[])
            return True
        return False
    '''

    def is_part_of(self, file_name):
        """Checks if <file> is part of this image."""
        return self.export_file == file_name

"""
_YEAR_PATTERN_INDEX = re.compile(r'([0-9][0-9][0-9][0-9]) (.*)')
"""

class ExportDirectory(object):
    """Tracks an album folder in the export location."""

    def __init__(self, name, iphoto_container, albumdirectory):
        '''
        self.name = name
        '''
        self.iphoto_container = iphoto_container
        self.albumdirectory = albumdirectory
        self.files = {}  # lower case file names -> ExportFile

    def add_iphoto_images(self, images, options):
        """Works through an image folder tree, and builds data for exporting."""
        entries = 0
        template = options.nametemplate

        if images is not None:
            entry_digits = len(str(len(images)))
            for image in images:
                entries += 1
                image_basename = self.make_album_basename(
                    image,
                    entries,
                    str(entries).zfill(entry_digits),
                    template)
                picture_file = ExportFile(image, self.iphoto_container, self.albumdirectory,
                                          image_basename, options)
                self.files[image_basename.lower()] = picture_file

        return entries

    def make_album_basename(self, photo, index, padded_index,
                            name_template):
        """creates unique file name."""
        base_name = imageutils.format_photo_name(photo,
                                                 self.iphoto_container.name,
                                                 index,
                                                 padded_index,
                                                 name_template)
        index = 0
        while True:
            album_basename = base_name
            if index > 0:
                album_basename += "_%d" % index
            if self.files.get(album_basename.lower()) is None:
                return album_basename
            index += 1
        return base_name

    def load_album(self, options):
        """walks the album directory tree, and scans it for existing files."""
        if not os.path.exists(self.albumdirectory):
            su.pout("Creating folder " + self.albumdirectory)
            if not options.dryrun:
                os.makedirs(self.albumdirectory)
            else:
                return
        file_list = os.listdir(self.albumdirectory)
        if file_list is None:
            return

        for f in sorted(file_list):
            # TODO Check ignored files
            '''
            # we won't touch some files
            if imageutils.is_ignore(f):
                continue
            '''

            album_file = unicodedata.normalize("NFC",
                                               os.path.join(self.albumdirectory,
                                                            f))
            if os.path.isdir(album_file):
                if options.originals and f == "Originals":
                    self.scan_originals(album_file, options)
                    continue
                else:
                    delete_album_file(album_file, self.albumdirectory,
                                      "Obsolete export directory", options)
                    continue

            base_name = unicodedata.normalize("NFC",
                                              su.getfilebasename(album_file))
            master_file = self.files.get(base_name.lower())

            # everything else must have a master, or will have to go
            if master_file is None or not master_file.is_part_of(album_file):
                delete_album_file(album_file, self.albumdirectory,
                                  "Obsolete exported file", options)

    '''
    def scan_originals(self, folder, options):
        """Scan a folder of Original images, and delete obsolete ones."""
        file_list = os.listdir(folder)
        if not file_list:
            return

        for f in file_list:
            # We won't touch some files.
            if imageutils.is_ignore(f):
                continue

            originalfile = unicodedata.normalize("NFC", os.path.join(folder, f))
            if os.path.isdir(originalfile):
                delete_album_file(originalfile, self.albumdirectory,
                                  "Obsolete export Originals directory",
                                  options)
                continue

            base_name = unicodedata.normalize("NFC",
                                              su.getfilebasename(originalfile))
            master_file = self.files.get(base_name.lower())

            # everything else must have a master, or will have to go
            if (not master_file or
                originalfile != master_file.original_export_file or
                master_file.photo.rotation_is_only_edit):
                delete_album_file(originalfile, originalfile,
                                  "Obsolete Original", options)
        '''

    def generate_files(self, options):
        """Generates the files in the export location."""
        if not os.path.exists(self.albumdirectory) and not options.dryrun:
            os.makedirs(self.albumdirectory)
        for f in sorted(self.files):
            self.files[f].generate(options)

'''
class IPhotoFace(iphotodata.IPhotoContainer):
    """A photo container based on a face."""

    def __init__(self, face, images):
        data = {}
        data["KeyList"] = []
        iphotodata.IPhotoContainer.__init__(self, data, "Face", False, images)
        self.images = images
        self.name = face
'''

class ExportLibrary(object):
    """The root of the export tree."""

    def __init__(self, albumdirectory):
        self.albumdirectory = albumdirectory
        self.named_folders = {}
        self._abort = False

    '''
    def abort(self):
        """Signals that a currently running export should be aborted as soon
        as possible.
        """
        self._abort = True
    '''

    def _check_abort(self):
        if self._abort:
            print "Export cancelled."
            return True
        return False

    def _find_unused_folder(self, folder):
        """Returns a folder name based on folder that isn't used yet"""
        i = 0
        while True:
            if i > 0:
                proposed = u'%s_(%d)' % (folder, i)
            else:
                proposed = folder
            if self.named_folders.get(proposed) is None:
                return proposed
            i += 1

    def process_albums(self, albums, album_types, folder_prefix, options):
        """Walks trough an Photos album tree, and discovers albums
           (directories)."""
        album_includes = "."
        if options.albums:
            album_includes = options.albums
        album_pattern = re.compile(su.unicode_string(album_includes), re.IGNORECASE)

        folder_includes = "."
        if options.events:
            folder_includes = options.events
        folder_pattern = re.compile(su.unicode_string(folder_includes), re.IGNORECASE)

        for sub_album in albums:
            if self._check_abort():
                return
            sub_name = sub_album.name
            if not sub_name:
                print "Found an album with no name: " + sub_album.albumid
                sub_name = "xxx"
            
            # TODO check the album type
            if (sub_album.albumtype == "None" or
                    sub_album.albumtype not in album_types):
                # print "Ignoring " + sub_album.name + " of type " + \
                # sub_album.albumtype
                continue

            if not album_pattern.match(sub_name):
                _logger.debug(u'Skipping "%s" because it does not match album pattern.', sub_name)
                continue

            _logger.debug(u'Loading "%s".', sub_name)

            folder_hint = sub_album.getfolderhint()
            _logger.debug(u'Parent folders: %s', folder_hint)

            if folder_hint is not None:
                is_folder_match = False
                for parent_folder in folder_hint.split('/'):
                    if folder_pattern.match(parent_folder):
                        is_folder_match = True
                        break
                if not is_folder_match:
                    _logger.debug(u'Skipping "%s" because it does not match folder pattern.', folder_hint)
                    continue

            prefix = folder_prefix  # TODO Normalmente vacio salvo "." para albumes de caras
            if folder_hint is not None:
                for parent_folder in folder_hint.split('/'):
                    prefix = prefix + imageutils.make_foldername(parent_folder) + "/"
            formatted_name = imageutils.format_album_name(
                sub_album, sub_name, options.foldertemplate)
            sub_name = prefix + imageutils.make_foldername(formatted_name)
            sub_name = self._find_unused_folder(sub_name)

            picture_directory = ExportDirectory(
                sub_name, sub_album,
                os.path.join(self.albumdirectory, sub_name))
            if picture_directory.add_iphoto_images(sub_album.images,
                                                   options) > 0:
                self.named_folders[sub_name] = picture_directory

        return len(self.named_folders)

    def load_album(self, options):
        """Loads an existing album (export folder)."""
        if not os.path.exists(self.albumdirectory) and not options.dryrun:
            os.makedirs(self.albumdirectory)

        album_directories = {}
        for folder in sorted(self.named_folders.values()):
            if self._check_abort():
                return
            album_directories[folder.albumdirectory] = True
            folder.load_album(options)

        self.check_directories(self.albumdirectory, "", album_directories,
                               options)

    def check_directories(self, directory, rel_path, album_directories,
                          options):
        """Checks an export directory for obsolete files."""
        if not os.path.exists(directory):
            return True
        contains_albums = False
        for f in su.os_listdir_unicode(directory):
            if self._check_abort():
                return
            album_file = os.path.join(directory, f)
            if os.path.isdir(album_file):
                rel_path_file = os.path.join(rel_path, f)
                if album_file in album_directories:
                    contains_albums = True
                elif not self.check_directories(album_file, rel_path_file,
                                                album_directories, options):
                    delete_album_file(album_file, directory,
                                      "Obsolete directory", options)
                else:
                    contains_albums = True
            else:
                '''
                # we won't touch some files
                if imageutils.is_ignore(f):
                    continue
                '''
                delete_album_file(album_file, directory, "Obsolete",
                                  options)

        return contains_albums

    def generate_files(self, options):
        """Walks through the export tree and sync the files."""
        if not os.path.exists(self.albumdirectory) and not options.dryrun:
            os.makedirs(self.albumdirectory)
        for ndir in sorted(self.named_folders):
            if self._check_abort():
                break
            self.named_folders[ndir].generate_files(options)


def export_iphoto(library, data, options):
    """Main routine for exporting Photos images."""

    print "Scanning Photos data for photos to export..."

    if options.events or options.albums:
        library.process_albums(data.root_album.albums, ["Regular", "Published"], u'', options)

    if options.smarts:
        library.process_albums(data.root_album.albums, ["Smart", "Special Roll", "Special Month", "Flagged"], u'',
                               options)

    if options.facealbums:
        library.process_albums(data.getfacealbums(), ["Face"], unicode(options.facealbum_prefix), options)

    print "Scanning existing files in export folder..."
    library.load_album(options)

    print "Exporting photos from Photos to export folder..."
    library.generate_files(options)

USAGE = """usage: %prog [options]
Exports images and movies from an Photos library into a folder.

Launches as an application if no options are specified.
"""

def get_option_parser():
    """Gets an OptionParser for the Phoshare command line tool options."""
    p = OptionParser(usage=USAGE)
    p.add_option(
        "-a", "--albums",
        help="""Export matching regular albums. The argument
        is a regular expression. Use -a . to export all regular albums.""")
    p.add_option(
        '--captiontemplate', default='{description}',
        help='Template for IPTC image captions. Default: "{description}".')
    p.add_option(
        "-d", "--delete", action="store_true",
        help="Delete obsolete files that are no longer in your Photos library.")
    p.add_option(
        "--dryrun", action="store_true",
        help="""Show what would have been done, but don't change or copy any
             files.""")
    p.add_option("-e", "--folders", dest="events",
                 help="""Export matching folders. The argument is
                 a regular expression. Use -e . to export all folders.""")
    p.add_option("--export",
                 help="""Export images and movies to specified folder.
                      Any files found in this folder that are not part of the
                      export set will be deleted, and files that match will be
                      overwritten if the iPhoto version of the file is
                      different.""")
    p.add_option("--facealbums", action='store_true',
                 help="Create albums (folders) for faces")
    p.add_option("--facealbum_prefix", default="",
                 help='Prefix for face folders (use with --facealbums)')
    p.add_option("--face_keywords", action="store_true",
                 help="Copy face names into keywords.")
    p.add_option("-f", "--faces", action="store_true",
                 help="Copy faces into metadata.")
    p.add_option("--foldertemplate", default="{name}",
                 help="""Template for naming folders. Default: "{name}".""")
    p.add_option("--gps", action="store_true",
                 help="Process GPS location information")
    p.add_option("--iphoto",
                 help="""Path to Photos library, e.g.
                 "%s/Pictures/iPhoto Library".""",
                 default="~/Pictures/iPhoto Library")   # TODO Adapt to Photos default
    p.add_option(
        "-k", "--iptc", action="store_const", const=1, dest="iptc",
        help="""Check the IPTC data of all new or updated files. Checks for
        keywords and descriptions. Requires the program "exiftool" (see
        http://www.sno.phy.queensu.ca/~phil/exiftool/).""")
    p.add_option(
        "-K", "--iptcall", action="store_const", const=2, dest="iptc",
        help="""Check the IPTC data of all files. Checks for
        keywords and descriptions. Requires the program "exiftool" (see
        http://www.sno.phy.queensu.ca/~phil/exiftool/).""")
    p.add_option(
      "-l", "--link", action="store_true",
      help="""Use links instead of copying files. Use with care, as changes made
      to the exported files might affect the image that is stored in the Photos
      library.""")
    p.add_option("--max_create", type='int', default=-1,
                 help='Maximum number of images to create.')
    p.add_option("--max_delete", type='int', default=-1,
                 help='Maximum number of images to delete.')
    p.add_option("--max_update", type='int', default=-1,
                 help='Maximum number of images to update.')
    p.add_option("-n", "--nametemplate", default="{title}",
                 help="""Template for naming image files. Default: "{title}".""")
    p.add_option("-o", "--originals", action="store_true",
                 help="Export original files into Originals.")
    p.add_option("-s", "--smarts",
                 help="""Export matching smart albums. The argument
                 is a regular expression. Use -s . to export all smart albums.""")
    p.add_option("-u", "--update", action="store_true",
                 help="Update existing files.")
    p.add_option('--verbose', action='store_true', 
                 help='Print verbose messages.')
    p.add_option('--version', action='store_true', 
                 help='Print build version and exit.')
    return p


def run_phoshare(cmd_args):
    """main routine for phoshare."""
    parser = get_option_parser()
    (options, args) = parser.parse_args(cmd_args)
    if len(args) != 0:
        parser.error("Found some unrecognized arguments on the command line.")

    if options.version:
        print '%s' % (phoshare.phoshare_version.PHOSHARE_VERSION,)
        return 1

    if options.iptc > 0 and not exiftool.check_exif_tool():
        print >> sys.stderr, ("Exiftool is needed for the --itpc or --iptcall options.")
        return 1

    if not options.iphoto:
        parser.error("Need to specify the Photos library with the --iphoto option.")

    if options.export:
        if not (options.albums or options.events or options.smarts or
                options.facealbums):
            parser.error("Need to specify at least one event, album, or smart "
                         "album for exporting, using the -e, -a, or -s "
                         "options.")
    else:
        parser.error("No action specified. Use --export to export from your "
                     "Photos library.")

    logging_handler = logging.StreamHandler()
    logging_handler.setLevel(logging.DEBUG if options.verbose else logging.INFO)
    _logger.addHandler(logging_handler)

    photos_library_dir = su.expand_home_folder(options.iphoto)
    data = iphotodata.get_iphoto_data(photos_library_dir, verbose=options.verbose)

    options.foldertemplate = unicode(options.foldertemplate)
    options.nametemplate = unicode(options.nametemplate)
    options.captiontemplate = unicode(options.captiontemplate)

    if options.export:
        album = ExportLibrary(su.expand_home_folder(options.export))
        export_iphoto(album, data, options)


def main():
    run_phoshare(sys.argv[1:])

if __name__ == "__main__":
    main()
