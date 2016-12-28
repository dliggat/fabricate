from fabric.api import task
from fabric.operations import local
from fabric.contrib.console import confirm
from fabric.utils import abort
from fabric.api import task, execute, env


@task(default=True)
def render():
    import pdb; pdb.set_trace()
    print(env.PATH)
