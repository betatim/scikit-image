import functools
import importlib
from importlib.metadata import entry_points
from functools import lru_cache


@lru_cache
def all_backends():
    """List all installed backends and information about them"""
    backends = {}
    backends_ = entry_points(group="skimage_backends")
    backend_infos = entry_points(group="skimage_backend_infos")

    for backend in backends_:
        backends[backend.name] = {"module": backend}
        try:
            info = backend_infos[backend.name]
            # Double () to load and then call the backend information function
            backends[backend.name]["info"] = info.load()()
        except KeyError:
            pass

    return backends


def dispatchable(func):
    func_name = func.__name__
    # The submodule inside skimage, used to know which (sub)module to import
    # from the backend
    func_module = func.__module__.removeprefix("skimage.")

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        for name, backend in all_backends().items():
            # If we have a BackendInformation object we check if the
            # method we are looking for is implemented in the backend
            if "info" in backend:
                if (
                    f"{func.__module__}.{func_name}"
                    not in backend["info"].supported_functions
                ):
                    continue

            backend_module = backend["module"].load()

            # Import the module that contains the backend implementation,
            # continuing to the next backend in case this fails
            try:
                mod = importlib.import_module(
                    backend_module.__name__ + "." + func_module
                )
            except ImportError:
                continue

            # Allow the backend to accept/reject a call based on the values
            # of the arguments
            # backend_wants_func = getattr(mod, f"i_want_{func_name}", None)
            # if backend_wants_func is not None:
            #    wants_it = backend_wants_func(*args, **kwargs)
            # else:
            #    wants_it = True

            backend_func = getattr(mod, func_name, None)
            if backend_func is not None:
                return backend_func(*args, **kwargs)

        else:
            return func(*args, **kwargs)

    return wrapper


class BackendInformation:
    """Information about a backend

    A backend that wants to provide additional information about itself
    should return an instance of this from its information entry-point.
    """

    def __init__(self, supported_functions):
        self.supported_functions = supported_functions