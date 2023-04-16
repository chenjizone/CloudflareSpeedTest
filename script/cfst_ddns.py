#!/usr/bin/env python
# coding=utf-8
import subprocess
from pydantic import BaseSettings
# import schedule
import os
import json
import traceback
from tencentcloud.common import credential
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.common.profile.http_profile import HttpProfile
from tencentcloud.dnspod.v20210323 import dnspod_client, models

RESULT_PATH = "/tmp/cloudflare_result.txt"
BIN = "./CloudflareST"


class SysConfig(BaseSettings):
    exec_interval_minutes: int = 10
    exec_cmd_timeout_seconds: int = 300


class DnsPodProvider(BaseSettings):
    ak: str = ...
    sk: str = ...
    endpoint: str = "dnspod.tencentcloudapi.com"
    line: str = "境内"
    domain: str = ...

    class Config:
        env_prefix = "dnspod_"


class DnsPodService(object):

    def __init__(self):
        self.config = DnsPodProvider()
        self.client = self._new_client(self.config)

    def _new_client(self, config):
        cred = credential.Credential(config.ak, config.sk)
        httpProfile = HttpProfile()
        httpProfile.endpoint = config.endpoint
        httpProfile.keepAlive = False
        clientProfile = ClientProfile()
        clientProfile.httpProfile = httpProfile
        client = dnspod_client.DnspodClient(cred, "", clientProfile)
        return client

    def _get_record_id(self):
        subDomain, domain = self._parse_domain(self.config.domain)
        req = models.DescribeRecordListRequest()
        params = {
            "Domain": domain,
            "Subdomain": subDomain,
            "RecordType": "A",
            "RecordLine": self.config.line
        }
        req.from_json_string(json.dumps(params))
        resp = self.client.DescribeRecordList(req)
        print(resp.to_json_string())

    def _update_record(self, recordId, newIp):
        pass

    def _create_record(self, ip):
        pass

    def _parse_domain(self, domain):
        return str(domain).split(".", 1)

    def update_dns(self, ip):
        existsRecordId = self._get_record_id()
        if existsRecordId:
            self._update_record(ip)
        else:
            self._create_record(ip)


def get_best_ip(file):
    pass


def start_job(sysConfig):
    print("Starting test task...")
    try:
        runCode = subprocess.call([BIN, "-o", RESULT_PATH],
                                  shell=True,
                                  stdout=subprocess.PIPE,
                                  stderr=subprocess.STDOUT,
                                  timeout=sysConfig.exec_cmd_timeout_seconds)
        if runCode != 0:
            print("Execute failed, code: %s" % runCode)
            return
        if not os.path.exists(RESULT_PATH):
            print("No result file")
            return
        if os.path.getsize(RESULT_PATH) == 0:
            print("Result file is empty")
            return
        with open(RESULT_PATH) as f:
            bestIp = get_best_ip(f)
        if not bestIp or len(bestIp) == 0:
            print("No best IP found")
            return
        dnspodService = DnsPodService()
        dnspodService.set_best_ip(bestIp)
        print("Best IP found: %s, update dns record success..." % bestIp)
    except BaseException:
        traceback.print_exc()


if __name__ == '__main__':
    # load configuration
    config = SysConfig()
    # print("Config is", config.dict())
    # # start cron job
    # schedule.every(config.run_interval_minutes).seconds.do(start_job, config)
    # while True:
    #     schedule.run_pending()
    dnspodService = DnsPodService()
    dnspodService.update_dns("198.41.195.7")
