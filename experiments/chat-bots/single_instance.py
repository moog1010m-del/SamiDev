"""Process-scoped state lock, released by the OS even after a crash."""
from pathlib import Path
import os
class SingleInstance:
    def __init__(self,state):self.path=Path(state).with_suffix('.lock');self.file=None
    def __enter__(self):
        self.path.parent.mkdir(parents=True,exist_ok=True);self.file=self.path.open('a+b')
        try:
            self.file.seek(0)
            if not self.file.read(1):self.file.write(b'0');self.file.flush()
            self.file.seek(0)
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(self.file.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(self.file.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError:
            self.file.close();raise RuntimeError('A sidecar already owns this state') from None
        return self
    def __exit__(self,*args):self.file.close()
