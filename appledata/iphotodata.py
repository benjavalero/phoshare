'''iPhoto database: reads iPhoto database and parses it into albums and images.

@author: tsporkert@gmail.com

This class reads iPhoto image, event, album information from the file
AlbumData.xml in the iPhoto library directory. That file is written by iPhoto
for the media browser in other applications. All data are
organized in the class IPhotoData. Images in iPhoto are grouped using events
(formerly knows as rolls) and albums. Each image is in exactly one event, and
optionally, in zero or more albums. Albums can be nested (folders). The album
types are:
Flagged - flagged pictures
Folder - contains other albums
Published - an album published to MobileMe
Regular - a regular user created album
SelectedEventAlbum - most recent album (as shown in iPhoto)
Shelf - list of flagged images
Smart - a user created smart album
SpecialMonth - "Last Month"
SpecialRoll -  "Last Import"
Event - this type does not exist in the XML file, but we use it in this code
        to allow us to treat events just like any other album
Face - Face album (does not exist in iPhoto, only in this code).
None - should not really happen
'''

# Original work Copyright 2010 Google Inc.
# Modified work Copyright 2014 Luke Hagan
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

# Modifications to original source by Luke Hagan:
#
#   2014-06-04: retrieve keywords from iPhoto database using sqlite;
#               fix a bug in copying of originals
#

import datetime
import os
import re
import sys

import appledata.applexml as applexml
import tilutil.imageutils as imageutils
import tilutil.systemutils as su

# List of extensions for image formats that are considered JPEG.
'''
_JPG_EXTENSIONS = ('jpg', 'jpeg')


# Convert Aperture numeric album types to iPhoto album type names.
_APERTURE_ALBUM_TYPES = {
    '1': 'Regular',
    '2': 'Smart',
    '3': 'Special',
    '4': 'Event',
    '5': 'Library',
    '6': 'Folder',
    '8': 'Book',
    '9': 'WebPage',
    '10':'WebJournal',
    '11': 'LightTable',
    '13': 'SmartWebPage',
    '14': 'MobileMeAccount',
    '15': 'MobileMeAlbum',
    '16': 'FlickrAccount',
    '17': 'FlickrAlbum',
    '18': 'OnlineAccount',
    '19': 'Slideshow',
    '20': 'Published',
    # Patching up some albums that are stored with no album type.
    'Last Import': 'Special',
    'Recovered Photos': 'Special',
}

def parse_face_rectangle(string_data):
    """Parse a rectangle specification into an array of coordinate data.

       Args:
         string_data: Rectangle like '{{x, y}, {width, height}}'

       Returns:
         Array of x, y, width and height as floats.
    """
    try:
        return [float(entry.strip('{} ')) for entry in string_data.split(',')]
    except ValueError:
        print >> sys.stderr, 'Failed to parse rectangle ' + string_data
        return [ 0.4, 0.4, 0.2, 0.2 ]
'''


