from typing import TypeVar, Generic

T = TypeVar('T')


class HNIterator(Generic[T]):

    def __init__(self, iterator) -> None:
        super().__init__()
        self.iterator = iterator
        self._next = next(iterator)

    def next(self) -> T:
        if self._next:
            ret_val = self._next
            try:
                self._next = next(self.iterator)
            except StopIteration:
                self._next = None
            return ret_val
        else:
            raise StopIteration()

    def has_next(self) -> bool:
        return self._next is not None

    def peek(self) -> T:
        return self._next
