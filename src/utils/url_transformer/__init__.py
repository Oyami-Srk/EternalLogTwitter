from abc import ABC, abstractmethod


class URLTransformer(ABC):
    @property
    @abstractmethod
    def apply_to(self) -> list[str]:
        pass

    @abstractmethod
    def transform(self, url: str) -> str:
        pass

    def __str__(self) -> str:
        return f"[URLTransformer for {','.join(self.apply_to)}]"


from .twitter import TwitterURLTransformer

URLTransformers: dict[str, URLTransformer] = {}
for transformer in [
    TwitterURLTransformer()
]:
    for host in transformer.apply_to:
        URLTransformers[host] = transformer
