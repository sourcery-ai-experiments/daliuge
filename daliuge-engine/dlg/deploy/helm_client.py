#
#    ICRAR - International Centre for Radio Astronomy Research
#    (c) UWA - The University of Western Australia, 2016
#    Copyright by UWA (in the framework of the ICRAR)
#    All rights reserved
#
#    This library is free software; you can redistribute it and/or
#    modify it under the terms of the GNU Lesser General Public
#    License as published by the Free Software Foundation; either
#    version 2.1 of the License, or (at your option) any later version.
#
#    This library is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#    Lesser General Public License for more details.
#
#    You should have received a copy of the GNU Lesser General Public
#    License along with this library; if not, write to the Free Software
#    Foundation, Inc., 59 Temple Place, Suite 330, Boston,
#    MA 02111-1307  USA
#
"""
Contains a module translating physical graphs to kubernetes helm charts.
"""
import http
import json
import re
import urllib.request
import time
import requests
import os

import yaml
import subprocess
from dlg.common.version import version as dlg_version


def _write_chart(chart_dir, chart_name: str, name: str, version: str, app_version: str, home: str,
                 description, keywords: list, sources: list, kubeVersion: str):
    chart_info = {'apiVersion': "v2", 'name': name, 'type': 'application', 'version': version,
                  'appVersion': app_version, 'home': home, 'description': description,
                  'keywords': keywords, 'sources': sources, 'kubeVersion': kubeVersion}
    # TODO: Fix app_version quotations.
    with open(f'{chart_dir}{os.sep}{chart_name}', 'w', encoding='utf-8') as chart_file:
        yaml.dump(chart_info, chart_file)


def _write_values(chart_dir, config):
    with open(f"{chart_dir}{os.sep}custom-values.yaml", 'w', encoding='utf-8') as value_file:
        yaml.dump(config, value_file)


def _find_num_nodes(pgt_data):
    pgt = json.loads(pgt_data)
    nodes = list(map(lambda x: x['node'], pgt))
    islands = list(map(lambda x: x['island'], pgt))
    num_islands = len(dict(zip(islands, nodes)))
    num_nodes = list(map(lambda x, y: x + y, islands, nodes))
    return num_islands, num_nodes


class HelmClient:
    """
    Writes necessary files to launch job with kubernetes.
    """

    def __init__(self, deploy_name, chart_name="dlg-test", deploy_dir="./",
                 submit=True, chart_version="0.1.0",
                 value_config=None, physical_graph_file=None, chart_vars=None):
        if value_config is None:
            value_config = dict()
        self._chart_name = chart_name
        self._chart_vars = {'name': 'daliuge-daemon',
                            'appVersion': 'v1.0.0',
                            'home': 'https://github.com/ICRAR/daliuge/daliuge-k8s',
                            'description': 'DALiuGE k8s deployment',
                            'keywords': ['daliuge', 'workflow'],
                            'sources': ['https://github.com/ICRAR/daliuge/daliuge-k8s'],
                            'kubeVersion': ">=1.10.0-0"
                            }
        if chart_vars is not None:
            self._chart_vars.update(chart_vars)
        self._deploy_dir = deploy_dir
        self._chart_dir = os.path.join(self._deploy_dir, self._chart_name)
        self._chart_version = chart_version
        self._deploy_name = deploy_name
        self._submit = submit
        self._value_data = value_config if value_config is not None else {}
        self._physical_graph_file = physical_graph_file if physical_graph_file is not None else []
        self._num_islands, self._num_nodes = _find_num_nodes(
            self._physical_graph_file)

        if not os.path.isdir(self._deploy_dir):
            os.makedirs(self._deploy_dir)

    def create_helm_chart(self):
        """
        Translates a physical graph to a kubernetes helm chart.
        For now, it will just try to run everything in a single container.
        """
        # TODO: Interpret physical graph as helm-chart
        # run helm init
        # os.chdir(self._deploy_dir)
        # subprocess.check_output([f'helm create {self._chart_name}'], shell=True)
        # Update chart.yaml
        _write_chart(self._chart_dir, 'Chart.yaml', self._chart_name, self._chart_version,
                     dlg_version,
                     self._chart_vars['home'], self._chart_vars['description'],
                     self._chart_vars['keywords'], self._chart_vars['sources'],
                     self._chart_vars['kubeVersion'])
        # Update values.yaml
        _write_values(self._chart_dir, self._value_data)
        # Add charts
        # TODO: Add charts to helm
        # Update template
        # TODO: Update templates in helm

    def launch_helm(self):
        """
        Launches the built helm chart using the most straightforward commands possible.
        Assumes all files are prepared and validated.
        """
        if self._submit:
            os.chdir(self._deploy_dir)
            instruction = f'helm install {self._deploy_name} {self._chart_name}/  ' \
                          f'--values {self._chart_name}{os.sep}custom-values.yaml'
            subprocess.check_output([instruction],
                                    shell=True).decode('utf-8')
            query = str(subprocess.check_output(['kubectl get svc -o wide'], shell=True))
            pattern = r"-service\s*ClusterIP\s*\d+\.\d+\.\d+\.\d+"
            ip_pattern = r"\d+\.\d+\.\d+\.\d+"
            outcome = re.search(pattern, query)
            if outcome:
                manager_ip = re.search(ip_pattern, outcome.string)
                # TODO: Dynamic port value
                url = f"http://{manager_ip.group(0)}:9000/managers/island/start"
                data = json.dumps({'nodes': ["localhost"]}).encode('utf-8')
                header = {'Content-Type': 'application/json'}
                time.sleep(10)
                response = requests.post(url=url, data=data, headers=header)
                print(response.content)
                if response.status_code != http.HTTPStatus.OK:
                    print("Cluster not running!")
            else:
                print("Could not find manager IP address")

        else:
            print(f"Created helm chart {self._chart_name} in {self._deploy_dir}")

    def submit_job(self):
        """
        There is a semi-dynamic element to fetching the IPs of Node(s) to deploy to.
        Hence, launching the chart and initiating graph execution have been de-coupled.
        """
        pass
