from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Tuple

from execution_evidence.oidc_provider_config import (
    OIDCProviderConfig,
)


class OIDCProviderConfigSourceError(
    RuntimeError
):
    pass


class OIDCProviderConfigSource(ABC):
    """Source of OIDC verification metadata.

    Provider configuration is verification metadata only.
    Implementations must not carry client secrets, private
    keys, refresh tokens, or other authentication secrets.
    """

    @abstractmethod
    def load(
        self,
    ) -> Tuple[OIDCProviderConfig, ...]:
        raise NotImplementedError
