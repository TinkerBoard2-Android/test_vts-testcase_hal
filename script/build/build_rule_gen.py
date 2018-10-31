#!/usr/bin/env python
#
# Copyright (C) 2017 The Android Open Source Project
#
# Licensed under the Apache License, Version 2.0 (the 'License');
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an 'AS IS' BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import os
import re

from utils.const import Constant
from vts_spec_parser import VtsSpecParser
import build_rule_gen_utils as utils


class BuildRuleGen(object):
    """Build rule generator for test/vts-testcase/hal."""
    _ANDROID_BUILD_TOP = os.environ.get('ANDROID_BUILD_TOP')
    if not _ANDROID_BUILD_TOP:
        print 'Run "lunch" command first.'
        sys.exit(1)
    _PROJECT_PATH = os.path.join(_ANDROID_BUILD_TOP, 'test', 'vts-testcase',
                                 'hal')
    _VTS_BUILD_TEMPLATE = os.path.join(_PROJECT_PATH, 'script', 'build',
                                       'template', 'vts_build_template.bp')

    def __init__(self, warning_header, package_root, path_root):
        """BuildRuleGen constructor.

        Args:
            warning_header: string, warning header for every generated file.
            package_root: string, prefix of the hal package.
            path_root: string, root path that stores the hal definition.
        """
        self._warning_header = warning_header
        self._vts_spec_parser = VtsSpecParser(package_root, path_root)
        self._package_root = package_root
        self._path_root = path_root

    def UpdateBuildRule(self, test_config_dir):
        """Updates build rules under the configuration directory.

        Args:
            test_config_dir: string, directory storing the configurations.

        Returns:
            True if any file is updated, False otherwise
        """
        hal_list = self._vts_spec_parser.HalNamesAndVersions()
        gen_file_paths, updated = self.UpdateHalDirBuildRule(
            hal_list, test_config_dir)
        updated |= utils.RemoveFilesInDirIf(
            os.path.join(self._ANDROID_BUILD_TOP, test_config_dir),
            lambda x: self._IsAutoGenerated(x) and (x not in gen_file_paths))
        return updated

    def UpdateHalDirBuildRule(self, hal_list, test_config_dir):
        """Updates build rules for vts drivers/profilers.

        Updates vts drivers/profilers for each pair of (hal_name, hal_version)
        in hal_list.

        Args:
            hal_list: list of tuple of strings. For example,
                [('vibrator', '1.3'), ('sensors', '1.7')]
            test_config_dir: string, directory storing the configurations.

        Returns:
            a list of strings where each string contains the path of a checked
            or updated build file.
            boolean, True if any file is updated, False otherwise.
        """
        file_paths = []
        updated = False
        for target in hal_list:
            hal_name = target[0]
            hal_version = target[1]

            hal_dir = os.path.join(
                self._ANDROID_BUILD_TOP, test_config_dir,
                utils.HalNameDir(hal_name), utils.HalVerDir(hal_version))

            file_path = os.path.join(hal_dir, 'build', 'Android.bp')
            updated |= utils.WriteBuildRule(file_path, self._VtsBuildRuleFromTemplate(
                self._VTS_BUILD_TEMPLATE, hal_name, hal_version))
            file_paths.append(file_path)
        return file_paths, updated

    def _VtsBuildRuleFromTemplate(self, template_path, hal_name, hal_version):
        """Returns build rules in string form by filling out a template.

        Reads template from given path and fills it out.

        Args:
          template_path: string, path to build rule template file.
          hal_name: string, name of the hal, e.g. 'vibrator'.
          hal_version: string, version of the hal, e.g '7.4'

        Returns:
          string, complete build rules in string form
        """
        with open(template_path) as template_file:
            build_template = str(template_file.read())
        return self._FillOutBuildRuleTemplate(hal_name, hal_version,
                                              build_template)

    def _FillOutBuildRuleTemplate(self, hal_name, hal_version, template):
        """Returns build rules in string form by filling out given template.

        Args:
          hal_name: string, name of the hal, e.g. 'vibrator'.
          hal_version: string, version of the hal, e.g '7.4'
          template: string, build rule template to fill out.

        Returns:
          string, complete build rule in string form.
        """
        package_root_dir = self._package_root.replace(".", "/")

        def GeneratedOutput(hal_name, hal_version, extension):
            """Formats list of vts spec names into a string.

            Formats list of vts spec name for given hal_name, hal_version
            into a string that can be inserted into build template.

            Args:
              hal_name: string, name of the hal, e.g. 'vibrator'.
              hal_version: string, version of the hal, e.g '7.4'
              extension: string, extension of files e.g. '.cpp'.

            Returns:
              string, to be inserted into build template.
            """
            result = []
            vts_spec_names = self._vts_spec_parser.VtsSpecNames(hal_name,
                                                                hal_version)
            for vts_spec in vts_spec_names:
                result.append('%s/%s/%s/%s%s' %
                              (package_root_dir, utils.HalNameDir(hal_name),
                               hal_version, vts_spec, extension))
            return ListToBuildString(result, 2)

        def ImportedPackages(vts_pkg_type, imported_packages):
            """Formats list of imported packages into a string.

            Formats list of imported packages for given hal_name, hal_version
            into a string that can be inserted into build template.

            Args:
              vts_pkg_type: string 'driver' or 'profiler'
              imported_packages: list of imported packages

            Returns:
              string, to be inserted into build template.
            """
            result = []
            for package in imported_packages:
                if re.match(Constant.HAL_PACKAGE_NAME_PATTERN, package):
                    vts_pkg_name = package + '-vts.' + vts_pkg_type
                    result.append(vts_pkg_name)
                else:
                    result.append(package)
            return ListToBuildString(result, 2)

        build_rule = self._warning_header + template
        build_rule = build_rule.replace('{HAL_NAME}', hal_name)
        build_rule = build_rule.replace('{HAL_NAME_DIR}',
                                        utils.HalNameDir(hal_name))
        build_rule = build_rule.replace('{HAL_VERSION}', hal_version)
        build_rule = build_rule.replace('{PACKAGE_ROOT}', self._package_root)
        build_rule = build_rule.replace('{PACKAGE_ROOT_DIR}', package_root_dir)
        build_rule = build_rule.replace(
            '{HIDL_GEN_ARGS}',
            "-r %s:%s" % (self._package_root, self._path_root))
        build_rule = build_rule.replace(
            '{GENERATED_VTS_SPECS}',
            GeneratedOutput(hal_name, hal_version, ''))
        build_rule = build_rule.replace(
            '{GENERATED_SOURCES}',
            GeneratedOutput(hal_name, hal_version, '.cpp'))
        build_rule = build_rule.replace(
            '{GENERATED_HEADERS}', GeneratedOutput(hal_name, hal_version, '.h'))

        imported_packages = self._vts_spec_parser.ImportedPackagesList(
            hal_name, hal_version)
        build_rule = build_rule.replace(
            '{IMPORTED_DRIVER_PACKAGES}',
            ImportedPackages('driver', imported_packages))
        build_rule = build_rule.replace(
            '{IMPORTED_PROFILER_PACKAGES}',
            ImportedPackages('profiler', imported_packages))

        this_package = '%s.%s@%s' % (self._package_root, hal_name, hal_version)
        imported_packages.append(this_package)
        hal_libs = sorted(imported_packages)

        build_rule = build_rule.replace(
            '{HAL_LIBS}', ListToBuildString(hal_libs, 2))

        return build_rule

    def _IsAutoGenerated(self, abs_file_path):
        """Checks if file was auto-generated.

        Args:
            abs_file_path: string, absolute file path.

        Returns:
            True iff file was auto-generated by BuildRuleGen.
        """
        [dir_name, file_name] = os.path.split(abs_file_path)
        if file_name != 'Android.bp':
            return False
        with open(abs_file_path) as myfile:
            return self._warning_header in myfile.read()

def ListToBuildString(lst, indent_lvl):
    """Formats a list of item into a string to be inserted into build rule.

    Args:
        lst: string list, e.g. [a, b, c].
        indent_lvl: int, indentation level of the output list.

    Returns:
        string to be inserted into build rule.
    """
    single_indent = '    '
    indent = single_indent * indent_lvl
    result = ''.join(map(lambda x: '\n%s"%s",' % (indent, x), sorted(lst)))
    if result:
        result += '\n' + single_indent * (indent_lvl - 1)
    return result
