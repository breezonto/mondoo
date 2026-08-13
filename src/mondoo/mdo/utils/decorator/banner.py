import time


def with_body_banner(hint: str, sym='=', half_len=20):
    def decorator(func):
        def wrapper(*args, **kwargs):
            line = f"{sym*half_len} {hint} {sym*half_len}"
            footer = sym * len(line)

            print(line + "\n")
            result = func(*args, **kwargs)
            print(f"\n{footer}")

            return result
        return wrapper
    return decorator


def with_result_banner(hint: str, sym='=', half_len=20):
    def decorator(func):
        def wrapper(*args, **kwargs):
            line = f"{sym*half_len} {hint} {sym*half_len}"
            footer = sym * len(line)

            result = func(*args, **kwargs)

            return f"{line}\n\n{result}\n{footer}"
        return wrapper
    return decorator


def with_duration_banner(hint: str, sym='=', half_len=20):
    def decorator(func):
        def wrapper(*args, **kwargs):
            line = f"{sym*half_len} {hint} {sym*half_len}"
            footer = sym * len(line)

            print(line + "\n")
            start_time = time.time()
            result = func(*args, **kwargs)
            end_time = time.time()
            duration = end_time - start_time
            print(f"Duration: {duration:.6f} seconds")
            print(f"\n{footer}")

            return result
        return wrapper
    return decorator