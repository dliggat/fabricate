# Fabricate

## Install

1. Set up a `virtualenv` (I recommend [`pyenv-virtualenv`](https://github.com/yyuu/pyenv-virtualenv), highly):
  * `pyenv virtualenv fabricate`
  * `pyenv activate fabricate`
2. Install dependencies:
  * `pip install -U -r requirements.txt`
3. From this point forward, the `fab` command will be available to run the tasks from `fabfile.py`.

## Create a Project
Files in `projects` represent unique instantiations of templates for a particular purpose.

Create a `projects/${PROJECTNAME}.yaml` file and ensure it refers to a template and has parameters outlined:


```yaml
# projects/my-project.yaml

template: standard_vpc                  # Required: an existing template in 'templates/'

az_count: 3                             # Any overridden variables for the Jinja render.

parameters:                             # Parameter injection for the template
  ResourcePrefix: dliggat-vpc
  VpcCidr: "10.0.0.0/16"
  PublicSubnetAZ0Cidr: "10.0.0.0/24"
  PublicSubnetAZ1Cidr: "10.0.1.0/24"
  PrivateSubnetAZ0Cidr: "10.0.3.0/24"
  PrivateSubnetAZ1Cidr: "10.0.4.0/24"
```

Note that project files must not contain spaces, underscores, or special characters, as the filename is eventually used as a CloudFormation stack name. Alphanumeric with hyphens is best.

## Render & Validate
There are `fab` tasks to render a CloudFormation file, and validate it against the API.

```bash
fab --set project=my-project render validate
```

This creates a new directory in `_output` of the following form:

```bash
_output/my-project
├── parameters.json   # Parameters file
└── template.yaml     # Rendered template file
```

These outputs can be used directly with the CloudFormation CLI (`aws cloudformation`).

## Provisioning

To provision a stack:

```bash
fab --set project=my-project provision
```

Or all at once:

```bash
fab --set project=my-project render validate provision
```

## Stack Updates
The project name is used directly as the CloudFormation stack name. If a stack by that name already exists, the `provision` command will issue a CloudFormation `update` instead of `create`.

## Describing Stacks

To get a list of stack properties, use the `describe` task:

```bash
fab --set project=my-project describe
```

