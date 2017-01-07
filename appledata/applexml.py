'''Reads iPhoto or iTunes XML data files'''

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
#   2014-06-04: retrieve keywords from iPhoto database using sqlite
#
   
import calendar
import datetime
import unicodedata
import os
import sys
from xml import sax
import sqlite3

import tilutil.systemutils as su

"""
APPLE_BASE = calendar.timegm((2001, 1, 1, 0, 0, 0, 0, 0, -1))
APPLE_BASE2 = datetime.datetime.fromtimestamp(calendar.timegm((2001, 1, 1, 0, 0, 0)))


def getappletime(value):
    '''Converts a numeric Apple time stamp into a date and time'''
    try:
        # datetime.datetime.fromtimestamp() takes only int, which limits it to 12/13/1901
        # as the earliest possible date. Use an alternate calculation for earlier dates.
        # This one however adjusts for daylight savings time, so summer times are off by an
        # hour from the time recorded in iPhoto.
        if APPLE_BASE + float(value) < -sys.maxint:
            return APPLE_BASE2 + datetime.timedelta(seconds=float(value))
        return datetime.datetime.fromtimestamp(APPLE_BASE + float(value))
    except (TypeError, ValueError) as _e:
        # bad time stamp in database, default to "now"
        return datetime.datetime.now()

class AppleXMLResolver(sax.handler.EntityResolver): #IGNORE:W0232
    '''Helper to deal with XML entity resolving'''

    def __init__(self):
        pass

    def resolveEntity(self, _publicId, systemId): #IGNORE:C0103
        '''Simple schema, resolve all entities to just the systemId'''
        return systemId
"""


def get_photos_library_file(library_dir):
    """Locates the Photos Library.apdb file."""
    if os.path.exists(library_dir) and os.path.isdir(library_dir):
        photos_library_file = os.path.join(library_dir, "database", "Library.apdb")
        if os.path.exists(photos_library_file):
            return photos_library_file
    raise ValueError, ("%s does not appear to be a valid Photos "
                       "library location.") % (library_dir)


def get_photos_metaschema_file(library_dir):
    """Locates the Photos metaSchema.db file."""
    if os.path.exists(library_dir) and os.path.isdir(library_dir):
        photos_metaschema_file = os.path.join(library_dir, "database", "metaSchema.db")
        if os.path.exists(photos_metaschema_file):
            return photos_metaschema_file
    raise ValueError, ("%s does not appear to be a valid Photos "
                       "library location.") % (library_dir)


def get_photos_imageproxies_file(library_dir):
    """Locates the Photos ImageProxies.apdb file."""
    if os.path.exists(library_dir) and os.path.isdir(library_dir):
        photos_imageproxies_file = os.path.join(library_dir, "database", "ImageProxies.apdb")
        if os.path.exists(photos_imageproxies_file):
            return photos_imageproxies_file
    raise ValueError, ("%s does not appear to be a valid Photos "
                       "library location.") % (library_dir)


