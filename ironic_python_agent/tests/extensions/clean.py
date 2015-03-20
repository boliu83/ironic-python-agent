# Copyright 2015 Rackspace, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import mock
from oslotest import base as test_base

from ironic_python_agent import errors
from ironic_python_agent.extensions import clean


class TestCleanExtension(test_base.BaseTestCase):
    def setUp(self):
        super(TestCleanExtension, self).setUp()
        self.agent_extension = clean.CleanExtension()
        self.node = {'uuid': 'dda135fb-732d-4742-8e72-df8f3199d244'}
        self.ports = []
        self.step = {
            'GenericHardwareManager':
                [{'step': 'erase_devices',
                  'priority': 10,
                  'interface': 'deploy'}]
        }
        self.version = {'generic': '1', 'specific': '1'}

    @mock.patch('ironic_python_agent.extensions.clean.'
                '_get_current_clean_version')
    @mock.patch('ironic_python_agent.hardware.dispatch_to_all_managers')
    def test_get_clean_steps(self, mock_dispatch, mock_version):
        mock_version.return_value = self.version

        manager_steps = {
            'SpecificHardwareManager': [
                {
                    'step': 'erase_devices',
                    'priority': 10,
                    'interface': 'deploy',
                    'reboot_requested': False
                },
                {
                    'step': 'upgrade_bios',
                    'priority': 20,
                    'interface': 'deploy',
                    'reboot_requested': True
                }
            ],
            'FirmwareHardwareManager': [
                {
                    'step': 'upgrade_firmware',
                    'priority': 30,
                    'interface': 'deploy',
                    'reboot_requested': False
                }
            ]
        }

        mock_dispatch.return_value = manager_steps
        expected_return = {
            'hardware_manager_version': self.version,
            'clean_steps': manager_steps
        }

        async_results = self.agent_extension.get_clean_steps(node=self.node,
                                                             ports=self.ports)

        self.assertEqual(expected_return, async_results.join().command_result)

    @mock.patch('ironic_python_agent.hardware.dispatch_to_managers')
    @mock.patch('ironic_python_agent.extensions.clean._check_clean_version')
    def test_execute_clean_step(self, mock_version, mock_dispatch):
        result = 'cleaned'
        mock_dispatch.return_value = result

        expected_result = {
            'clean_step': self.step['GenericHardwareManager'][0],
            'clean_result': result
        }
        async_result = self.agent_extension.execute_clean_step(
            step=self.step['GenericHardwareManager'][0],
            node=self.node, ports=self.ports,
            clean_version=self.version)
        async_result.join()

        mock_version.assert_called_once_with(self.version)
        mock_dispatch.assert_called_once_with(
            self.step['GenericHardwareManager'][0]['step'],
            self.node, self.ports)
        self.assertEqual(expected_result, async_result.command_result)

    @mock.patch('ironic_python_agent.extensions.clean._check_clean_version')
    def test_execute_clean_step_no_step(self, mock_version):
        async_result = self.agent_extension.execute_clean_step(
            step={}, node=self.node, ports=self.ports,
            clean_version=self.version)
        async_result.join()

        self.assertEqual('FAILED', async_result.command_status)
        mock_version.assert_called_once_with(self.version)

    @mock.patch('ironic_python_agent.hardware.dispatch_to_managers')
    @mock.patch('ironic_python_agent.extensions.clean._check_clean_version')
    def test_execute_clean_step_fail(self, mock_version, mock_dispatch):
        mock_dispatch.side_effect = RuntimeError

        async_result = self.agent_extension.execute_clean_step(
            step=self.step['GenericHardwareManager'][0], node=self.node,
            ports=self.ports, clean_version=self.version)
        async_result.join()

        self.assertEqual('FAILED', async_result.command_status)

        mock_version.assert_called_once_with(self.version)
        mock_dispatch.assert_called_once_with(
            self.step['GenericHardwareManager'][0]['step'],
            self.node, self.ports)

    @mock.patch('ironic_python_agent.hardware.dispatch_to_managers')
    @mock.patch('ironic_python_agent.extensions.clean._check_clean_version')
    def test_execute_clean_step_version_mismatch(self, mock_version,
                                                 mock_dispatch):
        mock_version.side_effect = errors.CleanVersionMismatch(
            {'GenericHardwareManager': 1}, {'GenericHardwareManager': 2})

        async_result = self.agent_extension.execute_clean_step(
            step=self.step['GenericHardwareManager'][0], node=self.node,
            ports=self.ports, clean_version=self.version)
        async_result.join()
        self.assertEqual('CLEAN_VERSION_MISMATCH', async_result.command_status)

        mock_version.assert_called_once_with(self.version)

    @mock.patch('ironic_python_agent.hardware.dispatch_to_all_managers')
    def _get_current_clean_version(self, mock_dispatch):
        mock_dispatch.return_value = {'SpecificHardwareManager':
                                      {'name': 'specific', 'version': '1'},
                                      'GenericHardwareManager':
                                      {'name': 'generic', 'version': '1'}}
        self.assertEqual(self.version, clean._get_current_clean_version())

    @mock.patch('ironic_python_agent.hardware.dispatch_to_all_managers')
    def test__check_clean_version_fail(self, mock_dispatch):
        mock_dispatch.return_value = {'SpecificHardwareManager':
                                      {'name': 'specific', 'version': '1'}}

        self.assertRaises(errors.CleanVersionMismatch,
                          clean._check_clean_version,
                          {'not_specific': '1'})