class IPhotoData(object):
    """top level iPhoto data node."""

    def __init__(self, photos_dict):
        """# call with results of readAppleXML."""
        self.data = photos_dict

        self.albums = {}

        """
        self.face_albums = None
        """

        # Master map of keywords
        self.keywords = self.data.get("List of Keywords")

        self.face_names = {}  # Master map of faces
        """
        face_list = self.data.get("List of Faces")
        if face_list:
            for face_entry in face_list.values():
                face_key = face_entry.get("key")
                face_name = face_entry.get("name")
                self.face_names[face_key] = face_name
                # Other keys in face_entry: image, key image face index,
                # PhotoCount, Order
        """

        self.images_by_id = {}
        image_data = self.data.get("Master Image List")
        if image_data:
            for key in image_data:
                image = IPhotoImage(key, image_data.get(key), self.keywords,
                                    self.face_names)
                self.images_by_id[key] = image

        album_data = self.data.get("List of Albums")

        self.root_album = IPhotoContainer("", "Root", None, None)
        for data in album_data:
            album = IPhotoAlbum(data, self.images_by_id, self.albums, self.root_album)
            self.albums[album.albumid] = album

        """
        self.images_by_base_name = None
        self.images_by_file_name = None
        """

    '''
    def _build_image_name_list(self):
        self.images_by_base_name = {}
        self.images_by_file_name = {}

        # build the basename map
        for image in self.images_by_id.values():
            base_name = image.getbasename()
            other_images = self.images_by_base_name.get(base_name)
            if other_images is None:
                other_images = []
                self.images_by_base_name[base_name] = other_images
            other_images.append(image)

            imagename = image.getimagename()
            other_image_list = self.images_by_file_name.get(imagename)
            if other_image_list is None:
                other_image_list = []
                self.images_by_file_name[imagename] = other_image_list
            other_image_list.append(image)
    '''

    def _getapplicationversion(self):
        return self.data.get("Application Version")
    applicationVersion = property(_getapplicationversion, doc='iPhoto version')

    def _getimages(self):
        return self.images_by_id.values()
    images = property(_getimages, doc="List of images")

    '''
    def _getrolls(self):
        return self._rolls.values()
    rolls = property(_getrolls, "List of rolls (events)")

    def getroll(self, album_id):
        return self._rolls.get(album_id)    

    def getbaseimages(self, base_name):
        """returns an IPhotoImage list of all images with a matching base name.
        """
        if not self.images_by_base_name:
            self._build_image_name_list()
        return self.images_by_base_name.get(base_name)

    def getnamedimage(self, file_name):
        """returns an IPhotoImage for the given file name."""
        if not self.images_by_file_name:
            self._build_image_name_list()
        image_list = self.images_by_file_name.get(file_name)
        if image_list:
            return image_list[0]
        return None

    def getallimages(self):
        """returns map from full path name to image."""
        image_map = {}
        for image in self.images_by_id.values():
            image_map[image.GetImagePath()] = image
            image_map[image.thumbpath] = image
            if image.originalpath is not None:
                image_map[image.originalpath] = image
        return image_map


    def check_photos(self):
        """Attempts to verify that the data are not corrupt by checking the "Photos" album
        against the image list.
        """
        photos = None
        for album in self.albums.values():
            if album.master:
                photos = album
                break
        if not photos:
            su.pout("No Photos album in library.")
            return
        # Check size of Photos album vs. Master Image List
        if photos.size != len(self.images_by_id):
            su.pout("Warning: Master image list has %d images, but Photos album has %d images." % (
                len(self.images_by_id), photos.size))
        # Cross check Photos vs. Master Image List
        photos_ids = {}
        for photo in photos.images:
            photos_ids[photo.id] = photo # Make a map of Photos by id for the second phase below
            if not self.images_by_id.has_key(photo.id):
                su.pout("Warning: only in Photos album, but not in Master Image List: %s" % (
                    photo.caption))
                print photo
        for image in self.images:
            if not photos_ids.has_key(image.id):
                su.pout("Warning: only in Master Image List, but not in Photos album: %s" % (
                    image.caption))
                print image


    def check_inalbums(self):
        """Checks that all images are in albums according to their events."""
        messages = []
        for image in self.images_by_id.values():
            if image.IsHidden():
                continue
            roll_name = self._rolls[image.roll].name
            albums = []
            in_album = False

            for album in image.GetAlbums():
                album_name = album.name
                if album.GetAlbumType == "Regular":
                    albums.append(album.name)
                    in_album = True
                    if album_name != roll_name:
                        messages.append(image.caption + ": in wrong album (" +
                                        roll_name + " vs. " + album_name + ").")
                elif (album.isSmart() and album_name.endswith(" Collection") or
                      album_name == "People" or album_name == "Unorganized"):
                    in_album = True
            if not in_album:
                messages.append(image.caption + ": not in any album.")
            if albums:
                messages.append(image.caption + ": in more than one album: " +
                                " ".join(albums))
        messages.sort()
        for message in messages:
            print message

    def getfacealbums(self):
        """Returns a map of albums for faces."""
        if self.face_albums:
            return self.face_albums.values()

        # Build the albums on first call
        self.face_albums = {}

        for image in self.images:
            for face in image.getfaces():
                face_album = self.face_albums.get(face)
                if not face_album:
                    face_album = IPhotoFace(face)
                    self.face_albums[face] = face_album
                face_album.addimage(image)
        return self.face_albums.values()


    def print_summary(self):
        named_rolls = {}
        for roll in self._rolls.values():
            named_rolls[roll.name] = roll
        for roll in sorted(named_rolls.keys()):
            named_rolls[roll].print_summary()
        named_albums = {}
        for album in self.albums.values():
            named_albums[album.name] = album
        for album in sorted(named_albums):
            named_albums[album].print_summary()
    '''

