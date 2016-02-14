# Copyright (c) 2015 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
Hook that loads defines all the available actions, broken down by publish type. 
"""

import re
import sgtk
import os
import pymel.core as pm
import maya.cmds as cmds
import maya.mel as mel
from sgtk.platform.qt import QtGui

HookBaseClass = sgtk.get_hook_baseclass()

class MayaActions(HookBaseClass):
    
    ##############################################################################################################
    # public interface - to be overridden by deriving classes 
    
    def generate_actions(self, sg_publish_data, actions, ui_area):
        """
        Returns a list of action instances for a particular publish.
        This method is called each time a user clicks a publish somewhere in the UI.
        The data returned from this hook will be used to populate the actions menu for a publish.
    
        The mapping between Publish types and actions are kept in a different place
        (in the configuration) so at the point when this hook is called, the loader app
        has already established *which* actions are appropriate for this object.
        
        The hook should return at least one action for each item passed in via the 
        actions parameter.
        
        This method needs to return detailed data for those actions, in the form of a list
        of dictionaries, each with name, params, caption and description keys.
        
        Because you are operating on a particular publish, you may tailor the output 
        (caption, tooltip etc) to contain custom information suitable for this publish.
        
        The ui_area parameter is a string and indicates where the publish is to be shown. 
        - If it will be shown in the main browsing area, "main" is passed. 
        - If it will be shown in the details area, "details" is passed.
        - If it will be shown in the history area, "history" is passed. 
        
        Please note that it is perfectly possible to create more than one action "instance" for 
        an action! You can for example do scene introspection - if the action passed in 
        is "character_attachment" you may for example scan the scene, figure out all the nodes
        where this object can be attached and return a list of action instances:
        "attach to left hand", "attach to right hand" etc. In this case, when more than 
        one object is returned for an action, use the params key to pass additional 
        data into the run_action hook.
        
        :param sg_publish_data: Shotgun data dictionary with all the standard publish fields.
        :param actions: List of action strings which have been defined in the app configuration.
        :param ui_area: String denoting the UI Area (see above).
        :returns List of dictionaries, each with keys name, params, caption and description
        """
        app = self.parent
        app.log_debug("Generate actions called for UI element %s. "
                      "Actions: %s. Publish Data: %s" % (ui_area, actions, sg_publish_data))
        
        action_instances = []

        simple_framework = self.load_framework(self._FRAMEWORK_SIMPLE_NAME)
        utils = simple_framework.import_module("utils")

        deprecated_actions_disabled = app.get_setting("disable_deprecated_files_actions", False)
        actions_disabled = (deprecated_actions_disabled and
                            utils.is_deprecated(sg_publish_data))
        
        if "reference" in actions and not actions_disabled:
            action_instances.append( {"name": "reference", 
                                      "params": None,
                                      "caption": "Create Reference", 
                                      "description": "This will add the item to the scene as a standard reference."} )

        if "import" in actions and not actions_disabled:
            action_instances.append( {"name": "import", 
                                      "params": None,
                                      "caption": "Import into Scene", 
                                      "description": "This will import the item into the current scene."} )

        if "texture_node" in actions:
            action_instances.append( {"name": "texture_node",
                                      "params": None, 
                                      "caption": "Create Texture Node", 
                                      "description": "Creates a file texture node for the selected item.."} )
            
        if "udim_texture_node" in actions:
            # Special case handling for Mari UDIM textures as these currently only load into 
            # Maya 2015 in a nice way!
            if self._get_maya_version() >= 2015:
                action_instances.append( {"name": "udim_texture_node",
                                          "params": None, 
                                          "caption": "Create Texture Node", 
                                          "description": "Creates a file texture node for the selected item.."} )    
        return action_instances

    def execute_action(self, name, params, sg_publish_data):
        """
        Execute a given action. The data sent to this be method will
        represent one of the actions enumerated by the generate_actions method.
        
        :param name: Action name string representing one of the items returned by generate_actions.
        :param params: Params data, as specified by generate_actions.
        :param sg_publish_data: Shotgun data dictionary with all the standard publish fields.
        :returns: No return value expected.
        """
        app = self.parent
        app.log_debug("Execute action called for action %s. "
                      "Parameters: %s. Publish Data: %s" % (name, params, sg_publish_data))

        simple_framework = self.load_framework(self._FRAMEWORK_SIMPLE_NAME)
        utils = simple_framework.import_module("utils")

        # Handle groups recursively. <jbee>
        if sg_publish_data["published_file_type"]["name"].lower() == "group":
            child_data = self.parent.shotgun.find_one(
                "PublishedFile",
                [["id", "is", sg_publish_data["id"]]],
                fields=["sg_children"],
            )
            for child in child_data["sg_children"]:
                # We need to make sure we provide the same data from SG
                # for the children that is typically given, so we'll query
                # the list of fields that came with the parent group. This
                # will travel down the tree as we recurse in the event of
                # groups nested inside of groups.
                child_expanded = self.parent.shotgun.find_one(
                    "PublishedFile",
                    [['id', 'is', child['id']]],
                    fields=sg_publish_data.keys(),
                )
                self.execute_action(name, params, child_expanded)
        else:
            # resolve path
            path = self.get_publish_path(sg_publish_data)
            
            if name == "reference":
                if not utils.is_deprecated(sg_publish_data) or self._confirm_action_on_deprecated("reference"):
                    self._create_reference(path, sg_publish_data)

            if name == "import":
                if not utils.is_deprecated(sg_publish_data) or self._confirm_action_on_deprecated("import"):
                    self._do_import(path, sg_publish_data)
            
            if name == "texture_node":
                self._create_texture_node(path, sg_publish_data)
                
            if name == "udim_texture_node":
                self._create_udim_texture_node(path, sg_publish_data)
                        
           
    ##############################################################################################################
    # helper methods which can be subclassed in custom hooks to fine tune the behaviour of things

    _FRAMEWORK_SIMPLE_NAME = "tk-framework-simple_v0.x.x"

    def _confirm_action_on_deprecated(self, action_name):
        """
        Confirms that the user really wants to do an action on a deprecated file.

        :param action_name: The name of the action requested.
        :returns:           If the action should be done or not
        """
        box = QtGui.QMessageBox()
        box.setText("Loading a Deprecated File")
        box.setInformativeText(
                "You are about to %s a deprecated file. Do you really want to %s it?" %
                (action_name, action_name))
        box.setIcon(QtGui.QMessageBox.Warning)

        accept = box.addButton(action_name.capitalize(), QtGui.QMessageBox.YesRole)
        cancel = box.addButton(QtGui.QMessageBox.Cancel)

        box.setDefaultButton(cancel)

        box.exec_()

        return box.clickedButton() == accept
    
    def _create_reference(self, path, sg_publish_data):
        """
        Create a reference with the same settings Maya would use
        if you used the create settings dialog.
        
        :param path: Path to file.
        :param sg_publish_data: Shotgun data dictionary with all the standard publish fields.
        """
        if not os.path.exists(path):
            raise Exception("File not found on disk - '%s'" % path)
        
        nodes = cmds.file(
            path,
            reference=True,
            lockReference=True,
            loadReferenceDepth="all",
            namespace=':',
            returnNewNodes=True,
        )

        reference_node = cmds.referenceQuery(path, referenceNode=True)
        _hookup_shaders(reference_node)

    def _do_import(self, path, sg_publish_data):
        """
        Create a reference with the same settings Maya would use
        if you used the create settings dialog.
        
        :param path: Path to file.
        :param sg_publish_data: Shotgun data dictionary with all the standard publish fields.
        """
        if not os.path.exists(path):
            raise Exception("File not found on disk - '%s'" % path)

        cmds.file(
            path,
            i=True,
            renameAll=True,
            loadReferenceDepth="all",
            preserveReferences=True,
            namespace=':',
        )
            
    def _create_texture_node(self, path, sg_publish_data):
        """
        Create a file texture node for a texture
        
        :param path:             Path to file.
        :param sg_publish_data:  Shotgun data dictionary with all the standard publish fields.
        :returns:                The newly created file node
        """
        file_node = cmds.shadingNode('file', asTexture=True)
        cmds.setAttr( "%s.fileTextureName" % file_node, path, type="string" )
        return file_node

    def _create_udim_texture_node(self, path, sg_publish_data):
        """
        Create a file texture node for a UDIM (Mari) texture
        
        :param path:             Path to file.
        :param sg_publish_data:  Shotgun data dictionary with all the standard publish fields.
        :returns:                The newly created file node
        """
        # create the normal file node:
        file_node = self._create_texture_node(path, sg_publish_data)
        if file_node:
            # path is a UDIM sequence so set the uv tiling mode to 3 ('UDIM (Mari)')
            cmds.setAttr("%s.uvTilingMode" % file_node, 3)
            # and generate a preview:
            mel.eval("generateUvTilePreview %s" % file_node)
        return file_node
            
    def _get_maya_version(self):
        """
        Determine and return the Maya version as an integer
        
        :returns:    The Maya major version
        """
        if not hasattr(self, "_maya_major_version"):
            self._maya_major_version = 0
            # get the maya version string:
            maya_ver = cmds.about(version=True)
            # handle a couple of different formats: 'Maya XXXX' & 'XXXX':
            if maya_ver.startswith("Maya "):
                maya_ver = maya_ver[5:]
            # strip of any extra stuff including decimals:
            major_version_number_str = maya_ver.split(" ")[0].split(".")[0]
            if major_version_number_str and major_version_number_str.isdigit():
                self._maya_major_version = int(major_version_number_str)
        return self._maya_major_version
        
def _hookup_shaders(reference_node):
    
    hookup_prefix = "SHADER_HOOKUP_"
    shader_hookups = {}
    for node in cmds.ls(type="script"):
        if not node.startswith(hookup_prefix):
            continue
        obj_pattern = node.replace(hookup_prefix, "") + "\d*"
        obj_pattern = "^" + obj_pattern + "$"
        shader = cmds.scriptNode(node, query=True, beforeScript=True)
        shader_hookups[obj_pattern] = shader
        
    for node in (cmds.referenceQuery(reference_node, nodes=True) or []):
        for (obj_pattern, shader) in shader_hookups.iteritems():
            if re.match(obj_pattern, node, re.IGNORECASE):
                # assign the shader to the object
                cmds.file(unloadReference=reference_node, force=True)
                cmds.setAttr(reference_node + ".locked", False)
                cmds.file(loadReference=reference_node)
                cmds.select(node, replace=True)
                cmds.hyperShade(assign=shader)
                cmds.file(unloadReference=reference_node)
                cmds.setAttr(reference_node + ".locked", True)
                cmds.file(loadReference=reference_node)
                
