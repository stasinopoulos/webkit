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


import logging
import string
import re
from string import Template

from generator import Generator
from generator_templates import GeneratorTemplates as Templates

log = logging.getLogger('global')


class AlternateBackendDispatcherHeaderGenerator(Generator):
    def __init__(self, model, input_filepath):
        Generator.__init__(self, model, input_filepath)

    def output_filename(self):
        return 'InspectorAlternateBackendDispatchers.h'

    def generate_output(self):
        headers = [
            '"InspectorProtocolTypes.h"',
            '<JavaScriptCore/InspectorBackendDispatcher.h>',
        ]

        header_args = {
            'headerGuardString': re.sub('\W+', '_', self.output_filename()),
            'includes': '\n'.join(['#include ' + header for header in headers]),
        }

        domains = self.domains_to_generate()
        sections = []
        sections.append(self.generate_license())
        sections.append(Template(Templates.AlternateDispatchersHeaderPrelude).substitute(None, **header_args))
        sections.append('\n'.join(filter(None, map(self._generate_handler_declarations_for_domain, domains))))
        sections.append(Template(Templates.AlternateDispatchersHeaderPostlude).substitute(None, **header_args))
        return '\n\n'.join(sections)

    def _generate_handler_declarations_for_domain(self, domain):
        if not domain.commands:
            return ''

        command_declarations = []
        for command in domain.commands:
            command_declarations.append(self._generate_handler_declaration_for_command(command))

        handler_args = {
            'domainName': domain.domain_name,
            'commandDeclarations': '\n'.join(command_declarations),
        }

        return Generator.wrap_with_guard_for_domain(domain, Template(Templates.AlternateBackendDispatcherHeaderDomainHandlerInterfaceDeclaration).substitute(None, **handler_args))

    def _generate_handler_declaration_for_command(self, command):
        lines = []
        parameters = ['long callId']
        for _parameter in command.call_parameters:
            parameters.append('%s in_%s' % (Generator.type_string_for_unchecked_formal_in_parameter(_parameter), _parameter.parameter_name))

        command_args = {
            'commandName': command.command_name,
            'parameters': ', '.join(parameters),
        }
        lines.append('    virtual void %(commandName)s(%(parameters)s) = 0;' % command_args)
        return '\n'.join(lines)
