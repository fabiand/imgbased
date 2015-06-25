
import subprocess
import logging
from ..utils import mounted, systemctl, File


log = logging.getLogger(__package__)


def init(app):
    app.hooks.connect("pre-arg-parse", add_argparse)
    app.hooks.connect("post-arg-parse", check_argparse)


def add_argparse(app, parser, subparsers):
    if not app.experimental:
        return

    s = subparsers.add_parser("volume",
                              help="Volume management")
    s.add_argument("--list", action="store_true",
                   "List all known volumnes")
    s.add_argument("--attach", metavar="PATH",
                   "Attach a volume to the current layer")
    s.add_argument("--detach", metavar="PATH",
                   "Detach a volume from the current layer")
    s.add_argument("--create", metavar="PATH",
                   "Create a volume for PATH")


def check_argparse(app, args):
    log.debug("Operating on: %s" % app.imgbase)
    if args.command == "volume":
        vols = Voumes(app.imgbase)
        if args.list:
            print(vols.list())
        elif args.create:
            where, size = args.create
            vols.create(where, size)
        elif args.remove:
            vols.remove(args.remove)
        elif args.attach:
            vols.attach(args.attach)
        elif args.detach:
            vols.detach(args.detach)


class Volumes(object):
    tag_volume = "imgbased:volume"

    imgbase = None

    mountfile_tmpl = """# Created by imgbased
[Mount]
What={what}
Where={where}
SloppyOptions={options}
"""

    automountfile_tmpl = """# Created by imgbased
[Automount]
Where={where}
"""

    def __init__(self, imgbase):
        self.imgbase = imgbase

    def list(self):
        lvs = self.imgbase.LV.find_by_tag(self.tag_volume)
        return lvs

    def _volname(self, where):
        return where.lstrip("/").replace("-", "--").replace("/", "-")

    def _mountfilename(self, where, unittype):
        safewhere = self._volname(where)
        return "/etc/systemd/system/%s.%s" % (safewhere, unittype)

    def create(self, where, size):
        volname = self._volname(where)

        # Create the vol
        vol = self.imgbase._thinpool().create_thinvol(volname, size)
        vol.addtag(self.tag_volume)

        # Populate
        with mounted(vol.path) as target:
            Rsync.sync(where + "/", target.rstrip("/"))

        self.attach(where)

    def remove(self, where):

    def attach(self, where):
        f = File(self._mountfilename(where, "mount"))
        f.write(self.mountfile_tmpl.format(what=what,
                                           where=where,
                                           options=options))

        f = File(self._mountfilename(where, "automount"))
        f.write(self.automountfile_tmpl.format(where=where))

        systemctl.daemon_reload()

        # Access it to start it
        os.listdir(where)

    def detach(self, where):
        mount = self._mountfilename(where, "mount")
        automount = self._mountfilename(where, "automount")

        for unitfile in [automount, mount]:
            systemctl.stop(os.path.basename(unitfile))
            File(unitfile).remove()

        systemctl.daemon_reload()


# vim: sw=4 et sts=4
