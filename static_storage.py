from urllib.parse import urljoin

from whitenoise.storage import CompressedManifestStaticFilesStorage


class PabloStaticStorage(CompressedManifestStaticFilesStorage):
    def url(self, name, force=False):
        if name == 'vendor/bootswatch':
            return urljoin(self.base_url, name)

        return super().url(name, force=force)