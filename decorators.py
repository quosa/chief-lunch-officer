#Adapted from http://stackoverflow.com/questions/15572288/general-decorator-to-wrap-try-except-in-python
def get_ignore_errors_decorator(default_value=''):

    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except:
                return default_value

        return wrapper

    return decorator
