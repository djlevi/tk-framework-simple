# Copyright (c) 2015 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

from sgtk import Hook


class FilterPublishes(Hook):
    """
    Hook that can be used to filter the list of publishes returned from Shotgun
    for the current location.
    """

    def execute(self, publishes, **kwargs):
        """
        Main hook entry point

        :param publishes:    List of dictionaries
                             A list of  dictionaries for the current location
                             within the app.  Each item in the list is a
                             Dictionary of the form:

                             {
                                 "sg_publish" : {Shotgun entity dictionary for
                                                 a Published File entity}
                             }


        :returns:            The filtered list of dictionaries of the same form
                             as the input 'publishes'
                             list
        """
        app = self.parent
        shotgun_utils = self.load_framework(
            "tk-framework-shotgunutils_v2.x.x")
        settings = shotgun_utils.import_module("settings")
        settings_manager = settings.UserSettings(app)

        # This user setting is expected to be set by the app using this hook
        # (e.g. the loader) to control whether to show the deprecated files or
        # filter them out.
        show_deprecated = settings_manager.retrieve(
            "show_deprecated_files", False)

        if not show_deprecated:
            framework = self.load_framework("tk-framework-simple_v0.x.x")
            utils = framework.import_module("utils")
            publishes = [publish for publish in publishes
                         if not utils.is_deprecated(publish["sg_publish"])]

        return publishes
