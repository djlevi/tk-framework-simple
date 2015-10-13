# Copyright (c) 2015 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.


def is_deprecated(published_file):
    """
    Checks if a given published file (as a Shotgun entity dictionary) is
    deprecated or not

    :param published_file:  Shotgun entity dictionary
                            A shotgun entity dictionary for a Published
                            File entity.
    :returns:               Whether the published file is deprecated
                            boolean
    """

    return published_file.get('sg_status_list') == 'dprctd'
