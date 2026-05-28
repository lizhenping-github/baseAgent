from abc import ABC, abstractmethod


class BaseMemory(ABC):
    @abstractmethod
    async def load(self) -> str:
        pass

    @abstractmethod
    async def save(self, content: str) -> None:
        pass

    @abstractmethod
    async def update(self, new_content: str) -> str:
        pass
