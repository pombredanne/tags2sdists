import logging
import os
import shutil
import sys

from zest.releaser import release

from tags2sdists.utils import command

logger = logging.getLogger(__name__)


def find_tarball(directory, name, version):
    """Return matching tarball filename from dist/ dir (if found).

    Setuptools generates a source distribution in a ``dist/`` directory and we
    need to find the exact filename, whether .tgz or .zip.

    We expect "name + '-' + version + '.tar.gz'", but we *can* get a
    -dev.r1234.tar.gz as that can be configured in a setup.cfg.  Not pretty,
    but we don't want to force anyone to modify old tags.

    """
    dir_contents = os.listdir(os.path.join(directory, 'dist'))
    candidates = [tarball for tarball in dir_contents
                  if tarball.endswith('.gz')
                  and tarball.startswith(name + '-' + version)]
    if not candidates:
        logger.error("No recognizable distribution found for %s, version %s",
                     name, version)
        logger.error("Contents of %s: %r", directory, dir_contents)
        return
    if len(candidates) > 1:
        # Should not happen.
        logger.warn("More than one candidate distribution found: %r",
                    candidates)
    tarball = candidates[0]
    return os.path.join(directory, 'dist', tarball)


class CheckoutBaseDir(object):
    """Wrapper around the directory containing the checkout directories."""

    def __init__(self, base_directory):
        self.base_directory = base_directory

    def checkout_dirs(self):
        """Return directories inside the base directory."""
        directories = [os.path.join(self.base_directory, d)
                       for d in os.listdir(self.base_directory)]
        return [d for d in directories if os.path.isdir(d)]


class CheckoutDir(object):
    """Wrapper around a directory with a checkout in it."""

    def __init__(self, directory, existing_sdists=None):
        if existing_sdists is None:
            self.existing_sdists = set()
        else:
            self.existing_sdists = set(existing_sdists)
        self._missing_tags = None
        self.start_directory = os.getcwd()
        os.chdir(directory)
        self.wrapper = release.Releaser()
        self.wrapper.prepare()  # zest.releaser requirement.

    def missing_tags(self):
        """Return difference between existing sdists and available tags."""
        if self._missing_tags is None:
            self._missing_tags = list(
                set(self.wrapper.vcs.available_tags()) - self.existing_sdists)
        return self._missing_tags

    def create_sdist(self, tag):
        """Create an sdist and return the full file path of the .tar.gz."""
        package = self.wrapper.vcs.name
        logger.info("Making tempdir for %s with tag %s...",
                    package, tag)
        self.wrapper.vcs.checkout_from_tag(tag)
        # checkout_from_tag() chdirs to a temp directory that we need to clean up
        # later.
        self.temp_tagdir = os.path.realpath(os.getcwd())
        logger.debug("Tag checkout placed in %s", self.temp_tagdir)
        python = sys.executable
        logger.debug(command("%s setup.py sdist" % python))
        tarball = find_tarball(self.temp_tagdir, package, tag)
        return tarball

    def cleanup(self):
        """Clean up temporary tag checkout dir."""
        shutil.rmtree(self.temp_tagdir)
        os.chdir(self.start_directory)
