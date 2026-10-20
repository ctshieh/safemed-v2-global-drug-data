"""Preserve partially retrieved official sources after failures, without overwriting inputs."""
import contextlib, shutil, sys, tempfile
@contextlib.contextmanager
def retained_temp(*,dir):
    path=tempfile.mkdtemp(prefix='FAILED-OR-INCOMPLETE-',dir=dir)
    try:
        yield path
    except BaseException:
        print('Partial source evidence retained: '+path,file=sys.stderr,flush=True)
        raise
    else:
        shutil.rmtree(path)