'''
_CAPTION_PATTERN = re.compile(
    r'([12][0-9][0-9][0-9])([01][0-9])([0123][0-9]) (.*)')
'''

class IPhotoImage(object):
    """Describes an image in the iPhoto database."""

    def __init__(self, key, data, keyword_map, face_map):
        '''
        self.id = key
        self.data = data
        '''
        self._caption = su.nn_string(data.get("Caption")).strip()
        '''
        self.comment = su.nn_string(data.get("Comment")).strip()
        '''

        self.date = datetime.datetime.now() # TODO Get photo date
        '''
        if data.has_key("DateAsTimerInterval"):
            self.date = applexml.getappletime(data.get("DateAsTimerInterval"))
        else:
            # Try to get the date from a the caption in "YYYYMMDD ..." format
            m = re.match(_CAPTION_PATTERN, self._caption)
            if m:
                year = int(m.group(1))
                month = int(m.group(2))
                if not month:
                    month = 1
                date = int(m.group(3))
                if not date:
                    date = 1
                self.date = datetime.datetime(year, month, date)
            else:
                self.date = None
        if data.has_key("ModDateAsTimerInterval"):
            self.mod_date = applexml.getappletime(data.get("ModDateAsTimerInterval"))
        else:
            if data.has_key("MetaModDateAsTimerInterval"):
                self.mod_date = applexml.getappletime(data.get("MetaModDateAsTimerInterval"))
            else:
                self.mod_Date = None
        '''

        self.image_path = data.get("ImagePath")

        '''
        if data.has_key("Rating"):
            self.rating = int(data.get("Rating"))
        else:
            self.rating = None
        if data.get("longitude"):
            latitude = float(data.get("latitude"))
            longitude = float(data.get("longitude"))
            self.gps = imageutils.GpsLocation(latitude, longitude)
        else:
            self.gps = None

        self.keywords = []
        keyword_list = data.get("Keywords")
        if keyword_list is not None:
            for i in keyword_list:
                self.keywords.append(keyword_map.get(i))

        self.originalpath = data.get("OriginalPath")
        self.roll = data.get("Roll") 

        self.albums = []  # list of albums that this image belongs to
        self.faces = []
        self.face_rectangles = []
        '''

        self.event_name = ''    # name of event (roll) that this image belongs to
        self.event_index = ''   # index within event
        self.event_index0 = ''  # index with event, left padded with 0

        '''
        face_list = data.get("Faces")
        if face_list:
            for face_entry in face_list:
                face_key = face_entry.get("face key")
                face_name = face_map.get(face_key)
                if face_name:
                    self.faces.append(face_name)
                    # Rectangle is '{{x, y}, {width, height}}' as ratios,
                    # referencing the lower left corner of the face rectangle,
                    # with lower left corner of image as (0,0)
                    rectangle = parse_face_rectangle(face_entry.get("rectangle"))
                    # Convert to using center of area, relative to upper left corner of image
                    rectangle[0] += rectangle[2] / 2.0
                    rectangle[1] = max(0.0, 1.0 - rectangle[1] - rectangle[3] / 2.0)
                    self.face_rectangles.append(rectangle)
                # Other keys in face_entry: face index

                # Now sort the faces left to right.
                sorted_names = {}
                sorted_rectangles = {}
                for i in xrange(len(self.faces)):
                    x = self.face_rectangles[i][0]
                    while sorted_names.has_key(x):
                        x += 0.00001
                    sorted_names[x] = self.faces[i]
                    sorted_rectangles[x] = self.face_rectangles[i]
                self.faces = [sorted_names[x] for x in sorted(sorted_names.keys())]
                self.face_rectangles = [
                    sorted_rectangles[x] for x in sorted(sorted_rectangles.keys())]
        '''

    '''
    def getimagepath(self):
        """Returns the full path to this image.."""
        return self.image_path
    '''

    def getimagename(self):
        """Returns the file name of this image.."""
        name = os.path.split(self.image_path)[1]
        return name

    '''
    def getbasename(self):
        """Returns the base name of the main image file."""
        return su.getfilebasename(self.image_path)
    '''

    def _getcaption(self):
        if not self._caption:
            return self.getimagename()
        return self._caption
    caption = property(_getcaption, doc="Caption (title) of the image")

    '''
    def ismovie(self):
        """Tests if this image is a movie."""
        return self.data.get("MediaType") == "Movie"

    def addalbum(self, album):
        """Adds an album to the list of albums for this image."""
        self.albums.append(album)

    def addface(self, name):
        """Adds a face (name) to the list of faces for this image."""
        self.faces.append(name)

    def getfaces(self):
        """Gets the list of face tags for this image."""
        return self.faces

    def ishidden(self):
        """Tests if the image is hidden (using keyword "Hidden")"""
        return "Hidden" in self.keywords

    def _getthumbpath(self):
        return self.data.get("ThumbPath")
    thumbpath = property(_getthumbpath, doc="Path to thumbnail image")

    def _getrotationisonlyedit(self):
        return self.data.get("RotationIsOnlyEdit")
    rotation_is_only_edit = property(_getrotationisonlyedit,
                                     doc="Rotation is only edit.")

    def _search_for_file(self, folder_path, basename):
        """Scans recursively through a folder tree and returns the path to the
           first file it finds that starts with "basename".
        """
        for file_name in su.os_listdir_unicode(folder_path):
            path = os.path.join(folder_path, file_name)
            if os.path.isdir(path):
                path = self._search_for_file(path, basename)
                if path:
                    return path
            elif file_name.startswith(basename):
                return path
        return None
    '''


