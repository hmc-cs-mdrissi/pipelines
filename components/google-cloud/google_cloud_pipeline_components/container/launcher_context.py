# Copyright 2022 The Kubeflow Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Launcher context for launcher clients to support cancellation propagation."""
import logging
import os
import signal

from kubernetes import client, config

DEFAULT_NAMESPACE = 'kubeflow'
KFP_POD_ENV_NAME = 'KFP_POD_NAME'
KFP_NAMESPACE_ENV_NAME = 'KFP_NAMESPACE'


class KfpExecutionContext:
  """Execution context for running inside Kubeflow Pipelines.

    The base class is aware of the KFP environment and can cascade
    a pipeline cancel event to the operation through ``on_cancel`` handler.
    Args:
        on_cancel: optional, function to handle KFP cancel event.
  """

  def __init__(self, on_cancel=None):
    self._load_kfp_environment()
    logging.info('Starting KFP context')
    self._on_cancel = on_cancel
    self._original_sigterm_handler = None

  def __enter__(self):
    self._original_sigterm_handler = signal.getsignal(signal.SIGTERM)
    signal.signal(signal.SIGTERM, self._exit_gracefully)
    return self

  def __exit__(self, *_):
    signal.signal(signal.SIGTERM, self._original_sigterm_handler)

  def under_kfp_environment(self):
    """Returns true if the execution is under KFP environment."""
    return self._pod_name and self._k8s_client

  def _load_kfp_environment(self):
    self._pod_name = os.environ.get(KFP_POD_ENV_NAME, None)
    self._namespace = os.environ.get(KFP_NAMESPACE_ENV_NAME, DEFAULT_NAMESPACE)
    if not self._pod_name:
      self._k8s_client = None
    else:
      try:
        config.load_incluster_config()
        self._k8s_client = client.CoreV1Api()
      except Exception as e:
        logging.warning('Failed to load kubernetes client:' ' {}.'.format(e))
        self._k8s_client = None

    if not self.under_kfp_environment():
      logging.warning('Running without KFP context.')

  def _exit_gracefully(self, *_):
    logging.info('SIGTERM signal received.')
    if (self._on_cancel and self.under_kfp_environment()):
      logging.info('Cancelling...')
      self._on_cancel()

    logging.info('Exit')
