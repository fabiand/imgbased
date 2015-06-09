#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# imgbase
#
# Copyright (C) 2015  Red Hat, Inc.
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

import logging
import re
from .utils import format_to_pattern
from .layers import Base, Image

log = logging.getLogger(__package__)


class NamingScheme():
    vg = None
    names = None

    def __init__(self, names=None, vg=None):
        self.names = names or []
        self.vg = vg

    def image_from_name(self, name):
        raise NotImplementedError

    def tree(self):
        """Returns an ordered list of bases and children
        """
        raise NotImplementedError

    def bases(self):
        return sorted(self.tree())

    def layers(self):
        layers = []
        for b in self.tree():
            layers.extend(b.layers)
        return sorted(layers)

    def last_base(self, lvs=None):
        return self.bases().pop()

    def last_layer(self, base=None, lvs=None):
        return self.layers().pop()

    def suggest_next_base(self, version=None, lvs=None):
        """Dertermine the name for the next base LV name (based on the scheme)
        """
        log.debug("Finding next base")
        try:
            base = self.last_base(lvs)
            base.version = version or int(base.version) + 1
            base.release = 0
            base.layers = []
        except RuntimeError:
            log.debug("No previous base found, creating an initial one")
            base = Base(self.vg, version or 0, 0)
            log.debug("Initial base is now: %s" % base)
        return base

    def suggest_next_layer(self, base=None, lvs=None):
        """Determine the LV name of the next layer (based on the scheme)
        """
        try:
            layer = self.last_layer(base, lvs)
            layer.release = int(layer.release) + 1
            layer.layers = []
        except IndexError:
            base = self.last_base(lvs)
            layer = Image(self.vg, base.version, 1)
        return layer

    def layout(self, lvs=None):
        """List all bases and layers for humans
        """
        idx = []
        try:
            tree = self.tree(lvs)
        except RuntimeError:
            raise RuntimeError("No valid layout found. Initialize if needed.")

        for base in tree:
            idx.append("%s" % base.name)
            for layer in base.layers:
                c = "└" if layer is base.layers[-1] else "├"
                idx.append(" %s╼ %s" % (c, layer.name))
        return "\n".join(idx)


class NvrLikeNaming(NamingScheme):
    """This class is for parsing nvr like schemes.
    Example: Image-0.0

    >>> layers = NvrLikeNaming()
    >>> layers.last_base()
    Traceback (most recent call last):
    ...
    RuntimeError: No bases found: []
    >>> layers.names = ["Image-0.0", "Image-13.0", "Image-2.1", "Image-2.0"]
    >>> layers.last_base()
    <Image-13.0 />


    >>> layers = NvrLikeNaming()
    >>> layers.last_layer()
    Traceback (most recent call last):
    ...
    RuntimeError: No bases found: []
    >>> layers.names = ["Image-0.0", "Image-13.0", "Image-13.1", "Image-2.0"]
    >>> layers.last_layer()
    <Image-13.1 />



    >>> layers = NvrLikeNaming()
    >>> layers.suggest_next_base()
    <Image-0.0 />
    >>> layers.names = ["Image-0.0"]
    >>> layers.suggest_next_base()
    <Image-1.0 />
    >>> layers.names = ["Image-0.0", "Image-13.0", "Image-13.1", "Image-2.0"]
    >>> layers.suggest_next_base()
    <Image-14.0 />
    >>> layers.suggest_next_base(version=20140401)
    <Image-20140401.0 />

    >>> layers = NvrLikeNaming()
    >>> layers.names = ["Image-0.0"]
    >>> layers.suggest_next_layer()
    <Image-0.1 />
    >>> layers.names = ["Image-0.0", "Image-13.0", "Image-13.1", "Image-2.0"]
    >>> layers.suggest_next_layer()
    <Image-13.2 />



    >>> layers = NvrLikeNaming()
    >>> print(layers.layout())
    Traceback (most recent call last):
    ...
    RuntimeError: No valid layout found. Initialize if needed.
    >>> layers.names = ["Image-0.0", "Image-13.0", "Image-2.1", "Image-2.0"]
    >>> layers.names += ["Image-2.2"]
    >>> print(layers.layout())
    Image-0.0
    Image-2.0
     ├╼ Image-2.1
     └╼ Image-2.2
    Image-13.0
    """

    layerformat = "Image-%d.%d"

    def tree(self, lvs=None):
        """Returns a list of bases and children
        >>> layers = NvrLikeNaming()
        >>> layers.tree()
        Traceback (most recent call last):
        ...
        RuntimeError: No bases found: []

        >>> layers.names = ["Image-0.0", "Image-13.0", "Image-2.1"]
        >>> layers.names += ["Image-2.0"]
        >>> layers.tree()
        [<Image-0.0 />, <Image-2.0 [<Image-2.1 />]/>, <Image-13.0 />]
        """
        if callable(self.names):
            lvs = self.names()
        else:
            lvs = lvs or self.names
        laypat = format_to_pattern(self.layerformat)
        sorted_lvs = []

        if lvs is None:
            lvs = self.lvs()

        for lv in lvs:
            if not re.match(laypat, lv):
                continue
            baseidx, layidx = map(int, re.search(laypat, lv).groups())
            sorted_lvs.append((baseidx, layidx))

        sorted_lvs = sorted(sorted_lvs)

        lst = []
        imgs = []
        for v in sorted_lvs:
            if v[1] == 0:
                img = Base(self.vg, *v)
            else:
                img = Image(self.vg, *v)
            imgs.append(img)
        for img in imgs:
            if img.release == 0:
                lst.append(img)
            else:
                lst[-1].layers.append(img)

        if len(lst) == 0:
            raise RuntimeError("No bases found: %s" % lvs)

        return lst

    def image_from_name(self, name):
        laypat = format_to_pattern(self.layerformat)
        log.info("Fetching %s from %s" % (laypat, name))
        match = re.search(laypat, name)
        if not match:
            raise RuntimeError("Failed to parse image name: %s" % name)
        version, release = match.groups()
        return Image(self.vg, int(version), int(release))

# vim: sw=4 et sts=4