class IPhotoContainer(object):
    """Base class for IPhotoAlbum and IPhotoRoll."""

    def __init__(self, name, albumtype, data, images):
        self.name = name

        '''
        self._date = None
        self.uuid = None
        self.comment = None

        if data:
            if data.get("RollDateAsTimerInterval"):
                self._date = applexml.getappletime(data.get("RollDateAsTimerInterval"))
            if data.get("uuid"):
                self.uuid = data.get("uuid")
                if self.uuid == 'lastImportAlbum':
                    albumtype = "Special Roll"
            if 'Comments' in data:
                self.comment = data.get("Comments")
        '''

        # TODO Convert Photos numeric album types to type names.
        if not albumtype:
            su.pout(u'No album type for %s.' % name)
        self.albumtype = albumtype
        self.data = data

        '''
        self.albumid = -1
        '''

        self.images = []
        self.albums = []

        '''
        self.master = False
        '''

        hidden = 0
        if data and ("KeyList" in data):
            keylist = data.get("KeyList")
            for key in keylist:
                if not key:
                    continue
                image = images.get(key)
                if image:
                    self.images.append(image)
                else:
                    hidden += 1
                    su.pout(u"%s: image with id %s does not exist - could be hidden." % (name, key))
        
        if hidden:
            su.pout(u"%s: %d images not exported (probably hidden)." % (name, hidden))

        '''
        self._assign_names()
        '''

    '''
    def _assign_names(self):
        """Assigns sequential index values to all images if this container is an Event."""
        if self.albumtype != 'Event':
            return
        i = 1
        index_digits = len(str(len(self.images)))
        for image in self.images:
            image.event_name = self.name
            image.event_index = i
            image.event_index0 = str(i).zfill(index_digits)
            i += 1

    def merge(self, other_roll):
        for image in other_roll.images:
            self.images.append(image)
        self._assign_names()

    def _getsize(self):
        return len(self.images)
    size = property(_getsize, "Gets the size (# of images) of this album.")
    '''

    def getfolderhint(self):
        return self.data['FolderPath']

    '''
    def getcommentwithouthints(self):
        """Gets the image comments, with any folder hint lines removed"""
        result = []
        if self.comment:
            for line in self.comment.split("\n"):
                if not line.startswith("@"):
                    result.append(line)
        return "\n".join(result)
    '''

    def addalbum(self, album):
        """adds an album to this container."""
        self.albums.append(album)

    def _getdate(self):
        # TODO USED WHEN DATE TEMPLATE FOR FOLDER NAME. RETURN FOR EXAMPLE THE ALBUM MODIFICATION DATE.
        return datetime.datetime.now()
    date = property(_getdate, doc='date of container (based on oldest image)')

    '''
    def tostring(self):
        """Gets a string that describes this album or event."""
        return "%s (%s)" % (self.name, self.albumtype)

    def print_summary(self):
        if self.albumtype != "Event":
            return
        original_count = 0
        file_size = 0
        original_size = 0
        face_count = 0
        for image in self.images:
            face_count += len(image.getfaces())
            if image.originalpath:
                original_count += 1
                if os.path.exists(image.originalpath):
                    original_size += os.path.getsize(image.originalpath)
            if os.path.exists(image.image_path):
                file_size += os.path.getsize(image.image_path)
                if not image.originalpath:
                    original_size += os.path.getsize(image.image_path)
        file_size = file_size / 1024.0 / 1024.0
        original_size = original_size / 1024.0 / 1024.0
        su.pout(u"%-50s %4d images (%6.1f MB), %3d originals (%6.1f MB), %3d faces" % (
            self.tostring(), len(self.images), file_size, original_count, original_size,
            face_count))
    '''


