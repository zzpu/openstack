#coding:utf-8
# Copyright 2010 United States Government as represented by the
# Administrator of the National Aeronautics and Space Administration.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

"""Starter script for Nova Compute."""

import sys
import traceback

from oslo.config import cfg

from nova.conductor import rpcapi as conductor_rpcapi
from nova import config
import nova.db.api
from nova import exception
from nova.i18n import _
from nova import objects
from nova.objects import base as objects_base
from nova.openstack.common import log as logging
from nova.openstack.common.report import guru_meditation_report as gmr
from nova import service
from nova import utils
from nova import version

CONF = cfg.CONF
CONF.import_opt('compute_topic', 'nova.compute.rpcapi')
CONF.import_opt('use_local', 'nova.conductor.api', group='conductor')


def block_db_access():
    class NoDB(object):
        def __getattr__(self, attr):
            return self

        def __call__(self, *args, **kwargs):
            stacktrace = "".join(traceback.format_stack())
            LOG = logging.getLogger('nova.compute')
            LOG.error(_('No db access allowed in nova-compute: %s'),
                      stacktrace)
            raise exception.DBNotAllowed('nova-compute')

    nova.db.api.IMPL = NoDB()


def main():
    """加载和设置配置参数，有两点需要注意：
    1. 调用rpc.set_defaults设置默认的exchange为nova，如果不设置则为
    openstack
    2. 调用rpc.init设置Transport和Notifier,Transport是
    oslo_messaging/transport.py/Transport实例，我采用的是默认的
    rpc_backend=rabbit，所以Transport采用的driver=oslo_messaging/
    _drivers/impl_rabbit.py/RabbitDriver；Notifier是一个通知消息发
    送器，它借助Transport完成通知消息的发送
    """
    config.parse_args(sys.argv)
    logging.setup('nova')
    utils.monkey_patch()
    objects.register_all()

    gmr.TextGuruMeditation.setup_autorun(version)

    if not CONF.conductor.use_local:
        block_db_access()
        objects_base.NovaObject.indirection_api = \
            conductor_rpcapi.ConductorAPI()
    """调用类方法nova/service.py/Service.create创建Service服务对象
    输入参数topic = compute， db_allowd = false；`create`方法是一个
    类方法（@classmethod），它首先基于输入参数和（/etc/nova.conf中的选
    项）设置配置，然后创建一个Service对象并返回给调用者
    """
    server = service.Service.create(binary='nova-compute',
                                    topic=CONF.compute_topic,
                                    db_allowed=CONF.conductor.use_local)
    """调用server方法启动服务并调用wait方法等待服务启动完成,serve方法创
    建Launcher服务启动实例对象（这里是ServiceLauncher）来启动服务，
    但最终会调用server.start方法启动服务。
    """
    service.serve(server)
    service.wait()
