from fabric.api import task
from fabric.operations import local
from fabric.contrib.console import confirm
from fabric.utils import abort


@task(default=True)
def render():
    print('hello')
