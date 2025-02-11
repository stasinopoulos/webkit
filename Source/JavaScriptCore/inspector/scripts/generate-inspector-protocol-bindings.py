#!/usr/bin/env python
#
# Copyright (c) 2014 Apple Inc. All rights reserved.
# Copyright (c) 2014 University of Washington. All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY APPLE INC. AND ITS CONTRIBUTORS ``AS IS''
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO,
# THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
# PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL APPLE INC. OR ITS CONTRIBUTORS
# BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF
# THE POSSIBILITY OF SUCH DAMAGE.

# This script generates JS and C++ bindings for the inspector protocol.
# Generators for individual files are located in the codegen/ directory.

import os.path
import re
import sys
import string
from string import Template
import optparse
import logging

try:
    import json
except ImportError:
    import simplejson as json

try:
    from codegen import *

# When copying generator files to JavaScriptCore's private headers on Mac,
# the codegen/ module directory is flattened. So, import directly.
except ImportError:
    import models
    from models import *
    from generator import *

    from generate_alternate_backend_dispatcher_header import *
    from generate_backend_commands import *
    from generate_backend_dispatcher_header import *
    from generate_backend_dispatcher_implementation import *
    from generate_frontend_dispatcher_header import *
    from generate_frontend_dispatcher_implementation import *
    from generate_protocol_types_header import *
    from generate_protocol_types_implementation import *


logging.basicConfig(format='%(levelname)s: %(message)s', level=logging.ERROR)
log = logging.getLogger('global')


# A writer that only updates file if it actually changed.
class IncrementalFileWriter:
    def __init__(self, filepath, force_output):
        self._filepath = filepath
        self._output = ""
        self.force_output = force_output

    def write(self, text):
        self._output += text

    def close(self):
        text_changed = True
        self._output = self._output.rstrip() + "\n"

        try:
            if self.force_output:
                raise

            read_file = open(self._filepath, "r")
            old_text = read_file.read()
            read_file.close()
            text_changed = old_text != self._output
        except:
            # Ignore, just overwrite by default
            pass

        if text_changed or self.force_output:
            out_file = open(self._filepath, "w")
            out_file.write(self._output)
            out_file.close()


def generate_from_specification(primary_specification_filepath=None,
                                supplemental_specification_filepaths=[],
                                concatenate_output=False,
                                output_dirpath=None,
                                force_output=False,
                                framework_name=""):

    def load_specification(protocol, filepath, isSupplemental=False):
        try:
            with open(filepath, "r") as input_file:
                parsed_json = json.load(input_file)
                protocol.parse_specification(parsed_json, isSupplemental)
        except ValueError as e:
            raise Exception("Error parsing valid JSON in file: " + filepath)

    protocol = models.Protocol(framework_name)
    for specification in supplemental_specification_filepaths:
        load_specification(protocol, specification, isSupplemental=True)
    load_specification(protocol, primary_specification_filepath, isSupplemental=False)

    protocol.resolve_types()

    generators = []
    generators.append(AlternateBackendDispatcherHeaderGenerator(protocol, primary_specification_filepath))
    generators.append(BackendCommandsGenerator(protocol, primary_specification_filepath))
    generators.append(BackendDispatcherHeaderGenerator(protocol, primary_specification_filepath))
    generators.append(BackendDispatcherImplementationGenerator(protocol, primary_specification_filepath))
    generators.append(FrontendDispatcherHeaderGenerator(protocol, primary_specification_filepath))
    generators.append(FrontendDispatcherImplementationGenerator(protocol, primary_specification_filepath))
    generators.append(ProtocolTypesHeaderGenerator(protocol, primary_specification_filepath))
    generators.append(ProtocolTypesImplementationGenerator(protocol, primary_specification_filepath))

    single_output_file_contents = []

    for generator in generators:
        output = generator.generate_output()
        if concatenate_output:
            single_output_file_contents.append('### Begin File: %s' % generator.output_filename())
            single_output_file_contents.append(output)
            single_output_file_contents.append('### End File: %s' % generator.output_filename())
            single_output_file_contents.append('')
        else:
            output_file = IncrementalFileWriter(os.path.join(output_dirpath, generator.output_filename()), force_output)
            output_file.write(output)
            output_file.close()

    if concatenate_output:
        filename = os.path.join(os.path.basename(primary_specification_filepath) + '-result')
        output_file = IncrementalFileWriter(os.path.join(output_dirpath, filename), force_output)
        output_file.write('\n'.join(single_output_file_contents))
        output_file.close()


if __name__ == '__main__':
    allowed_framework_names = ['JavaScriptCore', 'Test']
    cli_parser = optparse.OptionParser(usage="usage: %prog [options] PrimaryProtocol.json [SupplementalProtocol.json ...]")
    cli_parser.add_option("-o", "--outputDir", help="Directory where generated files should be written.")
    cli_parser.add_option("--framework", type="choice", choices=allowed_framework_names, help="The framework that the primary specification belongs to.")
    cli_parser.add_option("--force", action="store_true", help="Force output of generated scripts, even if nothing changed.")
    cli_parser.add_option("-v", "--debug", action="store_true", help="Log extra output for debugging the generator itself.")
    cli_parser.add_option("-t", "--test", action="store_true", help="Enable test mode. Use unique output filenames created by prepending the input filename.")

    options = None

    arg_options, arg_values = cli_parser.parse_args()
    if (len(arg_values) < 1):
        raise ParseException("At least one plain argument expected")

    if not arg_options.outputDir:
        raise ParseException("Missing output directory")

    if arg_options.debug:
        log.setLevel(logging.DEBUG)

    options = {
        'primary_specification_filepath': arg_values[0],
        'supplemental_specification_filepaths': arg_values[1:],
        'output_dirpath': arg_options.outputDir,
        'concatenate_output': arg_options.test,
        'framework_name': arg_options.framework,
        'force_output': arg_options.force
    }

    try:
        generate_from_specification(**options)
    except (ParseException, TypecheckException) as e:
        if arg_options.test:
            log.error(e.message)
        else:
            raise  # Force the build to fail.