class IPhotoAlbum(IPhotoContainer):
    """Describes an iPhoto Album."""

    def __init__(self, data, images, album_map, root_album):
        IPhotoContainer.__init__(self, data.get("AlbumName"),
                                 data.get("Album Type") if ("Album Type" in data) else "Regular",
                                 data, images)
        self.albumid = data.get("AlbumId")

        # TODO NO SE QUE SIGNIFICA ESTA PROPIEDAD "MASTER"
        if data.has_key("Master"):
            self.master = True

        self.parent = root_album
        self.parent.addalbum(self)


'''
class IPhotoFace(object):
    """An IPhotoContainer compatible class for a face."""

    def __init__(self, face):
        self.name = face
        self.albumtype = "Face"
        self.albumid = -1
        self.images = []
        self.albums = []
        self.comment = ""
        self.date = datetime.datetime.now()

    def _getsize(self):
        return len(self.images)
    size = property(_getsize, "Gets the size (# of images) of this album.")

    def getfolderhint(self):
        """Gets a suggested folder name from comments."""
        return None

    def getcommentwithouthints(self):
        """Gets the image comments, with any folder hint lines removed"""
        return ""

    def addimage(self, image):
        """Adds an image to this container."""
        self.images.append(image)
        # Set the face date based on the earlierst image.
        if image.date and image.date < self.date:
            self.date = image.date

    def tostring(self):
        """Gets a string that describes this album or event."""
        return "%s (%s)" % (self.name, self.albumtype)
'''

def get_iphoto_data(photos_library_dir, verbose=False):
    """reads the iPhoto database and converts it into an iPhotoData object."""
    if verbose:
        print "Reading %s database from %s..." % ('Photos', photos_library_dir)

    photos_dict = applexml.read_apple_library(photos_library_dir)

    data = IPhotoData(photos_dict)

    if data.applicationVersion != 477:
        # Library version for El Capitan is 1021
        raise ValueError, "Photos library version %s has not been tested and it's not supported" % (
            data.applicationVersion)

    return data
