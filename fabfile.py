import boto3
import datetime
import glob
import jinja2
import json
import os
import pprint
import subprocess
import yaml

from botocore.exceptions import ClientError, ValidationError
from collections import OrderedDict
from fabric.api import task
from fabric.operations import local
from fabric.contrib.console import confirm
from fabric.utils import abort
from fabric.api import task, execute, env


import logging; logging.basicConfig()
import coloredlogs
logger = logging.getLogger(__name__)
coloredlogs.install(level=logging.INFO)


def _construct_ordered_mapping(loader, node, deep=False):
    """Configure PyYaml to preserve order in dictionaries
    (ensures CloudFormation templates render in an expected top-level key order).
    """
    if isinstance(node, yaml.MappingNode):
        loader.flatten_mapping(node)
    return OrderedDict(loader.construct_pairs(node, deep))


def _construct_yaml_ordered_map(loader, node, deep=False):
    """Configure PyYaml to preserve order in dictionaries
    (ensures CloudFormation templates render in an expected top-level key order).
    """
    data = OrderedDict()
    yield data
    value = _construct_ordered_mapping(loader, node, deep)
    data.update(value)

yaml.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_yaml_ordered_map)


def _json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""
    if isinstance(obj, datetime.datetime):
        serial = obj.isoformat()
        return serial
    raise TypeError ("Type not serializable")


def _ensure_dir(directory):
    """Creates directory if it does not already exist."""
    if not os.path.exists(directory):
        os.makedirs(directory)
        logger.info('Created directory: %s', directory)


class Project(object):

    def __init__(self, project=None):
        self._data = { }
        self.name = project or env.project
        _ensure_dir(self.project_output_dir)
        self.configuration

    @property
    def configuration(self):
        if 'project' not in env:
            raise CfabException('No project set. Use fab --set project=$NAME')
        project_file = os.path.join(PROJECT_DIR, self.name + '.yaml')
        if not os.path.exists(project_file):
            raise CfabException('Unable to find project file {0}'.format(project_file))

        with open(project_file, 'r') as project_file_contents:
            self._data['project_file'] = yaml.load(project_file_contents.read())
        description = "A '{0}' stack for {1}; rendered on {2} by {3}.".format(self.template_name,
            self.name, datetime.date.today().isoformat(), os.path.basename(ROOT_DIR))
        self._data['metadata'] = {
            'description': description,
            'commit_hash': subprocess.check_output(['git', 'rev-parse', 'HEAD'])[:-1],
            'commit_message': '"' + subprocess.check_output([
                'git', 'log', '-1', '--pretty=%B']).strip()
                                                   .replace('"', '')
                                                   .replace('#', '')
                                                   .replace('\n', '')
                                                   .replace(':', ' ') + '"' }
        return self._data

    @property
    def template_name(self):
        return self._data['project_file']['template']

    @property
    def rendered_template_filename(self):
        return os.path.join(self.project_output_dir, RENDERED_TEMPLATE_FILE)

    @property
    def rendered_parameters_filename(self):
        return os.path.join(self.project_output_dir, RENDERED_PARAMETERS_FILE)

    @property
    def project_output_dir(self):
        directory = os.path.join(OUTPUT_DIR, self.name)
        return directory

    @property
    def parameters(self):
        if not 'parameters' in self._data['project_file']:
            return []
        return [{'ParameterKey': k,
                 'ParameterValue': v,
                 'UsePreviousValue': False}
            for (k,v) in self._data['project_file']['parameters'].items()]

class CfabException(Exception): pass


ROOT_DIR     = os.path.dirname(__file__)
PROJECT_DIR  = os.path.join(ROOT_DIR, 'projects')
TEMPLATE_DIR = os.path.join(ROOT_DIR, 'templates')
OUTPUT_DIR   = os.path.join(ROOT_DIR, '_output')
RENDERED_TEMPLATE_FILE = 'template.yaml'
RENDERED_PARAMETERS_FILE = 'parameters.json'



@task(default=True)
def render():
    project = Project()
    _ensure_dir(OUTPUT_DIR)
    jenv = jinja2.Environment(trim_blocks=True, lstrip_blocks=True, undefined=jinja2.StrictUndefined)
    jenv.loader = jinja2.FileSystemLoader(TEMPLATE_DIR)
    template = jenv.get_template('{0}.yaml'.format(project.template_name))
    rendered = template.render(**project.configuration)

    # Write the template file to _output.
    with open(project.rendered_template_filename, 'w') as output_contents:
        output_contents.write(rendered)
        logger.info('Wrote {0} to {1}'.format(
            project.template_name, project.rendered_template_filename))

    # Write the parameters file to _output.
    if project.parameters:
        output_json = json.dumps(project.parameters, indent=2, separators=(',', ': '))
        with open(project.rendered_parameters_filename, 'w') as output_contents:
            output_contents.write(output_json)
            logger.info('Wrote parameters file: {0}'.format(project.rendered_parameters_filename))


@task
def validate():
    """Validates the rendered template against the CloudFormation API."""
    client = boto3.client('cloudformation')
    project = Project()
    with open(project.rendered_template_filename, 'r') as output_contents:
        try:
            client.validate_template(TemplateBody=output_contents.read())
        except (ClientError, ValidationError) as e:
            logger.error('Unable to validate {0}. Exception: {1}'.format(
                project.rendered_template_filename, e))
            abort('Template validation error')


@task
def clean():
    """Removes rendered output for this project."""
    project = Project()
    for f in glob.glob(os.path.join(project.project_output_dir, '*')):
        os.remove(f)
        logger.info('Deleted {0}'.format(f))
    os.rmdir(project.project_output_dir)
    logger.info('Deleted {0}'.format(project.project_output_dir))


@task
def describe():
    client = boto3.client('cloudformation')
    project = Project()
    stack_name = project.name
    resp = client.describe_stacks(StackName=stack_name)
    # logger.info(pprint.pformat(resp))
    logger.info(json.dumps(resp, indent=2, default=_json_serial))



@task
def provision():
    """Creates or updates a CloudFormation stack.
    """
    client = boto3.client('cloudformation')
    project = Project()
    stack_name = project.name

    update = False
    try:
        resp = client.describe_stacks(StackName=stack_name)
        message = 'Stack {0} exists, and is in state {1}. Proceed with update?'.format(
            stack_name, resp['Stacks'][0]['StackStatus'])
        if not confirm(message):
            abort('Aborting.')
        else:
            update = True
    except ClientError:
        logger.info('No stack named {0}; proceeding with stack creation'.format(stack_name))

    with open(project.rendered_template_filename) as template_contents, open(
        project.rendered_parameters_filename) as parameters_contents:
        parameters = json.load(parameters_contents)
        if update:
            response = client.update_stack(StackName=stack_name,
                                           TemplateBody=template_contents.read(),
                                           Parameters=parameters,
                                           Capabilities=['CAPABILITY_IAM'])
        else:
            response = client.create_stack(StackName=stack_name,
                                           TemplateBody=template_contents.read(),
                                           Parameters=parameters,
                                           Capabilities=['CAPABILITY_IAM'])
        logger.info(json.dumps(response, indent=2))




