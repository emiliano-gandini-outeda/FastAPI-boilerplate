"""Generic provider registry for storage backends.

Shared by the cache and rate limiter providers, which differ only in the
backend contract they store and the exception they raise for missing backends.
"""

from typing import Generic, NoReturn, Protocol, TypeVar, runtime_checkable


@runtime_checkable
class Pingable(Protocol):
    async def ping(self) -> bool: ...


BackendT = TypeVar("BackendT", bound=Pingable)


class BackendProvider(Generic[BackendT]):
    """Registry of named backends with a default backend.

    Subclasses must implement ``_raise_not_found`` to raise the
    subsystem-specific exception for a missing backend.
    """

    def __init__(self) -> None:
        """Initialize the provider with no registered backends."""
        self._backends: dict[str, BackendT] = {}
        self._default_backend: str | None = None

    def _raise_not_found(self, name: str | None, *, for_default: bool = False) -> NoReturn:
        raise NotImplementedError

    def register_backend(self, name: str, backend: BackendT, default: bool = False) -> None:
        """Register a backend.

        Args:
            name: The name of the backend.
            backend: The backend instance.
            default: Whether this backend should be the default.
        """
        self._backends[name] = backend
        if default or self._default_backend is None:
            self._default_backend = name

    def get_backend(self, name: str | None = None) -> BackendT:
        """Get a backend by name, or the default backend if no name is given.

        Args:
            name: The name of the backend to get. If None, the default backend is returned.

        Returns:
            The requested backend.

        Raises:
            The subsystem's backend-not-found error if the backend is not available.
        """
        backend_name = name or self._default_backend
        if backend_name is None or backend_name not in self._backends:
            self._raise_not_found(backend_name)

        return self._backends[backend_name]

    def set_default_backend(self, name: str) -> None:
        """Set the default backend to use.

        Args:
            name: The name of the backend to set as default.

        Raises:
            The subsystem's backend-not-found error if the backend does not exist.
        """
        if name not in self._backends:
            self._raise_not_found(name, for_default=True)

        self._default_backend = name

    async def ping_all(self) -> dict[str, bool]:
        """Ping all registered backends.

        Returns:
            A dictionary mapping backend names to their availability.
        """
        results = {}
        for name, backend in self._backends.items():
            results[name] = await backend.ping()
        return results

    def list_backends(self) -> dict[str, type[BackendT]]:
        """List all registered backends.

        Returns:
            A dictionary mapping backend names to their types.
        """
        return {name: type(backend) for name, backend in self._backends.items()}

    @property
    def default_backend_name(self) -> str | None:
        """Get the name of the default backend, or None if no backends are registered."""
        return self._default_backend
