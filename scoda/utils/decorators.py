import warnings


def deprecated(message):
    def decorator(func):
        def wrapper(*args, **kwargs):
            warnings.warn(f"{func.__name__} is deprecated: {message}", category=DeprecationWarning, stacklevel=2)
            return func(*args, **kwargs)

        return wrapper

    return decorator
