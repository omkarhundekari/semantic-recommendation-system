from __future__ import annotations

from abc import ABC, abstractmethod

from execution_evidence.principal import Principal


class PrincipalStoreError(RuntimeError):
    pass


class PrincipalNotFoundError(
    PrincipalStoreError
):
    pass


class PrincipalAlreadyExistsError(
    PrincipalStoreError
):
    pass


class PrincipalKindNotFoundError(
    PrincipalStoreError
):
    pass


class PrincipalStore(ABC):
    @abstractmethod
    def create(
        self,
        principal: Principal,
    ) -> Principal:
        raise NotImplementedError

    @abstractmethod
    def load(
        self,
        principal_id: str,
    ) -> Principal:
        raise NotImplementedError