def read_apple_library(photos_library_dir):
    photos_dict = {}

    photos_metaschema_file = get_photos_metaschema_file(photos_library_dir)
    photos_imageproxies_file = get_photos_imageproxies_file(photos_library_dir)
    photos_library_file = get_photos_library_file(photos_library_dir)

    if photos_metaschema_file:
        # Library Version
        library_version = None
        conn1 = sqlite3.connect(photos_metaschema_file)
        c1 = conn1.cursor()
        c1.execute('select value from LiGlobals where keyPath is ?', ("libraryCompatibleBackToVersion",))
        for result in c1.fetchall():
            library_version = int(result[0])
        photos_dict['Application Version'] = library_version


    if photos_imageproxies_file:
        # Resources
        conn3 = sqlite3.connect(photos_imageproxies_file)
        c3 = conn3.cursor()
        c3.execute('select attachedModelId, resourceUuid, filename from RKModelResource '
                  'where attachedModelType = 2 and resourceType = 4')
        resources_dict = {}
        for result in c3.fetchall():
            attached_model_id = int(result[0])
            resource_dict = {}
            resource_dict['resourceUuid'] = result[1]
            resource_dict['filename'] = result[2]
            resources_dict[attached_model_id] = resource_dict


    if photos_metaschema_file:
        # Folders
        conn2 = sqlite3.connect(photos_library_file)
        c2 = conn2.cursor()
        c2.execute('select uuid, modelId, name, parentFolderUuid, folderPath from RKFolder '
                  'where folderType = 1 and isInTrash = 0 and isMagic = 0')
        folders_by_id = {}
        folders_by_uuid = {}
        for result in c2.fetchall():
            uuid = result[0]
            model_id = int(result[1])
            folder_dict = {}
            folder_dict['name'] = result[2]
            folder_dict['folderPath'] = result[4]
            folders_by_uuid[uuid] = folder_dict
            folders_by_id[model_id] = folder_dict

        # Albums
        c2 = conn2.cursor()
        c2.execute('select modelId, uuid, name, folderUuid from RKAlbum where albumType = 1'
                   ' and albumSubclass = 3 and isInTrash = 0 and isMagic = 0')
        albums = []
        albums_by_id = {}
        for result in c2.fetchall():
            album_id = int(result[0])
            album_data = {}
            album_data['AlbumName'] = unicodedata.normalize("NFC", result[2])
            album_data['KeyList'] = []

            # Load folder path
            album_data['FolderPath'] = None
            album_folder_uuid = result[3]
            if folders_by_uuid.has_key(album_folder_uuid):
                album_folder = folders_by_uuid[album_folder_uuid]
                parent_folder_ids = album_folder['folderPath']
                folder_path = ''
                for folder_id in parent_folder_ids.split('/'):
                    if folder_id and folders_by_id.has_key(int(folder_id)):
                        parent_folder = folders_by_id[int(folder_id)]
                        folder_path = os.path.join(folder_path, parent_folder['name'])
                album_data['FolderPath'] = folder_path

            # TODO COMPLETE
            albums.append(album_data)
            albums_by_id[album_id] = album_data
        photos_dict['List of Albums'] = albums

        # Masters
        c2 = conn2.cursor()
        c2.execute('select modelId, uuid, imagePath from RKMaster '
                  'where importComplete = 1 and isInTrash = 0')
        masters_dict = {}
        for result in c2.fetchall():
            model_id = int(result[0])
            master_dict = {}
            master_dict['imagePath'] = result[2]
            masters_dict[model_id] = master_dict

        # Images
        images = {}
        for master_id in masters_dict:
            image_data = {}
            if resources_dict.has_key(master_id):
                resource_dict = resources_dict[master_id]
                image_data['Caption'] = None  # TODO
                resourceUuid = resource_dict['resourceUuid']
                folder1 = str(ord(resourceUuid[0]))
                folder2 = str(ord(resourceUuid[1]))
                filename = resource_dict['filename']
                image_data['ImagePath'] = os.path.join(photos_library_dir, 'resources', 'modelresources',
                                                       folder1, folder2, resourceUuid, filename)
            else:
                master_dict = masters_dict[master_id]
                image_data['Caption'] = None  # TODO
                imagePath = master_dict['imagePath']
                image_data['ImagePath'] = os.path.join(photos_library_dir, 'Masters', imagePath)
            # TODO COMPLETE
            images[master_id] = image_data
        photos_dict['Master Image List'] = images

        # TODO Keywords
        photos_dict['List of Keywords'] = []

        # Album-Versions
        c2 = conn2.cursor()
        c2.execute('select albumId, versionId from RKAlbumVersion')
        for result in c2.fetchall():
            album_id = int(result[0])
            version_id = int(result[1])

            if albums_by_id.has_key(album_id):
                album_data = albums_by_id[album_id]
                album_data['KeyList'].append(version_id)

    return photos_dict
