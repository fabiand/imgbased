#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# imgbase
#
# Copyright (C) 2014  Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Author(s): Fabian Deutsch <fabiand@redhat.com>
#

import os
from six.moves import configparser
from io import StringIO

import logging


log = logging.getLogger(__package__)


class Configuration():
    """Datastructure to access localy configured remotes

    We configure remote repositories/locations locally,
    then we can use remote.pull(img) to add a remote image to our
    local VG.
    Just like git.

    >>> example = '''
    ... [core]
    ... '''

    >>> rs = Configuration()
    >>> rs.cfgstr = example
    """
    CFG_FILE = "imgbased.conf"
    CFG_DIR = "imgbased.conf.d/"
    USER_CFG_PREFIX = "/etc/"
    VENDOR_CFG_PREFIX = "/usr/lib/imgbased/"
    cfgstr = None

    class Section(object):
        def __repr__(self):
            vals = sorted(self.__dict__.items())
            return "<%s (%s) %s />" % (self.__class__.__name__,
                                       self._type, vals)

        def section_name(self):
            if hasattr(self, "name"):
                n = "%s %s" % (self._type, self.name)
            else:
                n = self._type
            return n

        def save(self):
            raise NotImplementedError()

    class CoreSection(Section):
        _type = "core"
        mode = None

    class PoolSection(Section):
        _type = "pool"
        name = None
        pull = None

    _known_section_types = [
        # Add some default classes
        CoreSection,
        PoolSection
    ]

    @staticmethod
    def register_section(klass):
        Configuration._known_section_types.append(klass)

    def _parser(self, only_user_file=False):
        p = configparser.ConfigParser()

        def read_loc(loc_prefix):
            cfgfile = loc_prefix + self.CFG_FILE
            cfgdir = loc_prefix + self.CFG_DIR

            log.debug("Reading config file: %s" % cfgfile)
            log.debug("Reading config dir: %s" % cfgdir)

            if os.path.exists(cfgfile):
                p.read(cfgfile)
                log.debug("Read file")

            if not only_user_file:
                """Also read the dir"""
                if os.path.exists(cfgdir):
                    for fn in os.listdir(cfgdir):
                        fullfn = cfgdir + "/" + fn
                        log.debug("Also reading: %s" % fullfn)
                        if os.path.isfile(fullfn):
                            p.read(fullfn)
                else:
                    log.debug("No config dir found")

        if self.cfgstr:
            log.debug("Using cfgstr")
            # Used for doctests
            try:
                p.readfp(StringIO(self.cfgstr.decode("ascii")))
            except:
                p.readfp(StringIO(self.cfgstr))
        else:
            locs = [self.VENDOR_CFG_PREFIX]
            if only_user_file:
                locs = [self.USER_CFG_PREFIX]
            else:
                locs += [self.USER_CFG_PREFIX]

            for loc in locs:
                log.debug("Passing prefix: %s" % loc)
                read_loc(loc)

        return p

    def core(self):
        return self.section(Configuration.CoreSection)

    def pool(self, name):
        return self.section(Configuration.PoolSection, name)

    def section(self, filter_type, name=None):
        sections = [s for s in self.sections(filter_type)
                    if (name is None
                        or (hasattr(s, "name") and s.name == name))]
        if not sections:
            raise RuntimeError("Failed to retrieve section: %s %s" %
                               (filter_type, name))
        return sections[0]

    def sections(self, filter_type=None):
        """A config parser which reads a string

        >>> example = '''
        ... [core]
        ... mode=1'''

        >>> rs = Configuration()
        >>> rs.cfgstr = example

        >>> def writer(p):
        ...     dst = StringIO()
        ...     p.write(dst)
        ...     dst.seek(0)
        ...     rs.cfgstr = dst.read()
        ...     print(rs.cfgstr)

        >>> rs._write = writer

        >>> list(rs.sections())
        [<CoreSection (core) [('mode', '1')] />]

        >>> list(rs.sections("core"))
        [<CoreSection (core) [('mode', '1')] />]

        >>> list(rs.sections(Configuration.CoreSection))
        [<CoreSection (core) [('mode', '1')] />]

        >>> core = rs.section(Configuration.CoreSection)
        >>> core
        <CoreSection (core) [('mode', '1')] />
        >>> core.mode = 11
        >>> rs.save(core)
        [core]
        mode = 11
        <BLANKLINE>
        <BLANKLINE>

        >>> rs.remove(rs.section("core"))
        <BLANKLINE>

        >>> pool = Configuration.PoolSection()
        >>> pool.name = "<pool>"
        >>> pool.url = "<url>"
        >>> rs.save(pool)
        [pool <pool>]
        url = <url>
        <BLANKLINE>
        <BLANKLINE>
        """
        p = self._parser()

        klasses = Configuration._known_section_types
        createSection = dict((k._type, k) for k in klasses)

        log.debug("Parsing all sections: %s" % p.sections())
        for sectionname in p.sections():
            # Tokens should be:
            # [<type>]
            # or
            # [<type>, <name>]
            _type, sep, name = sectionname.partition(" ")

            if filter_type:
                # A bit magic to allow filtering by type and class
                if type(filter_type) is type:
                    filter_type = filter_type._type
                if filter_type != _type:
                    continue

            section = createSection[_type]()

            if name:
                section.name = name

            sectiondict = dict(p.items(sectionname))
            section.__dict__.update(sectiondict)

            yield section

    def remove(self, section):
        p = self._parser(True)
        sname = section.section_name()
        if p.has_section(sname):
            p.remove_section(sname)
            self._write(p)
        else:
            log.warn("Unknown section: %s" % sname)

    def save(self, section):
        p = self._parser(True)
        sname = section.section_name()
        if not p.has_section(sname):
            p.add_section(sname)
        for k, v in section.__dict__.items():
            if k == "name":
                continue
            p.set(sname, k, str(v))
        self._write(p)

    def _write(self, p):
        cfgfile = self.USER_CFG_PREFIX + self.USER_CFG_FILE
        with open(cfgfile, 'wt') as configfile:
            p.write(configfile)
            log.debug("Wrote config file %s" % configfile)

# vim: sw=4 et sts=4:
