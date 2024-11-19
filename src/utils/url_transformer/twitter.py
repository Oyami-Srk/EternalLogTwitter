import re

from . import URLTransformer


class TwitterURLTransformer(URLTransformer):
    PATTERN = re.compile(r'https?://(?:www\.)?(?:twitter|x)\.com/([^/]+)/status/(\d+)')
    TEMPLATE = 'https://x.com/{0}/status/{1}'

    @property
    def apply_to(self) -> list[str]:
        return ['x.com', 'twitter.com']

    def transform(self, url: str) -> str:
        match = self.PATTERN.match(url)
        if match:
            return self.TEMPLATE.format(match.group(1), match.group(2))
        return url
