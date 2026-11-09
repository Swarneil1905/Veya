"""One cooperating desktop host owns a workspace until its process exits."""

import os
import stat
import sys
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def own_workspace(root: Path):
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    path = root / '.veya-host.lock'
    if path.is_symlink():
        raise OSError('Workspace lock cannot be a link')
    descriptor = os.open(path, os.O_RDWR | os.O_CREAT | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise OSError('Workspace lock must be a regular file')
        if os.fstat(descriptor).st_size == 0:
            os.write(descriptor, b'0')
        os.lseek(descriptor, 0, os.SEEK_SET)
        if sys.platform == 'win32':
            import msvcrt

            msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            os.lseek(descriptor, 0, os.SEEK_SET)
            if sys.platform == 'win32':
                msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
    finally:
        os.close(descriptor)
    # Keep the inode: unlinking a lock file permits two processes to lock different files.
