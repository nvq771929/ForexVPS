"""OS-backed single-writer lease for the local companion (released on crash)."""
from contextlib import contextmanager


@contextmanager
def exclusive(path):
    stream=open(path,'a+b')
    try:
        if stream.seek(0,2)==0:stream.write(b'1');stream.flush()
        stream.seek(0)
        try:
            import msvcrt
        except ImportError:
            import fcntl
            try:fcntl.flock(stream.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
            except OSError:raise RuntimeError('Another learner is already using this journal') from None
        else:
            try:msvcrt.locking(stream.fileno(),msvcrt.LK_NBLCK,1)
            except OSError:raise RuntimeError('Another learner is already using this journal') from None
        yield
    finally:stream.close()
